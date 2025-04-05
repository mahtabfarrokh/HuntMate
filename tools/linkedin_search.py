
from linkedin_api import Linkedin
from typing import List
import pandas as pd
import configparser
import time
import os


from models import JobSearchParams
import asyncio


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
    
    def get_job_info(self, job_id: str) -> str:
        """ Get job information from job id """
        try:
            job_details = self.api.get_job(job_id)
            JD = job_details.get('description', dict()).get('text', 'unknown')
            if JD == 'unknown':
                JD = str(job_details)
            return JD
        except Exception as e:
            print(f"Error fetching job {job_id}: {str(e)}")
            return ""
        
    def job_search(self, search_params: JobSearchParams) -> List[dict]:
        """ Search for jobs on LinkedIn """
        all_jobs = []
        if "db" not in os.listdir():
            os.mkdir("db")
        if "seen_jobs.csv" not in os.listdir("./db"):
            seen_jobs = set()
        else:   
            seen_jobs = set(pd.read_csv("./db/seen_jobs.csv")["job_id"])

        print("Searching for jobs on LinkedIn")
        final_limit = search_params.limit + 5
        if len(search_params.job_keywords) == 1 and len(search_params.locations) == 1:
            final_limit = search_params.limit + 20 # Add extra jobs to account for duplicates or wrong matches

        for keyword in search_params.job_keywords[:MAX_SEARCH_ITEMS]: 
            for location in search_params.locations[:MAX_SEARCH_ITEMS]:
                input_search = {
                    "keywords": keyword,
                    "location": location,
                    "limit": final_limit,  
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
                
                async def fetch_job_details(job_id):
                    def blocking_call():
                        try:
                            details = self.api.get_job(job_id)
                            return {
                                "job_id": job_id,
                                "details": details
                            }
                        except Exception as e:
                            print(f"Error fetching job {job_id}: {str(e)}")
                            return None

                    return await asyncio.to_thread(blocking_call)

                async def process_jobs(jobs):
                    tasks = []
                    for job in jobs:
                        job_id = job["entityUrn"].split(":")[-1]
                        if job_id in seen_jobs:
                            continue
                        seen_jobs.add(job_id)
                        tasks.append(fetch_job_details(job_id))

                    results = []
                    batch_size = 8
                    for i in range(0, len(tasks), batch_size):
                        batch = tasks[i:i + batch_size]
                        batch_results = await asyncio.gather(*batch, return_exceptions=True)
                        results.extend(batch_results)
                    
                    for result in results:
                        if result and isinstance(result, dict):
                            details = result["details"]
                            job_id = result["job_id"]
                            select_info = {
                                "title": details.get('title', 'unknown'),
                                "company": self.get_company_name(details),
                                "location": details.get('formattedLocation', 'unknown'),
                                "remote_allowed": details.get('workRemoteAllowed', 'unknown'),
                                "job_description": details.get('description', dict()).get('text', 'unknown'),
                                "job_posting_link": "https://www.linkedin.com/jobs/view/" + job_id,
                                "job_id": job_id
                            }
                            all_jobs.append(select_info)

                asyncio.run(process_jobs(jobs))

                end_time = time.time()
                print(f"Time taken for search: {end_time - start_time} seconds")\

        seen_jobs_df = pd.DataFrame(seen_jobs, columns=["job_id"])
        seen_jobs_df.to_csv("./db/seen_jobs.csv", index=False)

        print("Finished searching for jobs on LinkedIn")
        print(len(all_jobs))
        return all_jobs 
    


