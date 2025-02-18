
from linkedin_api import Linkedin
import configparser
from pydantic import BaseModel, Field
from typing import List, Literal


class JobSearchParams(BaseModel):
    job_keywords: str = Field(description="Keywords for the job search")
    location_name: str = Field(description="Location name for the job search")
    remote: List[Literal["On-site", "Remote", "Hybrid"]] = Field(description="Remote job options")
    experience: List[Literal["internship", "entry-level", "associate", "mid-senior-level", "director", "executive"]] = Field(description="Experience levels")
    job_type: List[Literal["full-time", "contract", "part-time", "temporary", "internship", "volunteer", "other"]] = Field(description="Types of jobs")
    limit: int = Field(description="Limit on the number of jobs to return")


class LinkedinSearchTool:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('./api.cfg')
        self.api = Linkedin(config['linkedin']['username'], config['linkedin']['password'], refresh_cookies=True)
        


    def job_search(self, job_keywords: str, location: str, remote: bool, experience: str, job_type: str, limit: int):
        """ Search for jobs on LinkedIn """
        
        search_params = JobSearchParams(
            keywords=job_keywords,
            location_name=location,
            remote=["2"] if remote else [],
            experience=[experience],
            job_type=[job_type],
            limit=limit
        ).dict()
        jobs = self.api.search_jobs(**search_params)
        for job in jobs:
            try:
                # Get detailed job information
                print("-----------------")
                job_id = job["entityUrn"].split(":")[-1]
                details = self.api.get_job(job_id)
                print(details)

            except Exception as e:
                print(f"Error processing job {job_id}: {str(e)}")
                continue
        return jobs 
    