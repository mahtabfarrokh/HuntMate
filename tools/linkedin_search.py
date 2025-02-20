
from pydantic import BaseModel, Field
from linkedin_api import Linkedin
from typing import List, Literal
import pandas as pd
import configparser
import os

# Shema for filling the job search parameters
class JobSearchParams(BaseModel):
    job_keywords: List[str] = Field(description="Keywords for the job search")
    location_name: List[str] = Field(description="Location names for the job search")
    remote: List[Literal["On-site", "Remote", "Hybrid"]] = Field(description="Remote job options")
    experience: List[Literal["internship", "entry-level", "associate", "mid-senior-level", "director", "executive"]] = Field(description="Experience levels")
    job_type: List[Literal["full-time", "contract", "part-time", "temporary", "internship", "volunteer", "other"]] = Field(description="Types of jobs")
    limit: int = Field(description="Limit on the number of jobs to return")


# Tool for searching jobs on LinkedIn using the LinkedIn API
class LinkedinSearchTool:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('./api.cfg')
        self.api = Linkedin(config['linkedin']['username'], config['linkedin']['password'])
        self.map_remote={"on-site": "1", "remote": "2", "hybrid": "3"}
        self.map_experience={"internship": "1", "entry-level": "2", "associate": "3", "mid-senior-level" : "4", "director": "5", "6": "executive"}

    def get_company_name(self, details: dict) -> str:
        """ Get company name from company id """
        for keys in details["companyDetails"].keys():
            for k in details["companyDetails"][keys].keys():
                for m in details["companyDetails"][keys][k].keys():
                    if m == "name":
                        return details["companyDetails"][keys][k][m]
        return "Unknown"
    
    def job_search(self, search_params: JobSearchParams) -> List[dict]:
        """ Search for jobs on LinkedIn """
        all_jobs = []
        if "db" not in os.listdir():
            os.mkdir("db")
        if "seen_jobs.csv" not in os.listdir("./db"):
            seen_jobs = set()
        else:   
            seen_jobs = set(pd.read_csv("./db/seen_jobs.csv")["job_id"])
        for job in search_params.job_keywords[:5]: 
            for location in search_params.location_name[:5]:
                input_search = {
                    "keywords": job,
                    "location": location,
                    "limit": search_params.limit,
                    "remote": [self.map_remote[remote.lower()] for remote in search_params.remote],
                    "experience": [self.map_experience[experience.lower()] for experience in search_params.experience],
                    "job_type": [job_type[0] for job_type in search_params.job_type]
                }
                jobs = self.api.search_jobs(**input_search)
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
                                        "job_description": details.get('description', 'unknown').get('text', 'unknown'),
                                        "job_posting_link": "https://www.linkedin.com/jobs/view/" + job_id,
                                        "job_id": job_id}
                        all_jobs.append(select_info)

                    except Exception as e:
                        print(f"Error processing job {job_id}: {str(e)}")
                        continue

        seen_jobs_df = pd.DataFrame(seen_jobs, columns=["job_id"])
        seen_jobs_df.to_csv("./db/seen_jobs.csv", index=False)
        return all_jobs 
    