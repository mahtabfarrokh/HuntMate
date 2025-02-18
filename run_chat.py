from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from IPython.display import Image, display
from pydantic import BaseModel, Field, List
from typing_extensions import Literal
from langchain_core.messages import HumanMessage, SystemMessage



from tools.linkedin_search import LinkedinSearchTool



# Schema for structured output to use as routing logic
class Route(BaseModel):
    # TODO: Add more possible routes and actions to take! 
    step: Literal["craft_email", "craft_coverletter", "linkedin_job_search"] = Field(
        None, description="The next step in the routing process"
    )

class JobSearchParams(BaseModel):
    job_keywords: str = Field(description="Keywords for the job search")
    location_name: str = Field(description="Location name for the job search")
    remote: List[Literal["On-site", "Remote", "Hybrid"]] = Field(description="Remote job options")
    experience: List[Literal["internship", "entry-level", "associate", "mid-senior-level", "director", "executive"]] = Field(description="Experience levels")
    job_type: List[Literal["full-time", "contract", "part-time", "temporary", "internship", "volunteer", "other"]] = Field(description="Types of jobs")
    limit: int = Field(description="Limit on the number of jobs to return")


class State(TypedDict):
    user_input: str
    route_decision: str
    job_search_params: JobSearchParams
    final_response: str


class HuntMate:
    def __init__(self):
        self.supervisor = create_supervisor()
        self.react_agent = create_react_agent()
        self.llm = ChatOpenAI("gpt-4o-mini")
        self.router = self.llm.with_structured_output(Route)
        self.Linkedin = LinkedinSearchTool()

    def llm_call_router(self, state: State):
        """Route the input to the appropriate node"""
        # Run the augmented LLM with structured output to serve as routing logic
        decision = self.router.invoke(
            [
                SystemMessage(
                    content="Route the input to craft_email, craft_coverletter, or linkedin_job_search based on the user's request."
                ),
                HumanMessage(content=state["input"]),
            ]
        )
        return {"route_decision": decision.step}

    def craft_email(self, state: State):
        # TODO: Attach this to a llm call
        return {"final_response": "Email crafted"}
    
    def craft_coverletter(self, state: State):
        # TODO: Attach this to a llm call
        return {"final_response": "Cover letter crafted"}

    def populate_job_search_params(self, state: State):
        # TODO
        return {"job_search_params": JobSearchParams(**state["input"])}



    def create_workflow(self):
        # Build workflow
        workflow = StateGraph(State)

        # Add nodes
        workflow.add_node("llm_call_router", self.llm_call_router)
        workflow.add_node("craft_email", self.craft_email)
        workflow.add_node("craft_coverletter", self.craft_coverletter)
        workflow.add_node("populate_job_search_params", self.populate_job_search_params)

        workflow.add_edge(START, "llm_call_router")
        # TODO: complete this ..

    def run(self):
        while True:
            user_input = input("You: ")
            if user_input == "exit":
                break
            response = self.workflow.invoke(user_input)
            print("AI: ", response)