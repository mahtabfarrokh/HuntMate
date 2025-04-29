
class AppConfig: 

    # LinekedIn parameters: 
    MAX_SEARCH_ITEMS = 5            # Limit for number of job keywords and locations to loop over.
    
    EXTRA_JOBS_TO_SEARCH_LOWER = 5  # Extra jobs to add to the search so that you can find the best match
    EXTRA_JOBS_TO_SEARCH_UPPER = 20 # Extra jobs to add to the search so that you can find the best match


    LAST_MONTH_TIME = 24*60*60*30   # Jobs listed in the last 30 days


    # UI app parameters: 
    MAX_JOBS = 50                   # Upper range for limit
    MIN_JOBS = 1                    # Lower range for limit
    DEFAULT_LIMIT = 10              # Default limit for number of jobs to return
    COLUMN_SETUP = [1, 0.5,  5]     # Column setup for the UI app

    # HuntMate core parameters:
    JOB_MATCH_BATCH_SIZE = 64        # Number of jobs to process in parallel in the LLM Call


