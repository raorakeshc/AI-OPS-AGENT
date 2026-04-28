import streamlit as st
import uuid
from agent import SupportAgent # Ensure your script is in src/agent.py

# Page Config
st.set_page_config(page_title="SkyBridge Logistics Support", page_icon="✈️", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background-image: linear-gradient(rgba(7, 12, 24, 0.78), rgba(7, 12, 24, 0.82)),
                          url('https://images.unsplash.com/photo-1578575437130-527eed3abbec?auto=format&fit=crop&w=1920&q=80');
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
    }

    .brand-card {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 16px;
        padding: 18px 22px;
        margin-bottom: 14px;
        backdrop-filter: blur(8px);
    }

    .brand-logo {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 42px;
        height: 42px;
        border-radius: 50%;
        background: linear-gradient(135deg, #00b4d8, #0077b6);
        color: white;
        font-weight: 700;
        margin-right: 10px;
        font-size: 18px;
    }

    .brand-title {
        color: #ffffff;
        font-size: 26px;
        font-weight: 700;
        margin: 0;
    }

    .brand-subtitle {
        color: #d7e3ff;
        margin-top: 4px;
        font-size: 14px;
    }

    .stChatMessage {
        background: rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.12);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(2, 8, 20, 0.95), rgba(8, 24, 48, 0.95));
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="brand-card">
        <div style="display:flex; align-items:center;">
            <div class="brand-logo">SB</div>
            <div>
                <p class="brand-title">SkyBridge Logistics</p>
                <p class="brand-subtitle">Airways & Logistics Support Assistant</p>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Initialize Agent and Thread ID in Session State
if "agent" not in st.session_state:
    st.session_state.agent = SupportAgent()
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for Feedback and Controls
with st.sidebar:
    st.markdown("### ✈️ SkyBridge Control Panel")
    st.caption("Manage conversation, feedback, and agent behavior")

    st.markdown("---")
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
if prompt := st.chat_input("Ask about orders, delivery, refunds, or escalations..."):
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
