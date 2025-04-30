from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles
from langgraph.graph import StateGraph, START, END
from IPython.display import Image, display
from litellm import batch_completion, completion
from typing import List, Dict, Any
import streamlit as st
import pandas as pd
import configparser
import Levenshtein
import logging
import shutil
import time
import json
import os


from src.settings import AppConfig
from src.tools.jobspy_search import JobSpySearchTool
from src.tools.linkedin_search import LinkedinSearchTool
from src.models import JobMatch, Route, State, JobSearchParams, JobUserMention
from src.prompts import fill_job_preferences, check_job_match, router_prompt, craft_coverletter_prompt, find_job_user_mentioned_prompt



logger = logging.getLogger(__name__)

# The main class for the HuntMate application
class HuntMate:
    def __init__(self, model_name: str = "gpt-4o-mini") -> None: 
        """Initialize the HuntMate application"""
        logger.info("Initializing HuntMate")
        self.clean_cache()
        config = configparser.ConfigParser()
        config.read('./api.cfg')
        os.environ["OPENAI_API_KEY"] = config['openai']['api_key']
        self.model_name = model_name
        self.linkedin_tool = LinkedinSearchTool()
        self.jobspy_tool = JobSpySearchTool()
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
        if os.path.exists("./my_linkedin_api/__pycache__"):
            shutil.rmtree("./my_linkedin_api/__pycache__")
        if os.path.exists("db"):
            # RESET the memory
            for file in os.listdir("db"):
                file_path = os.path.join("db", file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        # Ensure the db directory exists
        os.makedirs("db", exist_ok=True)

    def load_personal_memory(self, state) -> List[str]: 
        """Load the memory from the user_info_memory.csv file"""
        if os.path.exists("db/user_info_memory.csv"):
            df = pd.read_csv("db/user_info_memory.csv")
            if not df.empty:
                return df["Information"].tolist() + state.get("information_to_memorize", [])
        return state.get("information_to_memorize", [])

    
    def main_task_router(self, state: State) -> Dict[str, Any]:
        """Route the input to the appropriate node"""
        logger.info("In the router %s", state["skip_router"])
        if state["skip_router"]:
            return {"route_decision": "job_search"}
        else:
            response = completion(
                model= self.model_name,
                messages=router_prompt(state["user_input"]),
                response_format=Route,
            )
            json_content = response.choices[0].message.content
            decision = Route.parse_raw(json_content)

            if decision.information_to_memorize: 
                info = state.get("information_to_memorize", []) + [decision.information_to_memorize]
            else: 
                info = state.get("information_to_memorize", [])

            logger.info("Memory: %s", info)
            logger.info("route_decision: %s", decision.route)

            return {"route_decision": decision.route, "information_to_memorize": info}
    
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
        return route_map.get(state["route_decision"], "unsupported_task")
        
    def craft_email(self, state: State) -> Dict[str, Any]:
        # TODO: Attach this to a llm call 
        return {"final_response": "Email crafted"}
    
    def find_exact_job(self, state: State) -> str:
        """Find the exact job the user is selecting based on the user's input and history"""
        chat_history = []
        if os.path.exists("db/chat_history.csv"):
            chat_history = pd.read_csv("db/chat_history.csv")["chat_history"].tolist()

        response = completion(
            model=self.model_name,
            messages=find_job_user_mentioned_prompt(state["user_input"], chat_history),
            response_format=JobUserMention,  
        )
        json_content = response.choices[0].message.content
        result = JobUserMention.parse_raw(json_content)
        if result.description == "No job matched.":
            return state["user_input"]
        else:
            try: 
                job_id = result.description.split("https://www.linkedin.com/jobs/view/")[1].split(")")[0]
                complete_info = self.linkedin_tool.get_job_info(job_id)
                if complete_info:
                    return complete_info
                else: 
                    return result.description
            except:
                return state["user_input"]

        
    def craft_coverletter(self, state: State) -> Dict[str, Any]:
        """Generate a cover letter based on user input and memory"""
        job_description = self.find_exact_job(state)
        memory_personal = self.load_personal_memory(state)
        response = completion(
            model=self.model_name,
            messages=craft_coverletter_prompt(state["user_input"], memory_personal, job_description),
            response_format=None
        )
        cover_letter = response.choices[0].message.content
        return {"final_response": cover_letter}

    def collect_job_search_preferences(self, state: State) -> Dict[str, Any]:
        """Prompts the user to populate all required fields for the job search"""
        logger.info(">>>>> In collect_job_search_preferences")
        response = completion(
            model= self.model_name,
            messages=fill_job_preferences(state["user_input"]),
            response_format=JobSearchParams,
        )
        json_content = response.choices[0].message.content
        result = JobSearchParams.parse_raw(json_content)
        result.limit = max(AppConfig.MIN_JOBS, min(result.limit, AppConfig.MAX_JOBS))
        st.session_state.form_prefill = result
        logger.info("Prefill the form:")
        logger.info("Result: %s", result.dict())
        return {"job_search_params": result, "final_response": "show_form"}

    def process_job_search_params(self, state: State) -> Dict[str, Any]:
        """Populate the job search parameters based on the user's input"""
        logger.info(">>>>> In process_job_search_params")
        response = completion(
            model= self.model_name,
            messages=fill_job_preferences(state["user_input"]),
            response_format=JobSearchParams, 
        )
        json_content = response.choices[0].message.content
        result = JobSearchParams.parse_raw(json_content)
        if result.locations == []:
            result.locations = ["Worldwide"]
        logger.info(">>>>> Job search params")
        logger.info("Result:\n%s", result.dict())
        return {"job_search_params": result, "user_input": state["user_input"]}

    def job_details_output(self, job: dict, job_match: JobMatch) -> str:
        """Generate the output for the job details"""

        source_class = str(job["site"]).capitalize()  # default class if unknown
        return f""" 💼 {job['title']} [🌀 {source_class}] \n ###### **Company:** {job['company']}  \n ###### **Match Score:** {job_match.match_score}  \n ###### **Job Summary:** {job_match.job_summary}  \n ###### **Job Reasoning:** {job_match.reasonning}  \n ###### **[🔗 Link to the job posting]({job['job_posting_link']})**  \n---------------------------------\n"""
     
    def basic_keyword_match(self, job: dict, keywords: List[str]) -> bool:
        """Check if the job title or description contains any of the keywords"""
        title = job["title"].lower()
        description = job["job_description"].lower()
        for keyword in keywords:
            if keyword.lower() in title or keyword.lower() in description:
                return True
        return False

    def remove_duplicate_jobs(self, linkedin_jobs: List[Dict[str, str]], jobspy_jobs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """ Remove duplicate jobs based on company and title edit distance """

        def is_similar(str1: str, str2: str, threshold: float = 0.6) -> bool:
            """Check if two strings are similar based on a threshold using Levenshtein ratio."""
            return Levenshtein.ratio(str1.lower(), str2.lower()) >= threshold
        

        filtered_jobspy = []
        for jobspy_job in jobspy_jobs:
            duplicate = False
            for linkedin_job in linkedin_jobs:
                if is_similar(linkedin_job["title"], jobspy_job["title"]) and is_similar(linkedin_job["company"], jobspy_job["company"]):
                    duplicate = True
                    break
            if not duplicate:
                filtered_jobspy.append(jobspy_job)

        # Combine filtered jobspy jobs with linkedin jobs
        return filtered_jobspy + linkedin_jobs

    def find_related_jobs(self, state: State) -> Dict[str, Any]:
        """Find related jobs based on the user's input"""
        counter, i = 1, 0
        start_time = time.time()
        score_answer = {"1":[], "2":[],"3": [], "4": [], "5": []}
        
        linkedin_jobs, jobspy_jobs = [], []

        if state["selected_websites"] == []:
            state["selected_websites"] = ["Indeed", "LinkedIn", "Google", "Glassdoor"]
        
        if "LinkedIn" in state["selected_websites"]:
            linkedin_jobs = self.linkedin_tool.job_search(state["job_search_params"])
            if len(state["selected_websites"]) > 1:
                state["selected_websites"].remove("LinkedIn")

        if len(state["selected_websites"]) > 0:
            jobspy_jobs = self.jobspy_tool.job_search(state["job_search_params"], state["selected_websites"])
        
        found_jobs = self.remove_duplicate_jobs(linkedin_jobs, jobspy_jobs)

        found_jobs = [job for job in found_jobs if self.basic_keyword_match(job, state["job_search_params"].job_keywords)]
        mid_time = time.time()
        logger.info("Time taken for job search (mid - start): %s", mid_time - start_time)
        logger.info("Found jobs: %s", len(found_jobs))
        
        batch_size = AppConfig.JOB_MATCH_BATCH_SIZE
        while counter < state["job_search_params"].limit + 1 and  i < len(found_jobs): 
            logger.info("Processing job: %s", i)
            messages = [check_job_match(state["job_search_params"], job["title"], job["company"], job["job_description"], self.load_personal_memory(state)) for job in found_jobs[i:i+batch_size]]
            responses = batch_completion(
                model= self.model_name,
                messages=messages,
                response_format=JobMatch,
            )
            for res in responses:
                json_content = res.choices[0].message.content
                result = JobMatch.parse_raw(json_content)
                logger.info("Result:\n%s", result.dict())
                score_answer[str(result.match_score)].append((found_jobs[i], result))
                if result.match_score > 3:
                    counter += 1
                i += 1

        answer = f"""### 🔍 Here are the list of jobs I found based on your preferences:\n"""
        if len(score_answer["5"]) == 0 and len(score_answer["4"]) == 0:
            if len(score_answer["3"]) == 0 and len(score_answer["2"]) == 0 and len(score_answer["1"]) == 0:
                return {"final_response": "I couldn't find any job matches for you. Please try a more general list of job keywords or location. Also increase the limit value to get more jobs."}
            else:
                answer = f"### 🔍  I couldn't find a good job match for you. Here are a list of moderate job fits:\n"

        counter = 1
        for i in range(5, 0, -1):
            for job, result in score_answer[str(i)]:
                answer += self.job_details_output(job, result)    
                counter += 1
                if counter > state["job_search_params"].limit + AppConfig.EXTRA_JOBS_TO_SEARCH_LOWER:
                    return {"final_response": answer}
        end_time = time.time()
        logger.info("Main function time (end - start): %s", end_time - start_time)
        logger.info("Main function time (end - mid): %s", end_time - mid_time)
        return {"final_response": answer}

    def unsupported_task(self, state: State) -> Dict[str, Any]:
        """Return a response for an unsupported task"""
        return {"final_response": "I'm sorry, I can't help with that. If you believe Hunt Mate should be able to help with this, please let us know by raising an issue in our Git repo."}
    
    def update_memory(self, state: State) -> None:
        """Save memory and chat history to CSV files."""
        user_info_memory_path = "db/user_info_memory.csv"
        if len(state.get("information_to_memorize", [])) > 0:
            # Load existing data if the file exists
            if os.path.exists(user_info_memory_path):
                existing_data = pd.read_csv(user_info_memory_path)
            else:
                existing_data = pd.DataFrame(columns=["Information"])

            new_data = pd.DataFrame(state["information_to_memorize"], columns=["Information"])
            updated_data = pd.concat([existing_data, new_data], ignore_index=True)
            updated_data.to_csv(user_info_memory_path, index=False)

        # Save user_input and final_response to chat_history.csv
        chat_history_path = "db/chat_history.csv"
        new_data = pd.DataFrame({
            "chat_history": [state.get("user_input", ""), state.get("final_response", "")]
        })
        if os.path.exists(chat_history_path):
            existing_data = pd.read_csv(chat_history_path)
        else:
            existing_data = pd.DataFrame(columns=["chat_history"])

        updated_data = pd.concat([existing_data, new_data], ignore_index=True)
        updated_data.to_csv(chat_history_path, index=False)

    def save_diagram(self, path) -> None:
        with open(path, "wb") as f:
            f.write(
            self.workflow.get_graph().draw_mermaid_png(
                draw_method=MermaidDrawMethod.API,
        ))
            
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
        self.workflow.add_node("update_memory", self.update_memory)

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
        self.workflow.add_edge("craft_email", "update_memory")
        self.workflow.add_edge("craft_coverletter", "update_memory")
        self.workflow.add_edge("collect_job_search_preferences", "update_memory")
        self.workflow.add_edge("process_job_search_params", "find_related_jobs")
        self.workflow.add_edge("find_related_jobs", "update_memory")
        self.workflow.add_edge("unsupported_task", "update_memory")
        self.workflow.add_edge("update_memory", END)

        self.workflow = self.workflow.compile()   

        # self.save_diagram("./images/diagram.png")
        return 

    def run(self, user_input: str, skip_router: bool = True, filled_job_form: bool = False, websites: List[str] = []) -> str:
        """Run the HuntMate to generate the response"""
        response = self.workflow.invoke({"user_input": user_input, 
                                         "skip_router": skip_router, 
                                         "filled_job_form": filled_job_form, 
                                         "selected_websites": websites})["final_response"]
        return response
    


