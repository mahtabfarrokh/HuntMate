from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from typing_extensions import Literal
import streamlit as st
import configparser
import shutil
import time
import os

from tools.linkedin_search import LinkedinSearchTool, JobSearchParams
from prompts import fill_job_preferences, check_job_match, router_prompt

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
    skip_router: bool
    filled_job_form: bool 



# State schema for the LLM Agent
class JobMatch(TypedDict):
    match_score: int = Field(description="A score between 1 to 5 of how well the job matches the user's preferences.")
    reasonning: str = Field(description="One sentence reasonning for the choice of match_score.")
    job_summary: str = Field(description="Summary of the job in 50 words.")


# The main class for the HuntMate application
class HuntMate:
    def __init__(self):
        self.clean_cache()
        config = configparser.ConfigParser()
        config.read('./api.cfg')
        self.llm = ChatOpenAI(model="gpt-4o-mini", api_key=config['openai']['api_key'])
        self.job_llm = self.llm.with_structured_output(JobSearchParams)
        self.match_llm = self.llm.with_structured_output(JobMatch)
        self.router = self.llm.with_structured_output(Route)
        self.linkedin_tool = LinkedinSearchTool()
        self.create_workflow()
        self.batch_size = 4
        
        
    def generate_response(self, response: str, role: str = "assistant") -> None:
        """Generate the response for the user input"""
        with st.chat_message(role):
            st.markdown(response)
        st.session_state.messages.append({"role": role, "content": response})
        st.session_state

    def clean_cache(self) -> None:
        """Clean the cache before running the application"""
        if os.path.exists("./tools/__pycache__"):
            shutil.rmtree("./tools/__pycache__")
        if os.path.exists("./db/seen_jobs.csv"):
            os.remove("./db/seen_jobs.csv")
        return
    
    def main_task_router(self, state: State) -> dict:
        """Route the input to the appropriate node"""
        print("In the router")
        if state["skip_router"]:
            decision = Route(step="job_search")
        else:
            chain = router_prompt() | self.router
            decision = chain.invoke({"user_input": state["user_input"]})
            print("The type of the query is: ", decision)
        return {"route_decision": decision.step}
    
    def route_decision(self, state: State) -> str:
        """Conditional edge function to route to the appropriate node"""
        route_map = {
            "craft_email": "craft_email",
            "craft_coverletter": "craft_coverletter",
            "job_search": "collect_job_search_preferences",
        }
        if state["filled_job_form"]: 
             route_map = {
                "craft_email": "craft_email",
                "craft_coverletter": "craft_coverletter",
                "job_search": "process_job_search_params",
            }
        return route_map.get(state["route_decision"], "craft_email")
        
    def craft_email(self, state: State) -> dict:
        # TODO: Attach this to a llm call 
        return {"final_response": "Email crafted"}
    
    def craft_coverletter(self, state: State) -> dict:
        # TODO: Attach this to a llm call
        return {"final_response": "Cover letter crafted"}

    def collect_job_search_preferences(self, state: State) -> dict:
        """Prompts the user to populate all required fields for the job search"""
        print(">>>>> In collect_job_search_preferences")
        
        # chain = fill_job_preferences() | self.job_llm
        # result = chain.invoke({"user_input": state["user_input"]})
        result = JobSearchParams(job_keywords=["Machine Learning"], locations=[], remote=[], experience=[], job_type=[], limit=5, extra_preferences="")
        st.session_state.form_prefill = result
        return {"job_search_params": result, "final_response": "show_form"}


    def process_job_search_params(self, state: State) -> dict:
        """Populate the job search parameters based on the user's input"""
        ############################################################
        # TODO: You shouldn't rely on LLM to fill all the features, 
        # some are deterministic and doens't need LLM.
        ############################################################
        chain = fill_job_preferences() | self.job_llm
        result = chain.invoke({"user_input": state["user_input"]})
        print(">>>>> Job search params")
        print(result)
        return {"job_search_params": result, "user_input": state["user_input"]}

    def job_details_output(self, job: dict, job_match: JobMatch) -> str:
        """Generate the output for the job details"""
        return f"""
            ### :briefcase: {job['title']}  
            **Company:** {job['company']}  
            **Match Score:** {job_match['match_score']}   
            **Job Summary:** {job_match['job_summary']}  
            **[🔗 Job Link]({job['job_posting_link']})**  
            ---------------------------------
            """
    
    def find_related_jobs(self, state: State) -> dict:
        """Find related jobs based on the user's input"""
        counter, i = 1, 0
        chain = check_job_match() | self.match_llm
        found_jobs = self.linkedin_tool.job_search(state["job_search_params"])
        score_answer = {"3": [], "4": [], "5": []}
        while counter < state["job_search_params"].limit + 1 and  i < len(found_jobs): 
            result = chain.invoke({"user_input": str(state["job_search_params"]),
                                    "job_description": found_jobs[i]["job_description"], 
                                    "title": found_jobs[i]["title"],
                                    "company": found_jobs[i]["company"],
                                    "location": found_jobs[i]["location"],
                                    "remote_allowed": found_jobs[i]["remote_allowed"]})
            print("Result: ", result)
            if result["match_score"] > 2:
                score_answer[str(result["match_score"])].append((found_jobs[i], result))
            if result["match_score"] > 3:
                counter += 1
            i += 1

        print("Found jobs: ", len(found_jobs))
        print(score_answer)

        if len(score_answer["5"]) == 0 and len(score_answer["4"]) == 0 and len(score_answer["3"]) == 0:
            answer = "I'm sorry, I couldn't find any jobs that match your preferences. Please try again with different preferences."
            return {"final_response": answer}
        
        answer = "### 🔍  AI: Here are the list of jobs I found based on your preferences:\n"
        if len(score_answer["5"]) == 0 and len(score_answer["4"]) == 0:
            answer = "### 🔍  I couldn't find a good job match for you. Here are a list of moderate job fits:\n"

        counter = 1
        for i in range(5, 2, -1):
            for job, result in score_answer[str(i)]:
                answer += self.job_details_output(job, result)    
                counter += 1
                if counter > state["job_search_params"].limit + 5:
                    return {"final_response": answer}
                
        return {"final_response": answer}


    def create_workflow(self) -> None:
        """Create the workflow for the HuntMate application"""

        self.workflow = StateGraph(State)

        # Add nodes
        self.workflow.add_node("main_task_router", self.main_task_router)
        self.workflow.add_node("craft_email", self.craft_email)
        self.workflow.add_node("craft_coverletter", self.craft_coverletter)
        self.workflow.add_node("collect_job_search_preferences", self.collect_job_search_preferences)
        self.workflow.add_node("process_job_search_params", self.process_job_search_params)
        self.workflow.add_node("find_related_jobs", self.find_related_jobs)

        # Add edges
        self.workflow.add_edge(START, "main_task_router")
        self.workflow.add_conditional_edges(
            "main_task_router",
            self.route_decision,
            {  # Name returned by route_decision : Name of next node to visit
                "craft_email": "craft_email",
                "craft_coverletter": "craft_coverletter",
                "process_job_search_params": "process_job_search_params",
                "collect_job_search_preferences": "collect_job_search_preferences",
            },
        )
        self.workflow.add_edge("craft_email", END)
        self.workflow.add_edge("craft_coverletter", END)
        self.workflow.add_edge("collect_job_search_preferences", END)
        self.workflow.add_edge("process_job_search_params", "find_related_jobs")
        self.workflow.add_edge("find_related_jobs", END)
        self.workflow = self.workflow.compile()   
        return 

    def run(self, user_input: str, skip_router: bool = True, filled_job_form: bool = False) -> str:
        """Run the HuntMate to generate the response"""
        print("NEW RUN!!")
        response = self.workflow.invoke({"user_input": user_input, "skip_router": skip_router, "filled_job_form": filled_job_form})["final_response"]
        return response
    

# I prefer the machine learning job to be in the healthcare domain. 
# Note: if it is remote I'm okay with everywhere in Canada and US, but If it is hybrid or on-site, I strongly prefer Vancouver city, and it HAS to be in Canada!