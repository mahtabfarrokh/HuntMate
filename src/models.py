from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from typing import List, Literal
from enum import Enum

from src.settings import AppConfig


# For chain of thought
class Step(BaseModel):
    explanation: str
    output: str

# Enum for remote job types
class WorkMode(Enum):
    ON_SITE = "1"
    REMOTE = "2"
    HYBRID = "3"


# Enum for experience levels
class ExperienceLevel(Enum):
    INTERNSHIP = "1"
    ENTRY_LEVEL = "2"
    ASSOCIATE = "3"
    MID_SENIOR_LEVEL = "4"
    DIRECTOR = "5"
    EXECUTIVE = "6"

class Location(BaseModel):
    city: str = Field(description="City name")
    country: str = Field(description="Country name")

# Shema for filling the job search parameters
class JobSearchParams(BaseModel):
    steps: list[Step]
    job_keywords: List[str] = Field(description="Main essential keywords for the job search")
    locations: List[Location] = Field(description="Locations for the job search.")
    work_mode: List[WorkMode] = Field(description="Work mode options are on-site, remote, or hybrid")
    experience: List[ExperienceLevel] = Field(description="Experience levels")
    job_type: List[Literal["Full-time", "Contract", "Part-time", "Temporary", "Internship", "Volunteer", "Other"]] = Field(description="Types of jobs")
    limit: int = Field(description="Limit on the number of jobs to return")
    extra_preferences: str = Field(description="Extra preferences for the job search.")

# Schema for structured output to use as routing logic
class Route(BaseModel):
    route: Literal["craft_email", "craft_coverletter", "job_search", "unsupported_task", "extract_and_memorize"] = Field(
        None, description="The next step in the routing process"
    )
    information_to_memorize: str = Field(
        None, description="Any critical new information that should be memorized in the chat history."
    )

# State schema for the LLM Agent
class State(TypedDict):
    user_input: str
    route_decision: str
    job_search_params: JobSearchParams
    final_response: str
    skip_router: bool
    filled_job_form: bool 
    selected_websites: List[str]
    information_to_memorize: List[str]


# State schema for the LLM Agent
class JobMatch(BaseModel):
    match_score: int = Field(description="A score between 1 to 5 of how well the job matches the user's preferences.")
    reasonning: str = Field(description="One sentence reasonning for the choice of match_score.")
    job_summary: str = Field(description="Summary of the job in 50 words.")


class JobUserMention(BaseModel): 
    steps: list[Step]
    description: str = Field(description="Description of the job.")


