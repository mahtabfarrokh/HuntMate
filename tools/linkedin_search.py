
from linkedin_api import Linkedin
from typing import List
import pandas as pd
import configparser
import time
import os


from models import JobSearchParams


MAX_SEARCH_ITEMS = 5  # Limit for job keywords and locations


# Tool for searching jobs on LinkedIn using the LinkedIn API
class LinkedinSearchTool:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('./api.cfg')
        self.api = Linkedin(config['linkedin']['username'], config['linkedin']['password'])

    def get_company_name(self, details: dict) -> str:
        """ Get company name from company id """
        company_details = details.get("companyDetails", {})
        for key, value in company_details.items():
            for sub_key, sub_value in value.items():
                company_name = sub_value.get("name")
                if company_name:
                    return company_name
        return "Unknown"
    
    def job_search(self, search_params: JobSearchParams) -> List[dict]:
        """ Search for jobs on LinkedIn """

        print(search_params.experience)
        print("-------")
        all_jobs = []
        if "db" not in os.listdir():
            os.mkdir("db")
        if "seen_jobs.csv" not in os.listdir("./db"):
            seen_jobs = set()
        else:   
            seen_jobs = set(pd.read_csv("./db/seen_jobs.csv")["job_id"])

        print("Searching for jobs on LinkedIn")

        for keyword in search_params.job_keywords[:MAX_SEARCH_ITEMS]: 
            for location in search_params.locations[:MAX_SEARCH_ITEMS]:
                input_search = {
                    "keywords": keyword,
                    "location": location,
                    "limit": search_params.limit ,  # Add extra jobs to account for duplicates or wrong matches
                    "remote": [remote.value for remote in search_params.work_mode],
                    "experience": [experience.value for experience in search_params.experience],
                    "job_type": [job_type[0].upper() for job_type in search_params.job_type],
                    "listed_at": 24*60*60*30,  # Jobs listed in the last 30 days
                }

                print(input_search)
                start_time = time.time()
                try: 
                    jobs = self.api.search_jobs(**input_search)
                except Exception as e:
                    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                    print(f"Error searching for jobs: {str(e)}")
                    continue
                
                for job in jobs:
                    try:
                        # Get detailed job information
                        job_id = job["entityUrn"].split(":")[-1]
                        if job_id in seen_jobs:
                            continue
                        seen_jobs.add(job_id)
                        details = self.api.get_job(job_id)
                        select_info = {"title": details.get('title', 'unknown'),
                                        "company": self.get_company_name(details),
                                        "location": details.get('formattedLocation', 'unknown'),
                                        "remote_allowed": details.get('workRemoteAllowed', 'unknown'),
                                        "job_description": details.get('description', dict()).get('text', 'unknown'),
                                        "job_posting_link": "https://www.linkedin.com/jobs/view/" + job_id,
                                        "job_id": job_id}
                        
                        all_jobs.append(select_info)

                    except Exception as e:
                        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                        print(f"Error processing job {job_id}: {str(e)}")
                        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                        continue

                end_time = time.time()
                print(f"Time taken for search: {end_time - start_time} seconds")\

        seen_jobs_df = pd.DataFrame(seen_jobs, columns=["job_id"])
        seen_jobs_df.to_csv("./db/seen_jobs.csv", index=False)

        print("Finished searching for jobs on LinkedIn")
        print(len(all_jobs))
        return all_jobs 
    


