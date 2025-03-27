import streamlit as st
import argparse
import os

from huntmate_core import HuntMate


if not os.path.exists("./api.cfg"):
    st.error("Please create an `api.cfg` file with your keys, for an example see `api.cfg.example`.")
    st.stop()

parser = argparse.ArgumentParser()
parser.add_argument("--model_name", type=str, default="gpt-4o-mini", help="The name of the model to use.")
args = parser.parse_args()

chatbot = HuntMate(model_name=args.model_name)

st.title("Welcome to HuntMate!")
st.write("I am your companion in job hunting! :)")
st.write("You can start by saying 'Find me a job' or ask me anything about job search.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "show_job_form" not in st.session_state:
    st.session_state.show_job_form = False

if "form_prefill" not in st.session_state:
    st.session_state.form_prefill = None

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
            min_value=1, 
            max_value=50, 
            value=getattr(st.session_state.form_prefill, "limit", 10)
        )
        
        remote = st.multiselect(
            "Please provide your preference for work mode:", 
            options=["On-site", "Remote", "Hybrid"]
        )
        
        experience = st.multiselect(
            "Please provide your preference for experience:", 
            options=["internship", "entry-level", "associate", "mid-senior-level", "director", "executive"]
        )
        
        job_type = st.multiselect(
            "Please provide your preference for job type:", 
            options=["full-time", "contract", "part-time", "temporary", "internship", "volunteer", "other"]
        )
        locations = st.text_input(
            "Please provide your preference for location:", 
            value=", ".join(getattr(st.session_state.form_prefill, "locations", []))
        )
        
        job_keywords = st.text_input("Please provide your preference for job keywords:", 
                                     value=", ".join(getattr(st.session_state.form_prefill, "job_keywords", [])))
        
        other_preferences = st.text_area("Please describe any other preferences you have for the job search:")
        
        submit_button = st.form_submit_button("Submit")
        

        
        if submit_button:
            # Compile all inputs into an explanation string
            explanation = ""
            explanation += f"AI: Please provide the number of jobs I should be searching through: {limit}\n"
            explanation += f"AI: Please provide your preference for work mode: {remote}\n"
            explanation += f"AI: Please provide your preference for experience: {experience}\n"
            explanation += f"AI: Please provide your preference for job type: {job_type}\n"
            explanation += f"AI: Please provide your preference for location name: {locations}\n"
            explanation += f"AI: Please provide your preference for job keywords: {job_keywords}\n"
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
    response = chatbot.run(prompt, skip_router=True, filled_job_form=False)

    if response == "show_form": 
        # Define the questions and fields
        st.session_state.show_job_form = True
        st.rerun()
    else:
        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})

