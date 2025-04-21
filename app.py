from typing import get_args
import streamlit as st
import argparse
import logging
import os

from huntmate_core import HuntMate
from settings import AppConfig
from models import WorkMode, ExperienceLevel, JobSearchParams


st.set_page_config(layout="wide")


# Inject external styles
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# Helper function for tight labels
def tight_label(text: str):
    st.markdown(f'<div class="tight-label">{text}</div>', unsafe_allow_html=True)


class CheckBoxArray:
    def __init__(self, name: str, anchor, checkboxes: list[str], max_select: int, num_cols=1):
        self.name = name
        self.anchor = anchor
        cols = self.anchor.columns(num_cols)

        for i, cb in enumerate(checkboxes):
            key = f"{self.name}_{i}"
            if key not in st.session_state:
                st.session_state[key] = True  

        cb_values = [st.session_state[f"{self.name}_{i}"] for i in range(len(checkboxes))]
        disable = sum(cb_values) == max_select

        for i, cb in enumerate(checkboxes):
            key = f"{self.name}_{i}"
            cols[i % num_cols].checkbox(
                label=cb,
                disabled=(not st.session_state[key] and disable),
                key=key
            )

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "show_job_form" not in st.session_state:
    st.session_state.show_job_form = False

if "form_prefill" not in st.session_state:
    st.session_state.form_prefill = None

if "chatbot" not in st.session_state:
    logging.basicConfig(
        filename="huntmate.log",
        level=logging.INFO,
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
    pass  # spacer column

with main_col:
    st.title("Welcome to HuntMate!")
    st.write("I am your companion in job hunting! :)")
    st.write("You can start by saying 'Find me a job' or ask me anything about job search.")

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Show form if triggered
if st.session_state.show_job_form:
    with st.form(key="job_form", clear_on_submit=False):
        st.subheader("Job Search Preference Form")

        st.write("Please select the job boards you want to search on:")
        websites = ["Indeed", "LinkedIn", "Google", "Glassdoor"]
        cb_array = CheckBoxArray("cb_jobs", st, checkboxes=websites, num_cols=6, max_select=len(websites))

        tight_label("Please provide the number of jobs I should be searching through:")
        limit = st.number_input(
            label="limit", label_visibility="hidden",
            min_value=AppConfig.MIN_JOBS,
            max_value=AppConfig.MAX_JOBS,
            value=getattr(st.session_state.form_prefill, "limit", AppConfig.DEFAULT_LIMIT),
        )

        tight_label("Please provide your preference for work mode:")
        remote = st.multiselect(
            label="work_mode", label_visibility="hidden",
            options=[e.name.replace("_", "").capitalize() for e in WorkMode],
            default=[i.name.lower().replace("_", "").capitalize() for i in getattr(st.session_state.form_prefill, "work_mode", [])],
            help="Select your preferred work mode (e.g., Remote, Onsite, Hybrid).",
        )

        tight_label("Please provide your preference for experience level:")
        experience = st.multiselect(
            label="experience_level", label_visibility="hidden",
            options=[e.name.replace("_", " ").capitalize() for e in ExperienceLevel],
            default=[i.name.lower().replace("_", " ").capitalize() for i in getattr(st.session_state.form_prefill, "experience", [])]
        )

        tight_label("Please provide your preference for job type:")
        job_type = st.multiselect(
            label="job_type", label_visibility="hidden",
            options=list(get_args(JobSearchParams.__annotations__['job_type'])[0].__args__),
            default=[i for i in getattr(st.session_state.form_prefill, "job_type", [])]
        )

        tight_label("Please provide your preference for location:")
        locations = st.text_input(
            label="location", label_visibility="hidden",
            value=", ".join(getattr(st.session_state.form_prefill, "locations", []))
        )

        tight_label("Please provide your preference for job keywords:")
        job_keywords = st.text_input(
            label="job_keywords_input", label_visibility="hidden",
            value=", ".join(getattr(st.session_state.form_prefill, "job_keywords", []))
        )

        tight_label("Please describe any other preferences you have for the job search:")
        other_preferences = st.text_area(
            label="job_extra_input", label_visibility="hidden",
            value=getattr(st.session_state.form_prefill, "extra_preferences", "")
        )

        st.markdown('<div class="tight-label"> </div>', unsafe_allow_html=True)
        submit_button = st.form_submit_button("Submit")
        st.markdown('<div class="tight-label"> </div>', unsafe_allow_html=True)

        if submit_button:
            explanation = ""
            explanation += f"AI: Please provide the number of jobs I should be searching through: {limit}\n"
            explanation += f"AI: Please provide your preference for work mode: {remote}\n"
            explanation += f"AI: Please provide your preference for experience: {experience}\n"
            explanation += f"AI: Please provide your preference for job type: {job_type}\n"
            explanation += f"AI: Please provide your preference for the location: {locations}\n"
            explanation += f"AI: Please provide your preference for job title keywords: {job_keywords}\n"
            explanation += "[Extra Preferences Tag]"
            explanation += f"AI: Please describe any other preferences you have for the job search: {other_preferences}\n"


            selected_websites = [
                websites[i] for i in range(len(websites))
                if st.session_state.get(f"cb_jobs_{i}", False)
            ]

            with st.spinner("Processing your job preferences, this will take a while, please be patient."):
                response = chatbot.run(explanation, skip_router=True, filled_job_form=True, websites=selected_websites)
                with st.chat_message("assistant"):
                    st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.session_state.show_job_form = False
                st.rerun()

# Chat input
if prompt := st.chat_input("Ask me anything"):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    response = chatbot.run(prompt, skip_router=False, filled_job_form=False)

    if response == "show_form":
        st.session_state.show_job_form = True
        st.rerun()
    else:
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
