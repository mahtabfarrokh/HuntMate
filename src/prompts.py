from typing import List

from src.models import JobSearchParams

def fill_job_preferences(user_input) -> List[dict]: 
    messages = [
        {"role": "system",
          "content": """
                Think step by step and populate the JSON job search parameters based on the user's input. Leave fields empty if not provided.

                ### Feature Explanations:

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
                    - If the user uses abbreviations such as "AI," "ML," or "DS," expand them to their full forms.
                    - Example: "AI" → "Artificial Intelligence", "ML" → "Machine Learning", "DS" → "Data Science"
                 

                - **Extra Preferences:**  
                    - Any additional details provided by the user should be stored in the `extra_preferences` field.
                    - IMPORTANT: Do NOT include generic or obvious information (e.g., "User is looking for a job.") — we already know that. If there's nothing specific to add, leave the `extra_preferences` field blank.

                      
                ### Example:
                User Input: I'm looking for a remote job in data science in the United States.
                JSON Output:
                {
                   "job_keywords": ["Data Science"],
                   "locations": ["United States", "New York", "Los Angeles", "Chicago", "Houston", "San Francisco"],
                   "work_mode": ["2"],},


                Also make sure for the extra preferences, the user's input is stored in the `extra_preferences` field: 
                ### Example:
                User Input: I'm looking for a AI related job in the education domain. 
                JSON Output:
                {
                    "job_keywords": ["Artificial Intelligence"],
                    "extra_preferences": "Searching for a job in the education domain of AI."},
                """},


        {"role": "user", "content": f" ### User Input: {user_input}"}
    ]
    return messages


def check_job_match(user_input: JobSearchParams, title:str, company:str, job_description:str, memory_info: List[str]) -> List[dict]:
    if user_input.experience == []:
        experience = "all experience levels are acceptable."
    else:
        experience = "Only the following experience levels are acceptable: "
        for i in user_input.experience:
            experience += i.name + " "
    
    recent_memory = ", ".join(memory_info[-10:]) if memory_info else "None"

    messages = [
        {"role": "system",  "content": """  
                Fill the provided Pydantic schema with the user's input and the job description.
                For the `match_score`, give a score based on the following ruberic: 
                - 5 (Perfect Match): The job aligns with all essential preferences: at least one keyword, one of the experience level. Extra preferences (if provided) are also met.
                - 4 (Strong Match): The job matches most preferences including at least one keyword (at least 4/5 categories). Extra preferences are partially met or moderately aligned.
                - 3 (Moderate Match): The job meets at least 3/5 essential categories. It may have minor misalignment (e.g. experience level mismatch). Extra preferences are partially considered.
                - 2 (Weak Match): The job meets only 2/5 essential categories. It may have significant mismatches, and extra preferences are not met.
                - 1 (Poor Match): The job meets only 1/5 or none of the user's preferences. Major mismatches (e.g., keyword mismatch, wrong experience level) result in this score.
                
                Additional Considerations:
                If extra_preferences are marked as "important," missing them should lower the score by 1-2 points.
               
                Note: It's perfectly fine if the job title doesn't exactly match the keyword, as long as the keyword is mentioned in the job description.
                For example: if the keyword is "machine learning" but the job title is "Data Scientist" and the description includes machine learning tasks, that's still a valid match.

                Provide a brief justification for the score under `reasoning`.
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
                Think carefully and route the user's input to the correct function. 
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
    """Prompt for generating a cover letter based on user input and job description."""
    
    recent_memory = ", ".join(memory_info[-10:]) if memory_info else "None"
    
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
    

def unsupported_task_prompt(user_input: str, chat_history: List[str]) -> List[dict]:
    chat_history = chat_history[-10:][::-1]
    messages = [
        {"role": "system", "content": """
                You are a helpful assistant that can help the user with their job search.
                If user is greeting you, just say greeting back and ask how can you help them today.
                If user is asking about a topic not related to job search or crafting email or cover letter, for example asking abour the weather, just say you are not able to help with that, and point them to the right topics such as job search, crafting email, or cover letter.
                If user is asking about a topic related to job search, crafting email, or cover letter, just ask follow up questions to get more information.
                You will also be provided with the recent chat history, so you can use it to answer the user's question.

                ### Examples: 
                Example: 
                User: What is the weather in Vancouver?
                You: I'm sorry, I can't help with that. I'm here to help you with your job search, crafting email, or cover letter.

                Example:
                User: I want to apply for a job at Google.
                You: Sure, I can help you with that. What is the job title you are applying for?

                Example:
                User:  Hi there! 
                You: Hello! How can I help you today? 
         
                Example:
                User: I don't know how to interact with you. 
                You: I'm here to help you with your job search, crafting email, or cover letter. You can ask me anything about it. 

                """},
         {"role": "user", "content": f"""
                # User Input: {user_input}
                # Recent Chat History: {str(chat_history)}
                """ }
    ]
    return messages


 
def craft_email_prompt(user_input: str, memory_info: List[str], job_description:str) -> List[dict]:
    """Prompt for generating a cover letter based on user input and job description."""
    
    recent_memory = ", ".join(memory_info[-10:]) if memory_info else "None"
    
    messages = [
        {"role": "system", "content": """
                Craft a personalized email based on the job description, user input and preferences, and the recent chat history. 
                Keep the tone of the email professional and friendly. Unless user asks for a more casual tone.
         
                ### Additional Considerations:
                - **Job Description:** Highlight relevant skills and experiences that match the job requirements.
                - **Length:** Keep the email concise, ideally under 100 words. Unless user asks for more details.
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