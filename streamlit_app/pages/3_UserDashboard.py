import streamlit as st
import requests
import time
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="My Dashboard", layout="wide")
API_BASE_URL = "http://127.0.0.1:8000"

# --- CUSTOM CSS FOR DARK MODE UI ---
st.markdown("""
    <style>
    /* Card Style for Dark Mode */
    .status-card {
        text-align: center;
        padding: 20px;
        background-color: rgba(255, 255, 255, 0.05); /* Transparent White */
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .status-text {
        font-size: 18px;
        margin-top: 10px;
        color: #e0e0e0;
    }
    .highlight-green { color: #00cc66; font-weight: bold; }
    .highlight-red { color: #ff4b4b; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def api_request(method, endpoint, token=None, json=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        response = requests.request(
            method=method,
            url=f"{API_BASE_URL}{endpoint}",
            headers=headers,
            json=json
        )
        if response.status_code >= 400:
            return None
        return response.json()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def authenticated_request(method, endpoint, data=None):
    token = st.session_state.get("token")
    if not token:
        st.error("🔒 You are not logged in.")
        st.stop()
    return api_request(method, endpoint, token=token, json=data)

# ---------------------------------------------------------
# DASHBOARD LOGIC
# ---------------------------------------------------------

# --- 1. FETCH USER NAME (Fixes "Hi User") ---
# We call /me/ to get the latest profile info
if 'user' not in st.session_state or not st.session_state.get('user'):
    user_profile = authenticated_request("GET", "/me/")
    if user_profile:
        st.session_state['user'] = user_profile

# Display Header
user_name = st.session_state.get('user', {}).get('name', 'User')
st.markdown(f"# 🚀 Hi, {user_name}!")
st.markdown("---")

# --- 2. CHECK STATUS (Persistence) ---
current_session = authenticated_request("GET", "/time/current")

# --- 3. MAIN DASHBOARD LAYOUT ---
with st.container(border=True):
    col_left, col_right = st.columns([1, 2], gap="large")

    # --- LEFT COLUMN: STATUS CARD ---
    with col_left:
        st.subheader("⏱️ Current Status")
        
        if current_session:
            # ACTIVE STATE (Red)
            try:
                start_time = datetime.fromisoformat(current_session['clock_in_at'])
                display_time = start_time.strftime("%I:%M %p")
            except:
                display_time = "Unknown"
            
            st.markdown(f"""
                <div class="status-card" style="border-left: 5px solid #ff4b4b;">
                    <h2 class="highlight-red">🔴 CLOCKED IN</h2>
                    <p class="status-text">Started at: <b>{display_time}</b></p>
                </div>
            """, unsafe_allow_html=True)
            
            st.info(f"🔨 Working on: **{current_session.get('project_name', 'Unknown')}**")
            
        else:
            # INACTIVE STATE (Green)
            st.markdown(f"""
                <div class="status-card" style="border-left: 5px solid #00cc66;">
                    <h2 class="highlight-green">🟢 READY</h2>
                    <p class="status-text">You are not working currently.</p>
                </div>
            """, unsafe_allow_html=True)

    # --- RIGHT COLUMN: CONTROLS ---
    with col_right:
        st.subheader("📋 Assignment Controls")
        
        # Fetch Projects from Admin API (reused)
        assignments = authenticated_request("GET", "/admin/projects/") or []
        project_map = {p['name']: p for p in assignments}
        
        disabled_flag = False
        index_val = 0
        
        # If running, lock dropdown and find index
        if current_session:
            disabled_flag = True
            current_proj_name = current_session.get('project_name', '')
            proj_names = list(project_map.keys())
            if current_proj_name in proj_names:
                index_val = proj_names.index(current_proj_name)

        # Dropdown & Role Input
        c_proj, c_role = st.columns([2, 1])
        with c_proj:
            selected_proj_name = st.selectbox(
                "Select Project", 
                options=list(project_map.keys()), 
                index=index_val,
                disabled=disabled_flag,
                placeholder="Choose a project..."
            )
        
        with c_role:
            role_val = "N/A"
            if selected_proj_name and selected_proj_name in project_map:
                # Fetch role from API response (default to N/A)
                role_val = project_map[selected_proj_name].get('current_user_role', 'N/A')
            st.text_input("Your Role", value=role_val, disabled=True)

        st.write("") # Spacer
        
        # Big Action Button
        if current_session:
            if st.button("🛑 STOP SESSION & CLOCK OUT", type="primary", use_container_width=True):
                st.session_state['show_clockout_popup'] = True
                st.rerun()
        else:
            if st.button("🚀 START WORK SESSION", type="primary", use_container_width=True):
                if selected_proj_name:
                    proj_id = project_map[selected_proj_name]['id']
                    resp = authenticated_request("POST", "/time/clock-in", data={
                        "project_id": proj_id,
                        "work_role": role_val
                    })
                    if resp:
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                else:
                    st.warning("⚠️ Please select a project first.")

# --- 4. POPUP: CLOCK OUT FORM ---
if st.session_state.get('show_clockout_popup'):
    st.markdown("---")
    st.markdown("### 📝 Submit Timesheet")
    
    with st.container(border=True):
        c_pop1, c_pop2 = st.columns([1, 2])
        
        with c_pop1:
            tasks = st.number_input("Tasks Completed", min_value=0, step=1)
        
        with c_pop2:
            notes = st.text_area("Session Notes", placeholder="Briefly describe what you did...", height=100)
        
        st.write("")
        c_confirm, c_cancel = st.columns(2)
        
        with c_confirm:
            if st.button("✅ Confirm Submission", use_container_width=True, type="primary"):
                resp = authenticated_request("PUT", "/time/clock-out", data={
                    "tasks_completed": tasks, 
                    "notes": notes
                })
                if resp:
                    st.success("✅ Saved! Great work today.")
                    st.session_state['show_clockout_popup'] = False
                    time.sleep(1.5)
                    st.rerun()
        
        with c_cancel:
             if st.button("❌ Cancel", use_container_width=True):
                 st.session_state['show_clockout_popup'] = False
                 st.rerun()