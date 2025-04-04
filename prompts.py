from typing import List

from models import JobSearchParams

def fill_job_preferences(user_input) -> List[dict]: 
    messages = [
        {"role": "system",
          "content": """
                Think step by step and populate the JSON job search parameters based on the user's input. Leave fields empty if not provided.

                ### Additional Considerations:

                - **Locations Handling:**
                - If the user provides **only a country name**, include the country name along with its top 5 major cities.  
                    - Example: `"United States"` → `["United States", "New York", "Los Angeles", "Chicago", "Houston", "San Francisco"]`
                    - Example: `"Canada"` → `["Canada", "Toronto", "Montreal", "Vancouver", "Calgary", "Ottawa"]`
                - If the user provides **a city name alone**, do **not** add additional cities.  
                    - Example: `"Vancouver"` → `["Vancouver"]`
                - If the user provides **both a city and a country**, keep them as-is without adding extra cities.  
                    - Example: `"Vancouver, Canada"` → `["Vancouver", "Canada"]`
                    - Example: `"Los Angeles, Canada"` → `["Los Angeles", "Canada"]`

                - **Experience Level Handling:**  Pay attention to the following mappings:
                        - INTERNSHIP = "1"
                        - ENTRY_LEVEL = "2"
                        - ASSOCIATE = "3"
                        - MID_SENIOR_LEVEL = "4"
                        - DIRECTOR = "5"
                        - EXECUTIVE = "6"

                - **Job Keywords Handling:**  
                    - Include the main **essential keywords** for the job search in `job_keywords`.  

                - **Extra Preferences:**  
                    - Any additional details provided by the user should be stored in the `extra_preferences` field.
                    
                    
                ### Example:
                # User Input: I'm looking for a remote job in data science in the United States.
                # 
                # JSON Output:
                # {
                #    "job_keywords": ["data science"],
                #   "locations": ["United States", "New York", "Los Angeles", "Chicago", "Houston", "San Francisco"],
                #   "work_mode": ["2"],},


                Also make sure for the extra preferences, the user's input is stored in the `extra_preferences` field: 
                ### Example:
                # User Input: I'm looking for a AI related job in the education domain.
                # 
                # JSON Output:
                # {
                #    "job_keywords": ["AI", "Artificial Intelligence", "Machine Learning", "Deep Learning"],
                #    "extra_preferences": "Looking for a job in the education domain."},
                """},


        {"role": "user", "content": f" ### User Input: {user_input}"}
    ]
    return messages


def check_job_match(user_input: JobSearchParams, title:str, company:str, location:str, job_description:str, memory_info: List[str]) -> List[dict]:
    # user_location_pref = user_input.locations
    # if user_input.work_mode == [] or len(user_input.work_mode) == 3:
    #     workmode = "hybrid, remote, or on-site, all works."
    # else:
    #     workmode = "Only the following work modes are acceptable: "
    #     for i in user_input.work_mode:
    #         workmode += i.name + " "
    if user_input.experience == []:
        experience = "all experience levels are acceptable."
    else:
        experience = "Only the following experience levels are acceptable: "
        for i in user_input.experience:
            experience += i.name + " "
    
    recent_memory = ""
    if memory_info:
        for i in memory_info[-10:]:
            recent_memory += memory_info[i] + ", "
    else: 
        recent_memory = "No info available."

    messages = [
        {"role": "system",  "content": """  
                Fill the provided pydantic schema with the user's input and the job description.
                For the `match_score`, give a score based on the following ruberic: 
                - 5 (Perfect Match): The job aligns with all essential preferences: at least one keyword, experience level. Extra preferences (if provided) are also met.
                - 4 (Strong Match): The job matches most preferences including at least one keyword (at least 4/5 categories). Extra preferences are partially met or moderately aligned.
                - 3 (Moderate Match): The job meets at least 3/5 essential categories. It may have minor misalignment (e.g. experience level mismatch). Extra preferences are partially considered.
                - 2 (Weak Match): The job meets only 2/5 essential categories. It may have significant mismatches, and extra preferences are not met.
                - 1 (Poor Match): The job meets only 1/5 or none of the user's preferences. Major mismatches (e.g., keyword mismatch, wrong experience level) result in this score.
                
                Additional Considerations:
                If extra_preferences are marked as "important," missing them should lower the score by 1-2 points.
                A job lacking any of the keywords should not score higher than 2.
             
                Note: It's perfectly fine if the job title doesn't exactly match the keyword, as long as the keyword is mentioned in the job description.
                For example: if the keyword is "machine learning" but the job title is "Data Scientist" and the description includes machine learning tasks, that's still a valid match.

                Provide a brief justification for the score under `reasonning`.
                """},

        {"role": "user", "content": f"""
                # User Preference: 
                - Keywords: {str(user_input.job_keywords)}
                - Experience: {str(user_input.experience)}
                - Extra Preferences: {str(user_input.extra_preferences)} 
                - General Information About the User in Memory: {str(recent_memory)}
                ----------------------------------------------
                # About the job:
                - Job Title: {title}
                - Company: {company}
                - Job Description: {job_description}""" }
    ]
    return messages


def router_prompt(user_input:str) -> List[dict]:
    messages = [
        {"role": "system", "content": """
                Think step by step and route the user's input to the correct function. 
                For example, if the user says "job search," route it to the `job_search` function.

                Also extract and record any critical new information that should be persisted in chat history — such as user general preferences/constraints/information. 
                Only include information that is general and reusable across sessions, not input specific to a single task or thread.
                The key here is that only save the parts of user input that includes "Always," "Never," "Only," "Remember," etc. which indicate a general preference.
                Also if the user gives a critical personal informations, such as "I am a software engineer," save it in the memory.

                For instance:
                - If the user says, "Always give me remote jobs in the United States," route to `job_search` and store "Only remote jobs in the United States are accepted."
                - Do not include temporary or situational information, such as "I'm looking for a job in computer science right now."
                
                Focus on:
                - Identifying the appropriate function.
                - Extracting and summarizing reusable user preferences and information.
                """},
        {"role": "user", "content": f"User: {user_input}"}
    ]
    return messages

def craft_coverletter_prompt(user_input: str, memory_info: List[str], job_description:str) -> List[dict]:
    recent_memory = ""
    if memory_info:
        memory_info = memory_info[-10:]
        for i in range(len(memory_info)):
            recent_memory += memory_info[i] + ", "  
    else: 
        recent_memory = "No info available."
    
    messages = [
        {"role": "system", "content": """
                Craft a cover letter based on the job description and user input. 
                The cover letter should be personalized to the job and the user's preferences.
                
                ### Additional Considerations:
                - **User Preferences:** Incorporate the user's general preferences and constraints into the cover letter.
                - **Job Description:** Highlight relevant skills and experiences that match the job requirements.
                - **Memory Information:** If there are any recent memory items, consider incorporating them into the cover letter.
                - **Professional Tone:** Maintain a professional tone throughout the cover letter.
                - **Customization:** Ensure the cover letter is customized to the specific job and user.
                - **Length:** Keep the cover letter concise, ideally within 3-4 paragraphs.
                """},
        {"role": "user", "content": f"""
                # User Preference: 
                - User Input: {user_input}
                - General Information About the User in Memory: {str(recent_memory)}
                ----------------------------------------------
                # About the job:
                - Job Description: {job_description}
                """ }
    ]
    return messages


def find_job_user_mentioned_prompt(user_input: str, chat_history: List[str]) -> List[dict]:
    chat_history = chat_history[-10:][::-1]  # Limit to the last 10 messages for context and reverse the order
    messages = [
        {"role": "system", "content": """
                Think step by step and check if the the job in user input can be found in the chat history.
                If the job is found in the chat history, return all the job details.
                If the job is not found in the chat history, return "No job matched."

                Note: in rare cases you might find mutiple job matches in the chat history, in that case starting from the top of the history return only the first match that you find. 
                """},
        {"role": "user", "content": f"""
                # User Input: {user_input}
                # Recent Chat History: {str(chat_history)}
                """ }
    ]
    return messages
    