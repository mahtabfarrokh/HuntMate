
from my_linkedin_api import Linkedin
from typing import List, Dict, Any
import pandas as pd
import configparser
import logging
import time
import os


from src.models import JobSearchParams
from src.settings import AppConfig
import asyncio



logger = logging.getLogger(__name__)

# Tool for searching jobs on LinkedIn using the LinkedIn API
class LinkedinSearchTool:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('./api.cfg')
        self.api = Linkedin(config['linkedin']['username'], config['linkedin']['password'])

    def get_company_name(self, details: Dict[str, Any]) -> str:
        """ Get company name from company id """
        company_details = details.get("companyDetails", {})
        for key, value in company_details.items():
            company_name = value.get("companyName", "")
            if company_name:
                return company_name
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
            logger.error(f"Error fetching job {job_id}: {str(e)}")
            return ""
    

    def job_search(self, search_params: JobSearchParams) -> List[Dict[str, str]]:
        """ Search for jobs on LinkedIn """
        all_jobs = []
        if "db" not in os.listdir():
            os.mkdir("db")
        if "seen_jobs.csv" not in os.listdir("./db"):
            seen_jobs = set()
        else:   
            seen_jobs = set(pd.read_csv("./db/seen_jobs.csv")["job_id"])

        logging.info("Searching for jobs on LinkedIn")
        final_limit = search_params.limit
        for keyword in search_params.job_keywords[:AppConfig.MAX_SEARCH_ITEMS]: 
            for location in search_params.locations[:AppConfig.MAX_SEARCH_ITEMS]:
                input_search = {
                    "keywords": keyword,
                    "location_name": location,
                    "limit": final_limit,  
                    "remote": [remote.value for remote in search_params.work_mode],
                    "experience": [experience.value for experience in search_params.experience],
                    "job_type": [job_type[0].upper() for job_type in search_params.job_type],
                    "listed_at": AppConfig.LAST_MONTH_TIME,  # Jobs listed in the last 30 days
                }

                logger.info(f"Search parameters: {input_search}")
                start_time = time.time()
                try:
                    jobs = self.api.search_jobs(**input_search)
                except Exception as e:
                    logger.error(f"Error searching for jobs: {str(e)}")
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
                            logger.error(f"Error fetching job {job_id}: {str(e)}")
                            return None

                    return await asyncio.to_thread(blocking_call)

                async def process_jobs(jobs):
                    tasks = []
                    for job in jobs:
                        job_id = str(job["entityUrn"]).split(":")[-1]
                        if job_id in seen_jobs:
                            continue

                        seen_jobs.add(job_id)
                        tasks.append(fetch_job_details(job_id))

                    results = []
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
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
                                "job_id": job_id,
                                "site": "LinkedIn",
                            }
                            all_jobs.append(select_info)

                asyncio.run(process_jobs(jobs))

                end_time = time.time()
                logging.info(f"LinkedIn Time taken for search (end - start): {end_time - start_time} seconds")

        seen_jobs_df = pd.DataFrame(seen_jobs, columns=["job_id"])
        seen_jobs_df.to_csv("./db/seen_jobs.csv", index=False)

        logging.info("Finished searching for jobs on LinkedIn. Total jobs found: %s", len(all_jobs))
        return all_jobs 
    


# I prefer if the job is either in ML application in healthcare and examples are medical imaging, pathology images, cancer research and survival analysis. Or if a job is in Gen AI, and LLM or RAG related.