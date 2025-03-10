from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException
from msedge.selenium_tools import Edge, EdgeOptions
from typing import List

from tools.linkedin_search import JobSearchParams


class IndeedSearchTool:
    def __init__(self):
        pass


    def get_url(self, position, location):
        """Generate url from position and location"""
        template = 'https://www.indeed.com/jobs?q={}&l={}'
        position = position.replace(' ', '+')
        location = location.replace(' ', '+')
        url = template.format(position, location)
        return url


    def job_search(self, search_params: JobSearchParams) -> List[dict]:
        """ Search for jobs on Indeed """
        all_jobs = []
        for job in search_params.job_keywords[:5]: 
            for location in search_params.location_name[:5]:
                url = self.get_url(job, location)
                options = EdgeOptions()
                options.use_chromium = True
                driver = Edge(options=options)
                driver.get(url)
                jobs = driver.find_elements_by_class_name('jobsearch-SerpJobCard')
                for job in jobs:
                    try:
                        title = job.find_element_by_class_name('title').text
                        company = job.find_element_by_class_name('company').text
                        location = job.find_element_by_class_name('location').text
                        job_id = job.get_attribute('data-jk')
                        job_link = f'https://www.indeed.com/viewjob?jk={job_id}'
                        select_info = {"title": title,
                                        "company": company,
                                        "location": location,
                                        "remote_allowed": "unknown",
                                        "job_description": "unknown",
                                        "job_posting_link": job_link,
                                        "job_id": job_id}
                        all_jobs.append(select_info)
                        print("-----------------")
                        print(select_info)
                    except (NoSuchElementException, ElementNotInteractableException) as e:
                        print(f"Error processing job {job_id}: {str(e)}")
                        continue
                driver.quit()




