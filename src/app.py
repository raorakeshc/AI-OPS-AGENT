import streamlit as st
import uuid
import json
import base64
from pathlib import Path
from collections import Counter
from agent import SupportAgent # Ensure your script is in src/agent.py

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Page Config
st.set_page_config(page_title="UBA Logistics Support", page_icon="✈️", layout="wide")

# Background Image Loading
assets_path = Path(__file__).resolve().parent / "assets" / "login_bg.png"
bg_base64 = ""
if assets_path.exists():
    bg_base64 = get_base64_of_bin_file(str(assets_path))

st.markdown(f"""
    <style>
    .stApp {{
        background-image: linear-gradient(rgba(255, 255, 255, 0.85), rgba(255, 255, 255, 0.85)), url("data:image/png;base64,{bg_base64}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    .brand-card {{
        background: linear-gradient(135deg, rgba(3, 105, 161, 0.9), rgba(2, 132, 199, 0.7));
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 24px;
        padding: 20px 28px;
        margin-bottom: 25px;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
    }}

    .brand-logo {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 42px;
        height: 42px;
        border-radius: 50%;
        background: linear-gradient(135deg, #1e293b, #0f172a);
        color: #ffd60a;
        font-weight: 700;
        margin-right: 12px;
        font-size: 18px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }}

    .brand-title {{
        color: #ffd60a;
        font-size: 26px;
        font-weight: 700;
        margin: 0;
    }}

    .brand-subtitle {{
        color: rgba(255, 255, 255, 0.8);
        margin-top: 2px;
        font-size: 14px;
    }}

    /* Dashboard Glassmorphism Metrics */
    [data-testid="stMetric"] {{
        background: rgba(255, 255, 255, 0.75);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 214, 10, 0.4);
        border-radius: 20px;
        padding: 20px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
        transition: transform 0.3s ease;
    }}

    [data-testid="stMetric"]:hover {{
        transform: translateY(-5px);
        box-shadow: 0 12px 40px rgba(255, 214, 10, 0.2);
    }}

    [data-testid="stMetricValue"] {{
        color: #0369a1 !important;
    }}

    [data-testid="stMetricLabel"] {{
        color: #475569 !important;
    }}

    .stDataFrame, .stTable {{
        background: rgba(255, 255, 255, 0.5) !important;
        backdrop-filter: blur(10px) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(255, 214, 10, 0.2) !important;
        padding: 10px !important;
    }}

    .stChatMessage {{
        background: rgba(255, 255, 255, 0.92);
        backdrop-filter: blur(5px);
        border-radius: 16px;
        border: 1px solid rgba(255, 214, 10, 0.3);
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
    }}

    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, rgba(255, 248, 204, 0.98), rgba(255, 255, 255, 0.98));
    }}
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
    st.markdown(f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(0, 0, 0, 0.65), rgba(0, 0, 0, 0.65)), url("data:image/png;base64,{bg_base64}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .login-wrapper {{
            display: flex;
            justify-content: center;
            align-items: flex-start;
            min-height: auto;
            padding-top: 0.5rem; /* Minimal space from top */
        }}
        
        .login-card {{
            background: rgba(0, 0, 0, 0.3); /* Dark glass for better contrast */
            backdrop-filter: blur(20px) saturate(150%);
            -webkit-backdrop-filter: blur(20px) saturate(150%);
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 1.5rem 2rem; /* Reduced vertical padding, kept horizontal */
            width: 100%;
            max-width: 650px; /* Further increased width */
            box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.6);
            animation: slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        
        @keyframes slideUp {{
            from {{ opacity: 0; transform: translateY(30px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .login-header {{
            text-align: center;
            margin-bottom: 0.5rem; /* Reduced margin to push inputs up */
        }}
        
        .login-logo {{
            font-size: 1rem; /* Even smaller */
            margin-bottom: 0.1rem;
        }}
        
        .login-title {{
            color: #ffd60a; /* Brand Yellow */
            font-size: 1.25rem; /* Smaller title */
            font-weight: 800;
            margin: 0;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3); /* Improved readability on glass */
        }}
        
        .login-subtitle {{
            color: rgba(255, 255, 255, 0.6);
            font-size: 0.75rem;
            margin-top: 0.05rem;
        }}

        /* Compact form adjustments */
        [data-testid="stForm"] {{
            border: none !important;
            padding: 0 !important;
        }}

        .stTextInput > div > div > input {{
            background-color: rgba(255, 255, 255, 0.9) !important; /* Light background for black text */
            color: black !important;
            caret-color: black !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 14px !important;
            padding: 10px 14px !important;
            font-size: 0.95rem !important;
            box-shadow: none !important; /* Remove focus highlight shadow */
            outline: none !important; /* Remove focus outline */
        }}
        
        .stTextInput > div > div > input:focus {{
            border: 1px solid rgba(255, 255, 255, 0.2) !important; /* Keep border same on focus */
            box-shadow: none !important;
            outline: none !important;
        }}
        
        .stTextInput label {{
            color: rgba(255, 255, 255, 0.8) !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            margin-bottom: 4px !important;
        }}
        
        .stButton > button {{
            background: linear-gradient(135deg, #ffd60a 0%, #ffb703 100%) !important;
            color: #1a1c2c !important;
            font-weight: 700 !important;
            border-radius: 14px !important;
            border: none !important;
            padding: 14px !important;
            margin-top: 10px !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.9rem !important;
        }}
        
        .stButton > button:hover {{
            transform: translateY(-3px);
            box-shadow: 0 12px 20px -5px rgba(255, 214, 10, 0.5);
            filter: brightness(1.1);
        }}
        
        .help-text {{
            text-align: center;
            margin-top: 2rem;
            color: rgba(255, 255, 255, 0.5);
            font-size: 0.875rem;
        }}
        
        .help-text a {{
            color: #ffd60a;
            text-decoration: none;
            font-weight: 600;
        }}
        </style>
        
        <div class="login-wrapper">
            <div class="login-card">
                <div class="login-header">
                    <div class="login-logo">✈️</div>
                    <h1 class="login-title">UBA Logistics</h1>
                    <p class="login-subtitle">Global Operations Gateway</p>
                </div>
    """, unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        # Centering narrower inputs
        _, input_col, _ = st.columns([1, 2, 1])
        with input_col:
            username = st.text_input("Username", placeholder="ID")
            password = st.text_input("Password", type="password", placeholder="••••")
        
        st.markdown("<div style='padding: 5px;'></div>", unsafe_allow_html=True)
        
        # Centering a smaller button
        _, btn_col, _ = st.columns([1.5, 1, 1.5])
        with btn_col:
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if username == "admin" and password == "admin123":
                st.session_state.authenticated = True
                st.session_state.role = "admin"
                st.session_state.current_page = "Dashboard"
                st.rerun()
            elif username == "user" and password == "user123":
                st.session_state.authenticated = True
                st.session_state.role = "user"
                st.session_state.current_page = "Agent"
                st.rerun()
            else:
                st.error("Invalid credentials")
    
    st.markdown("""
                <div class="help-text">
                    Need assistance? <a href="mailto:it@ubalogistics.com">Contact Systems Support</a>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

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

if "role" not in st.session_state:
    st.session_state.role = None

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"


if st.session_state.authenticated:
    with st.sidebar:
        st.markdown("### Navigation")
        
        # Define pages based on role
        if st.session_state.role == "admin":
            pages = ["Dashboard", "Agent"]
        else:
            pages = ["Agent"]
            
        # Ensure current_page is valid for the role
        if st.session_state.current_page not in pages:
            st.session_state.current_page = pages[0]

        selected_page = st.radio(
            "Go to",
            pages,
            index=pages.index(st.session_state.current_page) if st.session_state.current_page in pages else 0,
        )
        st.session_state.current_page = selected_page

        st.markdown("---")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.role = None
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

