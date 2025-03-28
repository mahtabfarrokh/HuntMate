from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles
from langgraph.graph import StateGraph, START, END
from IPython.display import Image, display
from litellm import completion
import streamlit as st
import configparser
import shutil
import os


from tools.linkedin_search import LinkedinSearchTool, JobSearchParams
from prompts import fill_job_preferences, check_job_match, router_prompt
from models import JobMatch, Route, State, JobSearchParams



# TODO: Handle long term memory langgraph
# TODO: check how would open-source LLMs work with the current implementation
# TODO: make suggestions on how to improve the resume based on the job description
# TODO: if the llm model is not correct prompt the user to provide the correct model name
# TODO: is there a way around this pydantic/json formatting for open-source llms? 
# TODO: Add logo and improve the UI
# TODO: find a way around project setup for users with no experience in python
# TODO: Add new chat button to reset the memory

# The main class for the HuntMate application
class HuntMate:
    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        """Initialize the HuntMate application"""
        print("In the init", model_name)
        self.clean_cache()
        config = configparser.ConfigParser()
        config.read('./api.cfg')
        os.environ["OPENAI_API_KEY"] = config['openai']['api_key']
        self.model_name = model_name
        self.linkedin_tool = LinkedinSearchTool()
        self.create_workflow()
        
        
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
            response = completion(
                model= self.model_name,
                messages=router_prompt(state["user_input"]),
                response_format=Route,
            )
            json_content = response.choices[0].message.content
            decision = JobSearchParams.parse_raw(json_content)
            print("The type of the query is: ", decision)
        return {"route_decision": decision.step}
    
    def route_decision(self, state: State) -> str:
        """Conditional edge function to route to the appropriate node"""
        route_map = {
            "craft_email": "craft_email",
            "craft_coverletter": "craft_coverletter",
            "job_search": "collect_job_search_preferences",
            "unsupported_task": "unsupported_task"
        }
        if state["filled_job_form"]: 
             route_map = {
                "craft_email": "craft_email",
                "craft_coverletter": "craft_coverletter",
                "job_search": "process_job_search_params",
                "unsupported_task": "unsupported_task"
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
        # response = completion(
        #     model= self.model_name,
        #     messages=fill_job_preferences(state["user_input"]),
        #     response_format=JobSearchParams,
        # )
        # json_content = response.choices[0].message.content
        # result = JobSearchParams.parse_raw(json_content)
        # if result.limit < 1:
        #     result.limit = 1
        # if result.limit > 50: 
        #     result.limit = 50
        result = JobSearchParams(job_keywords=["Machine Learning"], locations=["United States"], work_mode=[], experience=[], job_type=[], limit=20, extra_preferences="I am looking for machine learning jobs in healthcare domain. Exmples: cancer prognosis, medical imaging, survival analysis, etc.")
        st.session_state.form_prefill = result
        return {"job_search_params": result, "final_response": "show_form"}

    def process_job_search_params(self, state: State) -> dict:
        """Populate the job search parameters based on the user's input"""
        print(">>>>> In process_job_search_params")
        response = completion(
            model= self.model_name,
            messages=fill_job_preferences(state["user_input"]),
            response_format=JobSearchParams, 
        )
        json_content = response.choices[0].message.content
        result = JobSearchParams.parse_raw(json_content)
        if result.locations == []:
            result.locations = ["Worldwide"]
        print(">>>>> Job search params")
        print(result)
        return {"job_search_params": result, "user_input": state["user_input"]}

    def job_details_output(self, job: dict, job_match: JobMatch) -> str:
        """Generate the output for the job details"""
        # TODO: This should be moved to app.py
        return f"""### :briefcase: {job['title']}  \n ###### **Company:** {job['company']}  \n ###### **Match Score:** {job_match.match_score}  \n ###### **Job Summary:** {job_match.job_summary}  \n ###### **Job Reasoning:** {job_match.reasonning}  \n ###### **[🔗 Job Link]({job['job_posting_link']})**  \n---------------------------------\n"""
    
    def find_related_jobs(self, state: State) -> dict:
        """Find related jobs based on the user's input"""
        counter, i = 1, 0
        score_answer = {"1":[], "2":[],"3": [], "4": [], "5": []}
        
        found_jobs = self.linkedin_tool.job_search(state["job_search_params"])
        print("Found jobs: ", len(found_jobs))

        while counter < state["job_search_params"].limit + 1 and  i < len(found_jobs): 
            print("Processing job: ", i)
            response = completion(
                model= self.model_name,
                messages=check_job_match(str(state["job_search_params"]), found_jobs[i]["title"], found_jobs[i]["company"], found_jobs[i]["location"], found_jobs[i]["job_description"]),
                response_format=JobMatch,
            )
            json_content = response.choices[0].message.content
            result = JobMatch.parse_raw(json_content)

            print("Match score: ", result.match_score, found_jobs[i]["title"])

            score_answer[str(result.match_score)].append((found_jobs[i], result))
            if result.match_score > 3:
                counter += 1
            i += 1
        
        answer = f"""### 🔍 Here are the list of jobs I found based on your preferences:\n"""
        if len(score_answer["5"]) == 0 and len(score_answer["4"]) == 0:
            answer = f"### 🔍  I couldn't find a good job match for you. Here are a list of moderate job fits:\n"

        counter = 1
        for i in range(5, 0, -1):
            for job, result in score_answer[str(i)]:
                answer += self.job_details_output(job, result)    
                counter += 1
                if counter > state["job_search_params"].limit + 5:
                    return {"final_response": answer}
                
        return {"final_response": answer}

    def unsupported_task(self, state: State) -> dict:
        """Return a response for an unsupported task"""
        return {"final_response": "I'm sorry, I can't help with that. If you believe JobMate should be able to help with this, please let us know by raising an issue in our Git repo."}
    
    def create_workflow(self) -> None:
        """Create the workflow for the HuntMate application"""

        self.workflow = StateGraph(State)

        # Add nodes
        self.workflow.add_node("main_task_router", self.main_task_router)
        self.workflow.add_node("craft_email", self.craft_email)
        self.workflow.add_node("unsupported_task", self.unsupported_task)
        self.workflow.add_node("craft_coverletter", self.craft_coverletter)
        self.workflow.add_node("collect_job_search_preferences", self.collect_job_search_preferences)
        self.workflow.add_node("process_job_search_params", self.process_job_search_params)
        self.workflow.add_node("find_related_jobs", self.find_related_jobs)

        # Add edges
        self.workflow.add_edge(START, "main_task_router")
        self.workflow.add_conditional_edges(
            "main_task_router",
            self.route_decision,
            { 
                "craft_email": "craft_email",
                "craft_coverletter": "craft_coverletter",
                "process_job_search_params": "process_job_search_params",
                "collect_job_search_preferences": "collect_job_search_preferences",
                "unsupported_task": "unsupported_task"
            },
        )
        self.workflow.add_edge("craft_email", END)
        self.workflow.add_edge("craft_coverletter", END)
        self.workflow.add_edge("collect_job_search_preferences", END)
        self.workflow.add_edge("process_job_search_params", "find_related_jobs")
        self.workflow.add_edge("find_related_jobs", END)
        self.workflow.add_edge("unsupported_task", END)

        self.workflow = self.workflow.compile()   
        # with open("diagram.png", "wb") as f:
        #     f.write(
        #     self.workflow.get_graph().draw_mermaid_png(
        #         draw_method=MermaidDrawMethod.API,
        #     )
        #     )
        return 

    def run(self, user_input: str, skip_router: bool = True, filled_job_form: bool = False) -> str:
        """Run the HuntMate to generate the response"""
        response = self.workflow.invoke({"user_input": user_input, "skip_router": skip_router, "filled_job_form": filled_job_form})["final_response"]
        return response
    


