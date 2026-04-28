import streamlit as st
import uuid
import json
from pathlib import Path
from collections import Counter
from agent import SupportAgent # Ensure your script is in src/agent.py

# Page Config
st.set_page_config(page_title="UBA Logistics Support", page_icon="✈️", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background-image: linear-gradient(rgba(255, 245, 179, 0.78), rgba(255, 255, 255, 0.82)),
                          url('https://images.unsplash.com/photo-1578575437130-527eed3abbec?auto=format&fit=crop&w=1920&q=80');
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
    }

    .brand-card {
        background: rgba(255, 255, 255, 0.90);
        border: 1px solid rgba(255, 214, 10, 0.55);
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
        background: linear-gradient(135deg, #ffd60a, #ffb703);
        color: #1f2937;
        font-weight: 700;
        margin-right: 10px;
        font-size: 18px;
    }

    .brand-title {
        color: #1f2937;
        font-size: 26px;
        font-weight: 700;
        margin: 0;
    }

    .brand-subtitle {
        color: #374151;
        margin-top: 4px;
        font-size: 14px;
    }

    .stChatMessage {
        background: rgba(255, 255, 255, 0.88);
        border-radius: 12px;
        border: 1px solid rgba(255, 214, 10, 0.45);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(255, 248, 204, 0.98), rgba(255, 255, 255, 0.98));
    }
    </style>
    """,
    unsafe_allow_html=True
)


def render_brand_header():
    st.markdown(
        """
        <div class="brand-card">
            <div style="display:flex; align-items:center;">
                <div class="brand-logo">UBAL</div>
                <div>
                    <p class="brand-title">UBA Logistics</p>
                    <p class="brand-subtitle"> Logistics Support AI Assistant</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def load_orders_data():
    orders_path = Path(__file__).resolve().parent.parent / "data" / "orders.json"
    if not orders_path.exists():
        return {}
    try:
        with orders_path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def render_login_page():
    st.markdown("""
        <style>
        /* Center the login container */
        [data-testid="stVerticalBlock"] > div:has(div.login-card) {
            display: flex;
            justify-content: center;
            padding-top: 5rem;
        }
        
        .login-card {
            background: rgba(255, 255, 255, 1.0); /* Solid white for maximum brightness */
            padding: 3rem;
            border-radius: 24px;
            /* Stronger shadow with a hint of brand gold */
            box-shadow: 0 20px 40px rgba(0,0,0,0.2), 0 0 15px rgba(255, 214, 10, 0.3);
            border: 2px solid #ffd60a;
            text-align: center;
            transition: transform 0.3s ease;
        }
        
        /* Make input boxes cleaner */
        .stTextInput input {
            background-color: #f9fafb !important;
            border: 1px solid #e5e7eb !important;
            border-radius: 10px !important;
            padding: 12px !important;
        }

        .stTextInput label {
            font-weight: 700 !important;
            color: #111827 !important;
            font-size: 1rem !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Use slightly tighter columns to make the card feel sturdy
    _, col, _ = st.columns([1.2, 1.4, 1.2])

    with col:
        # Brand Branding inside the card - Elevated Look
        st.markdown("""
            <h1 style='text-align: center; color: #1f2937; margin-bottom: 0; font-weight: 800;'><span style="font-size: 24px;">✈️</span>UBA Logistics</h1>
            <p style='text-align: center; color: #4b5563; font-size: 1rem; margin-top: 5px;'>Secure Agent Gateway</p>
            <hr style='margin: 1.5rem 0; border-color: #f3f4f6;'>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter your ID")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            
            st.markdown("<div style='padding: 10px;'></div>", unsafe_allow_html=True)
            
            submitted = st.form_submit_button("Sign In to UBAL", use_container_width=True)

            if submitted:
                if username == "admin" and password == "admin123":
                    st.session_state.authenticated = True
                    st.session_state.current_page = "Dashboard"
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        
        st.markdown("""
            <p style='font-size: 0.85rem; color: #6b7280; margin-top: 1.5rem;'>
                Need help? <a href='mailto:it@ubalogistics.com' style='color: #d97706; font-weight: 600; text-decoration: none;'>Contact System Admin</a>
            </p>
        """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

def render_dashboard_page():
    render_brand_header()
    st.subheader("Operations Dashboard")

    orders = load_orders_data()
    if not orders:
        st.warning("No order data found.")
        return

    status_counts = Counter(orders.values())
    total_orders = len(orders)
    delivered_count = sum(1 for status in orders.values() if "Delivered" in status)
    transit_count = sum(1 for status in orders.values() if "Transit" in status or "Out for Delivery" in status)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Orders", total_orders)
    col2.metric("Delivered", delivered_count)
    col3.metric("In Transit/Out for Delivery", transit_count)

    chart_data = [
        {"status": status, "count": count}
        for status, count in sorted(status_counts.items(), key=lambda item: item[1], reverse=True)
    ]

    st.markdown("### Orders by Status (Pie Chart)")
    try:
        import altair as alt

        pie_chart = (
            alt.Chart(alt.Data(values=chart_data))
            .mark_arc(innerRadius=50)
            .encode(
                theta=alt.Theta(field="count", type="quantitative"),
                color=alt.Color(field="status", type="nominal", legend=alt.Legend(title="Status")),
                tooltip=["status", "count"],
            )
            .properties(height=450)
        )
        st.altair_chart(pie_chart, use_container_width=True)
    except Exception:
        st.info("Pie chart library unavailable. Showing status counts table instead.")
        st.table(chart_data)

    st.markdown("### Order List")
    selected_status = st.selectbox(
        "Filter by status",
        options=["All"] + sorted(status_counts.keys()),
        index=0,
    )

    rows = []
    for order_id, status in sorted(orders.items(), key=lambda item: int(item[0]) if item[0].isdigit() else item[0]):
        if selected_status == "All" or status == selected_status:
            rows.append({"order_id": order_id, "status": status})

    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No orders match selected status.")

def render_footer():
    st.markdown(
        """
        <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: rgba(255, 255, 255, 0.9);
            color: #1f2937;
            text-align: center;
            padding: 10px;
            font-size: 12px;
            border-top: 1px solid rgba(255, 214, 10, 0.5);
            backdrop-filter: blur(5px);
            z-index: 999;
        }
        </style>
        <div class="footer">
            <p><b>© 2026 UBA Logistics (UBAL)</b> | Global Operations Headquarters | 
            Support: support@ubalogistics.com | Terms of Service | Privacy Policy</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_agent_page():
    render_brand_header()
    st.subheader("Support Agent")

    if "agent" not in st.session_state:
        st.session_state.agent = SupportAgent()
        st.session_state.thread_id = str(uuid.uuid4())

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.markdown("### ✈️ UBA Control Panel")
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

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask about orders, delivery, refunds, or escalations..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.agent.ask(prompt, thread_id=st.session_state.thread_id)
                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"


if st.session_state.authenticated:
    with st.sidebar:
        st.markdown("### Navigation")
        selected_page = st.radio(
            "Go to",
            ["Dashboard", "Agent"],
            index=0 if st.session_state.current_page == "Dashboard" else 1,
        )
        st.session_state.current_page = selected_page

        st.markdown("---")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.current_page = "Dashboard"
            st.rerun()

    if st.session_state.current_page == "Dashboard":
        render_dashboard_page()
    else:
        render_agent_page()
else:
    render_login_page()

# CALL FOOTER HERE
render_footer()

