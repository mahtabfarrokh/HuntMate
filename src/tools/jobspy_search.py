from jobspy import scrape_jobs
from typing import List, Dict
import pandas as pd
import Levenshtein
import logging
import time
import os


from src.models import JobSearchParams
from src.settings import AppConfig


# The default user agent is blocked by glassdoor, so we need to change it
from jobspy.glassdoor.constant import headers
headers["user-agent"] = AppConfig.GLASSDOOR_HEADER_UPDATE

from jobspy.linkedin.constant import headers
headers["user-agent"] = AppConfig.GLASSDOOR_HEADER_UPDATE


logger = logging.getLogger(__name__)

class JobSpySearchTool:
    def __init__(self):
        pass
    
    def remove_duplicate_jobs(self, all_jobs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """ Remove duplicate jobs based on company and title edit distance """

        def is_similar(str1: str, str2: str, threshold: float = 0.5) -> bool:
            """Check if two strings are similar based on a threshold using Levenshtein ratio."""
            if type(str1) != str or type(str2) != str:
                return True
            return Levenshtein.ratio(str1.lower(), str2.lower()) >= threshold

        unique_jobs = []
        for i, job in enumerate(all_jobs):
            duplicate_found = False
            for unique_job in unique_jobs:
                if is_similar(job["company"], unique_job["company"]) and is_similar(job["title"], unique_job["title"]):
                    duplicate_found = True
                    break
            if not duplicate_found:
                unique_jobs.append(job)

        return unique_jobs

    def check_location_similarity(self, location1: str, location2: str) -> bool:
        """ Check for the similary between the job's location and the user's location """
        if type(location1) != str or type(location2) != str:
            return False
        if location2.lower() in location1.lower():
            return True
        if location1.lower() in location2.lower():
            return True
        location1 = location1.lower()
        location2 = location2.lower()
        return Levenshtein.ratio(location1, location2) > 0.1
    
    def fix_website_name(self, website: str, url: str, website_selected: List[str]) -> str:
        """ Fix the website name if it is google based on the url """
        
        if website == "google":
            for website_selected in website_selected:
                if website_selected in url:
                    return website_selected
        return website

    def job_search(self, search_params: JobSearchParams, websites: List[str]) -> List[Dict[str, str]]:
        """ Search for jobs using jobspy """
        if websites is None:
            return []  
        websites = [w.lower() for w in websites]
        final_limit = search_params.limit + AppConfig.EXTRA_JOBS_TO_SEARCH_LOWER
        if len(search_params.job_keywords) == 1 and len(search_params.locations) == 1:
            final_limit = search_params.limit + AppConfig.EXTRA_JOBS_TO_SEARCH_UPPER # Add extra jobs to account for duplicates or wrong matches

    
        if "seen_jobs.csv" not in os.listdir("./db"):
            seen_jobs = set()
        else:   
            seen_jobs = set(pd.read_csv("./db/seen_jobs.csv")["job_id"])

        all_jobs = []
        search_websites = websites
        if "linkedin" in websites:
            search_websites.remove("linkedin")
        for keyword in search_params.job_keywords[:AppConfig.MAX_SEARCH_ITEMS]: 
            for location in search_params.locations[:AppConfig.MAX_SEARCH_ITEMS]:
                start_time = time.time()
                google_search_str = ""
                search_term_str = '"' + keyword + '"'
                if "google" in websites:
                    google_search_str = search_term_str + ' in ' + location.city
                try:
                    jobs = scrape_jobs(
                        site_name=search_websites,
                        search_term= search_term_str,
                        location=location.city,
                        google_search_term=google_search_str,
                        results_wanted=final_limit,
                        hours_old=AppConfig.LAST_MONTH_TIME,
                        country_indeed=location.country,
                    )
                except Exception as e:
                    logging.error(f"Error searching for jobs: {str(e)}")
                    continue
                print(">>>", len(jobs))
                for i in range(len(jobs)):
                    if jobs["id"][i] in seen_jobs:
                            continue
                    if not self.check_location_similarity(str(jobs["location"][i]), location.city):
                        continue
                    seen_jobs.add(jobs["id"][i])
                
                    all_jobs.append({
                        "title": jobs["title"][i],
                        "company": jobs["company"][i],
                        "location": jobs["location"][i],
                        "remote_allowed": jobs["is_remote"][i],
                        "job_description": jobs["description"][i] if jobs["description"][i] else "No description available.",
                        "job_posting_link": jobs["job_url"][i],
                        "job_id": jobs["id"][i],
                        "site": self.fix_website_name(jobs["site"][i], jobs["job_url"][i], websites),
                    })
                end_time = time.time()
                logging.info(f"JOBSPY (end - start): {end_time - start_time} seconds")

        seen_jobs_df = pd.DataFrame(seen_jobs, columns=["job_id"])
        seen_jobs_df.to_csv("./db/seen_jobs.csv", index=False)
        if len(websites) == 1:
            return all_jobs
        
        return self.remove_duplicate_jobs(all_jobs)