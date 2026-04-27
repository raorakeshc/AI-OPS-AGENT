import streamlit as st
import uuid
from agent import SupportAgent # Ensure your script is in src/agent.py

# Page Config
st.set_page_config(page_title="AI Ops Support Agent", page_icon="🤖")
st.title("🤖 AI Ops Support Agent")
st.markdown("---")

# Initialize Agent and Thread ID in Session State
if "agent" not in st.session_state:
    st.session_state.agent = SupportAgent()
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for Feedback and Controls
with st.sidebar:
    st.header("Settings")
    if st.button("🗑️ Clear Chat Memory"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()
    
    st.markdown("---")
    st.header("Agent Training")
    feedback = st.text_input("Enter style feedback (e.g., 'Talk like a pirate')")
    if st.button("Submit Feedback"):
        if feedback:
            st.session_state.agent.feedback_manager.add_feedback(feedback)
            st.success(f"Feedback saved: {feedback}")

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("How can I help you with your order?"):
    # Add user message to UI
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate Agent Response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = st.session_state.agent.ask(prompt, thread_id=st.session_state.thread_id)
            st.markdown(response)
    
    # Save assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": response})