from typing import List


def fill_job_preferences(user_input) -> List[dict]: 
    messages = [
        {"role": "system",
          "content": """
                Populate the JSON job search parameters based on the user's input. Leave fields empty if not provided.

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
                    - Any additional details provided by the user should be stored in the `extra_preferences` field."""},
        {"role": "user", "content": f" ### User Input: {user_input}"}
    ]
    return messages


def check_job_match(user_input, title, company, location, job_description) -> List[dict]:
    messages = [
        {"role": "system",  "content": """  
                Fill the provided pydantic schema with the user's input and the job description.
                For the `match_score`, give a score based on the following ruberic: 
                - 5 (Perfect Match): The job aligns with all essential preferences: at least one keyword, location, remote type, experience level, and job type. Extra preferences (if provided) are also met.
                - 4 (Strong Match): The job matches most preferences including at least one keyword (at least 4/5 categories). Extra preferences are partially met or moderately aligned.
                - 3 (Moderate Match): The job meets at least 3/5 essential categories. It may have minor misalignment (e.g., remote flexibility or experience level mismatch). Extra preferences are partially considered.
                - 2 (Weak Match): The job meets only 2/5 essential categories. It may have significant mismatches, such as incorrect location or experience level. Extra preferences are not met.
                - 1 (Poor Match): The job meets only 1/5 or none of the user's preferences. Major mismatches (e.g., wrong job type, wrong experience level, incorrect location) result in this score.
                
                Additional Considerations:
                If extra_preferences are marked as "important," missing them should lower the score by 1-2 points.
                A job lacking essential keywords should not score higher than 2.
                A remote job mismatch is less penalizing than a location mismatch if remote flexibility is unclear.
                
                Provide a brief justification for the score under `reasonning`.
                """},
        {"role": "user", "content": f"""
                ### User Preference: {user_input} 
                ### Job Title: {title}
                ### Company: {company}
                ### Location: {location}
                ### Job Description: {job_description}""" }
    ]
    return messages


def router_prompt(user_input) -> List[dict]:
    messages = [
        {"role": "system", "content": """
                Route the user input to the appropriate function based on the user's input. 
                For example, if the user input is "job search," the system should route the input to the `job_search` function."""},
        {"role": "user", "content": f"User: {user_input}"}
    ]
    return messages


