from typing import get_args
import streamlit as st
import argparse
import logging
import os

from huntmate_core import HuntMate
from settings import AppConfig
from models import WorkMode, ExperienceLevel, JobSearchParams


st.set_page_config(layout="wide")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "show_job_form" not in st.session_state:
    st.session_state.show_job_form = False

if "form_prefill" not in st.session_state:
    st.session_state.form_prefill = None
    
if "chatbot" not in st.session_state:
    logging.basicConfig(
        filename="huntmate.log",  # or None to only log to console
        level=logging.INFO,       # change to logging.DEBUG for more detail
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if not os.path.exists("./api.cfg"):
        st.error("Please create an `api.cfg` file with your keys, for an example see `api.cfg.example`.")
        st.stop()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default="gpt-4o-mini", help="The name of the model to use.")
    args = parser.parse_args()
    st.session_state.chatbot = HuntMate(model_name=args.model_name)

chatbot = st.session_state.chatbot

logo_col, spacer_col, main_col = st.columns(AppConfig.COLUMN_SETUP)

with logo_col:
    st.image("images/logo.png", use_container_width=True)

with spacer_col:
    # empty spacer, no content
    pass

with main_col:
    st.title("Welcome to HuntMate!")
    st.write("I am your companion in job hunting! :)")
    st.write("You can start by saying 'Find me a job' or ask me anything about job search.")

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Display the job form if show_job_form is True
if st.session_state.show_job_form:
    st.subheader("Job Search Preferences")
    with st.form(key="job_form"):
        # Define form fields based on your questions
        limit = st.number_input(
            "Please provide the number of jobs I should be searching through:", 
            min_value=AppConfig.MIN_JOBS, 
            max_value=AppConfig.MAX_JOBS, 
            value=getattr(st.session_state.form_prefill, "limit", AppConfig.DEFAULT_LIMIT),
        )
        
        remote = st.multiselect(
            "Please provide your preference for work mode:", 
            options=[e.name.replace("_", "").capitalize() for e in WorkMode],
            default=[i.name.lower().replace("_", "").capitalize() for i in getattr(st.session_state.form_prefill, "work_mode", [])]
        )

        experience = st.multiselect(
            "Please provide your preference for experience level:", 
            options=[e.name.replace("_", " ").capitalize() for e in ExperienceLevel],
            default=[i.name.lower().replace("_", " ").capitalize() for i in getattr(st.session_state.form_prefill, "experience", [])]
        )
        
        job_type = st.multiselect(
            "Please provide your preference for job type:", 
            options=list(get_args(JobSearchParams.__annotations__['job_type'])[0].__args__),
            default=[i for i in getattr(st.session_state.form_prefill, "job_type", [])]
        )
        locations = st.text_input(
            "Please provide your preference for location:", 
            value=", ".join(getattr(st.session_state.form_prefill, "locations", []))
        )
        
        job_keywords = st.text_input("Please provide your preference for job keywords:", 
                                    value=", ".join(getattr(st.session_state.form_prefill, "job_keywords", [])))
        
        other_preferences = st.text_area("Please describe any other preferences you have for the job search:",
                                        value= getattr(st.session_state.form_prefill, "extra_preferences", ""))
        
        submit_button = st.form_submit_button("Submit")
        

        if submit_button:
            # Compile all inputs into an explanation string
            explanation = ""
            explanation += f"AI: Please provide the number of jobs I should be searching through: {limit}\n"
            explanation += f"AI: Please provide your preference for work mode: {remote}\n"
            explanation += f"AI: Please provide your preference for experience: {experience}\n"
            explanation += f"AI: Please provide your preference for job type: {job_type}\n"
            explanation += f"AI: Please provide your preference for the location: {locations}\n"
            explanation += f"AI: Please provide your preference for job title keywords: {job_keywords}\n"
            explanation += "[Extra Preferences Tag]"
            explanation += f"AI: Please describe any other preferences you have for the job search: {other_preferences}\n"
            
            # Process the form with your function
            with st.spinner("Processing your job preferences, this will take a while, please be patient."):
                # Call your function with the explanation
                response = chatbot.run(explanation, skip_router=True, filled_job_form=True)
                
                # Display result in the chat
                with st.chat_message("assistant"):
                    st.markdown(response)
                
                # Add assistant message to chat history
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # Reset the form flag
                st.session_state.show_job_form = False
                st.rerun()

# Accept user input
if prompt := st.chat_input("Ask me anything"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Get response from HuntMate
    response = chatbot.run(prompt, skip_router=False, filled_job_form=False)

    if response == "show_form": 
        # Define the questions and fields
        st.session_state.show_job_form = True
        st.rerun()
    else:
        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})

