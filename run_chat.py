from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from typing_extensions import Literal
import configparser
import shutil
import os

from tools.linkedin_search import LinkedinSearchTool, JobSearchParams


# Schema for structured output to use as routing logic
class Route(BaseModel):
    step: Literal["craft_email", "craft_coverletter", "job_search"] = Field(
        None, description="The next step in the routing process"
    )


# State schema for the LLM Agent
class State(TypedDict):
    user_input: str
    route_decision: str
    job_search_params: JobSearchParams
    final_response: str


# State schema for the LLM Agent
class JobMatch(TypedDict):
    is_match: bool = Field(description="Whether the job matches the user's preferences")
    reasonning: str = Field(description="One sentence reasonning for the choice of is_match")
    job_summary: str = Field(description="Summary of the job in 30 words.")


# The main class for the HuntMate application
class HuntMate:
    def __init__(self):
        self.clean_cache()
        config = configparser.ConfigParser()
        config.read('./api.cfg')
        self.llm = ChatOpenAI(model="gpt-4o-mini", api_key=config['openai']['api_key'])
        self.linkedin_tool = LinkedinSearchTool()
        self.create_workflow()
        self.batch_size = 4

    def clean_cache(self) -> None:
        """Clean the cache before running the application"""
        if os.path.exists("./tools/__pycache__"):
            shutil.rmtree("./tools/__pycache__")
        if os.path.exists("./db/seen_jobs.csv"):
            os.remove("./db/seen_jobs.csv")
        return
    
    def llm_call_router(self, state: State) -> dict:
        """Route the input to the appropriate node"""
        print("In the router")
        self.router = self.llm.with_structured_output(Route)
        # Run the augmented LLM with structured output to serve as routing logic
        decision = self.router.invoke(
            [
                SystemMessage(
                    content="Route the input to the correct choice of task based on the user's request."
                ),
                HumanMessage(content=state["user_input"]),
            ]
        )
        print("The type of the query is: ", decision)
        return {"route_decision": decision.step}
    
    def route_decision(self, state: State) -> str:
        """Conditional edge function to route to the appropriate node"""
        route_map = {
            "craft_email": "craft_email",
            "craft_coverletter": "craft_coverletter",
            "job_search": "populate_job_search_params",
        }
        return route_map.get(state["route_decision"], "craft_email")
        
    def craft_email(self, state: State) -> dict:
        # TODO: Attach this to a llm call 
        return {"final_response": "Email crafted"}
    
    def craft_coverletter(self, state: State) -> dict:
        # TODO: Attach this to a llm call
        return {"final_response": "Cover letter crafted"}

    def job_search_user_interaction(self, result: JobSearchParams) -> str:
        """Prompts the user to populate all required fields for the job search"""
      
        questions = {
            "limit": "AI: Please provide the number of jobs I should be searching through:",
            "remote": "AI: Please provide your preference for remote: On-site, Remote, Hybrid",
            "experience": "AI: Please provide your preference for experience: internship, entry-level, associate, mid-senior-level, director, executive",
            "job_type": "AI: Please provide your preference for job type: full-time, contract, part-time, temporary, internship, volunteer, other",
            "location_name": "AI: Please provide your preference for location name:",
            "job_keywords": "AI: Please provide your preference for job keywords:"
        }
        explanation = ""
        for field, question in questions.items():
            if field == "limit" or getattr(result, field) == []:
                print(question)
                input_value = input("You: ").lower()
                explanation += question + " " + input_value + "\n"
        
        question = "AI: Please describe any other preferences you have for the job search:"
        print(question)
        input_value = input("You: ").lower()
        explanation += question + " " + input_value + "\n" 

        return explanation
        
    def populate_job_search_params(self, state: State) -> dict:
        """Populate the job search parameters based on the user's input"""
        self.job_llm = self.llm.with_structured_output(JobSearchParams)
        result = self.job_llm.invoke([
                SystemMessage(
                    content="Populate the job search parameters based on the user's input. Leave it empty if not provided."
                ),
                HumanMessage(content=state["user_input"]),
            ])
        
        state["user_input"] += "\n" + self.job_search_user_interaction(result)

        result = self.job_llm.invoke([
                SystemMessage(
                    content="Populate the job search parameters based on the user's input. Leave it empty if not provided."
                ),
                HumanMessage(content=state["user_input"]),
            ])

        return {"job_search_params": result, "user_input": state["user_input"]}


    def find_related_jobs(self, state: State) -> dict:
        """Find related jobs based on the user's input"""
        found_jobs = self.linkedin_tool.job_search(state["job_search_params"])
        self.match_llm = self.llm.with_structured_output(JobMatch)
        answer = "AI: Here are some jobs I found based on your preferences:\n"
        counter = 1
        human_input = "User Input and preference: " + state["user_input"] + "\n" + "Job Information: \n" 
        for job in found_jobs:
            result = self.match_llm.invoke([
                SystemMessage(
                    content="Fill the pydantic schema with the job details."
                ),
                HumanMessage(content=human_input + str(job)),
            ])
            if result["is_match"]:
                answer += "Job " + str(counter) + ": " + result["job_summary"] + "\n" + "Reasoning: " + result["reasonning"] + "\n"
                answer +=  "Job title is:" + job["title"] +"\n"
                answer +=  "Comapny name is:" + job["company"] +"\n"
                answer +=  "Job link is:" + job["job_posting_link"] +"\n" + "-----------------\n"
                counter += 1
                         
        return {"final_response": answer}


    def create_workflow(self) -> None:
        """Create the workflow for the HuntMate application"""

        self.workflow = StateGraph(State)

        # Add nodes
        self.workflow.add_node("llm_call_router", self.llm_call_router)
        self.workflow.add_node("craft_email", self.craft_email)
        self.workflow.add_node("craft_coverletter", self.craft_coverletter)
        self.workflow.add_node("populate_job_search_params", self.populate_job_search_params)
        self.workflow.add_node("find_related_jobs", self.find_related_jobs)

        # Add edges
        self.workflow.add_edge(START, "llm_call_router")
        self.workflow.add_conditional_edges(
            "llm_call_router",
            self.route_decision,
            {  # Name returned by route_decision : Name of next node to visit
                "craft_email": "craft_email",
                "craft_coverletter": "craft_coverletter",
                "populate_job_search_params": "populate_job_search_params",
            },
        )
        self.workflow.add_edge("craft_email", END)
        self.workflow.add_edge("craft_coverletter", END)
        self.workflow.add_edge("populate_job_search_params", "find_related_jobs")
        self.workflow.add_edge("find_related_jobs", END)
        self.workflow = self.workflow.compile()   
        return 

    def run(self) -> None:
        """Run the HuntMate application"""
        print("AI: Welcome to HuntMate! I am here to help you with your job search.")
        print("AI: You can type 'exit' anytime to quit the application.")   
        while True:
            user_input = input("You: ")
            if user_input == "exit":
                break
            response = self.workflow.invoke({"user_input": user_input})["final_response"]
            print(response)

        print("AI: Goodbye! Have a great day!")
        return

if __name__ == "__main__":
    HuntMate().run()
