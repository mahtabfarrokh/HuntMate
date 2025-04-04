from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles
from langgraph.graph import StateGraph, START, END
from IPython.display import Image, display
from litellm import batch_completion, completion
from typing import List
import streamlit as st
import pandas as pd
import configparser
import shutil
import os


from tools.linkedin_search import LinkedinSearchTool, JobSearchParams
from prompts import fill_job_preferences, check_job_match, router_prompt, craft_coverletter_prompt, find_job_user_mentioned_prompt
from models import JobMatch, Route, State, JobSearchParams, JobUserMention




# TODO: check how would open-source LLMs work with the current implementation
# TODO: make suggestions on how to improve the resume based on the job description
# TODO: if the llm model is not correct prompt the user to provide the correct model name
# TODO: is there a way around this pydantic/json formatting for open-source llms? 
# TODO: Add logo and improve the UI
# TODO: find a way around project setup for users with no experience in python
# TODO: Add new chat button to reset the memory
# TODO: Add prompts for craft email, cover letter.. 
# TODO: improve the memory from csv file to a better solution



# The main class for the HuntMate application
class HuntMate:
    def __init__(self, model_name: str = "gpt-4o-mini") -> None: 
        """Initialize the HuntMate application"""
        print("HERE in INIT")
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
        if os.path.exists("db"):
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
                return df["Information"].tolist().extend(state.get("information_to_memorize", []))
        return state.get("information_to_memorize", [])

    
    def main_task_router(self, state: State) -> dict:
        """Route the input to the appropriate node"""
        print("In the router", state["skip_router"])
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
            print(">>>>>>>>>>>>>>>>>>>>>>>>")
            print("Memory: ", info)
            print("route_decision: ", decision.route)
            print(">>>>>>>>>>>>>>>>>>>>>>>>")

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
        
    def craft_email(self, state: State) -> dict:
        # TODO: Attach this to a llm call 
        return {"final_response": "Email crafted"}
    
    def find_exact_job(self, state: State) -> dict:
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
                result = self.linkedin_tool.get_job_info(job_id)
                if result :
                    return result
                else: 
                    return state["user_input"]
            except:
                return state["user_input"]

        
    def craft_coverletter(self, state: State) -> dict:
        """Generate a cover letter based on user input and memory"""
        # TODO: connect to the find exact job function and give the job info here!
        job_description = self.find_exact_job(state)
        memory_personal = self.load_personal_memory(state)
        print(">>>>>>>>>>>>>>>")
        print(job_description)
        print(">>>>>>>>>>>>>>>")
        response = completion(
            model=self.model_name,
            messages=craft_coverletter_prompt(state["user_input"], memory_personal, job_description),
            response_format=None
        )
        cover_letter = response.choices[0].message.content
        return {"final_response": cover_letter}

    def collect_job_search_preferences(self, state: State) -> dict:
        """Prompts the user to populate all required fields for the job search"""
        print(">>>>> In collect_job_search_preferences")
        response = completion(
            model= self.model_name,
            messages=fill_job_preferences(state["user_input"]),
            response_format=JobSearchParams,
        )
        json_content = response.choices[0].message.content
        result = JobSearchParams.parse_raw(json_content)
        result.limit = max(1, min(result.limit, 50))
        st.session_state.form_prefill = result
        print("Prefill the form:")
        print(result)
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
        batch_size = 4
        print(type(state["job_search_params"]))
        while counter < state["job_search_params"].limit + 1 and  i < len(found_jobs): 
            print("Processing job: ", i)
            messages = [check_job_match(state["job_search_params"], job["title"], job["company"], job["location"], job["job_description"], self.load_personal_memory(state)) for job in found_jobs[i:i+batch_size]]
            responses = batch_completion(
                model= self.model_name,
                messages=messages,
                response_format=JobMatch,
            )
            for res in responses:
                json_content = res.choices[0].message.content
                result = JobMatch.parse_raw(json_content)
                print(result)
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
        return {"final_response": "I'm sorry, I can't help with that. If you believe Hunt Mate should be able to help with this, please let us know by raising an issue in our Git repo."}
    
    def update_memory(self, state: State) -> None:
        """Save memory and chat history to CSV files."""
        # Save important information about the user preferences to user_info_memory.csv
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
    


