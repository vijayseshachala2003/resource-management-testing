import streamlit as st
import requests
import time
from datetime import datetime, date
from role_guard import setup_role_access

# --- CONFIGURATION ---
st.set_page_config(page_title="Home", layout="wide")
setup_role_access(__file__)
API_BASE_URL = "http://127.0.0.1:8000"

# --- CUSTOM CSS FOR DARK MODE UI ---
st.markdown("""
    <style>
    .status-card {
        text-align: left;
        padding: 20px;
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        margin-bottom: 20px;
    }
    .status-title {
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #cbd5e1;
        margin: 0 0 6px 0;
    }
    .status-value {
        font-size: 22px;
        font-weight: 600;
        color: #f8fafc;
        margin: 0 0 6px 0;
    }
    .status-text {
        font-size: 14px;
        color: #cbd5e1;
        margin: 0;
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.04em;
    }
    .badge-success {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .badge-danger {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.35);
    }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def api_request(method, endpoint, token=None, json=None, params=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        response = requests.request(
            method=method,
            url=f"{API_BASE_URL}{endpoint}",
            headers=headers,
            json=json,
            params=params,
        )
        if response.status_code >= 400:
            return None
        return response.json()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def authenticated_request(method, endpoint, data=None, params=None):
    token = st.session_state.get("token")
    if not token:
        st.error("You are not logged in.")
        st.stop()
    return api_request(method, endpoint, token=token, json=data, params=params)

# ---------------------------------------------------------
# HELPERS: TIME DISPLAY
# ---------------------------------------------------------
def format_duration_hhmmss(total_seconds: int) -> str:
    if total_seconds <= 0:
        return "-"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def calculate_hours_worked(clock_in, clock_out, minutes_worked):
    if not clock_in or not clock_out:
        return "-"

    if minutes_worked is not None and minutes_worked > 0:
        total_seconds = int(minutes_worked * 60)
        return format_duration_hhmmss(total_seconds)

    try:
        ci = datetime.fromisoformat(clock_in.replace("Z", ""))
        co = datetime.fromisoformat(clock_out.replace("Z", ""))
        total_seconds = int((co - ci).total_seconds())
        return format_duration_hhmmss(total_seconds)
    except Exception:
        return "-"

def split_datetime(ts):
    if not ts:
        return "-", "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", ""))
        return dt.date().isoformat(), dt.strftime("%I:%M %p")
    except Exception:
        return "-", "-"

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
user = st.session_state.get("user")

user_name = "User"  # default fallback

if user:
    if isinstance(user, dict):
        user_name = (
            user.get("name")
            or user.get("full_name")
            or user.get("email")
            or user_name
        )
    # 1️⃣ Supabase user (highest priority)
    elif hasattr(user, "user_metadata") and user.user_metadata:
        user_name = (
            user.user_metadata.get("full_name")
            or user.user_metadata.get("name")
            or user.email
        )
    # 2️⃣ Backend User model
    elif hasattr(user, "name") and user.name:
        user_name = user.name
    # 3️⃣ Email fallback
    elif hasattr(user, "email"):
        user_name = user.email

st.markdown(f"# Welcome, {user_name}")
current_time_str = datetime.now().strftime("%H:%M:%S")
st.caption(f"Current time: {current_time_str}")
st.divider()


# --- 2. CHECK STATUS (Persistence) ---
current_session = authenticated_request("GET", "/time/current")

# --- 3. MAIN DASHBOARD LAYOUT ---
with st.container(border=True):
    col_left, col_right = st.columns([1, 2], gap="large")

    # --- LEFT COLUMN: STATUS CARD ---
    with col_left:
        st.subheader("Current Status")
        
        if current_session:
            # ACTIVE STATE
            _, display_time = split_datetime(current_session.get("clock_in_at"))
            
            st.markdown(f"""
                <div class="status-card">
                    <p class="status-title">Status</p>
                    <div class="status-value">
                        <span class="badge badge-danger">Clocked in</span>
                    </div>
                    <p class="status-text">Started at: <b>{display_time}</b></p>
                </div>
            """, unsafe_allow_html=True)
            
            st.caption(f"Current project: {current_session.get('project_name', 'Unknown')}")
            
        else:
            # INACTIVE STATE
            st.markdown(f"""
                <div class="status-card">
                    <p class="status-title">Status</p>
                    <div class="status-value">
                        <span class="badge badge-success">Ready</span>
                    </div>
                    <p class="status-text">You are not working currently.</p>
                </div>
            """, unsafe_allow_html=True)

    # --- RIGHT COLUMN: CONTROLS ---
    with col_right:
        st.subheader("Assignment Controls")
        
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
            # Build role options from available data
            role_options = []
            for project in assignments:
                role = project.get("current_user_role")
                if role and role.upper() != "N/A" and role not in role_options:
                    role_options.append(role)

            default_roles = ["ANNOTATION", "QC", "Super QC", "Live QC", "Retro QC", "Reasearch", "Other"]
            for role in default_roles:
                if role not in role_options:
                    role_options.append(role)

            role_index = 0
            if current_session:
                current_role = current_session.get("work_role")
                if current_role in role_options:
                    role_index = role_options.index(current_role)

            role_val = st.selectbox(
                "Select Role",
                options=role_options,
                index=role_index,
                disabled=disabled_flag,
            )

        st.write("")  # Spacer
        
        # Big Action Button
        if current_session:
            if st.button("Stop session and clock out", type="primary", use_container_width=True):
                st.session_state['show_clockout_popup'] = True
                st.rerun()
        else:
            if st.button("Start work session", type="primary", use_container_width=True):
                if selected_proj_name:
                    proj_id = project_map[selected_proj_name]['id']
                    clock_in_at = datetime.now().isoformat()
                    resp = authenticated_request("POST", "/time/clock-in", data={
                        "project_id": proj_id,
                        "work_role": role_val,
                        "clock_in_at": clock_in_at,
                    })
                    if resp:
                        time.sleep(1)
                        st.rerun()
                else:
                    st.warning("Please select a project first.")

# --- 3B. TODAY'S CLOCK IN / OUT DETAILS ---
st.subheader("Today's Sessions")
today_str = date.today().isoformat()
today_sessions = authenticated_request(
    "GET",
    "/time/history",
    params={
        "start_date": today_str,
        "end_date": today_str,
    },
) or []

if not today_sessions:
    st.info("No clock-in / clock-out sessions found for today.")
else:
    # Sort latest first (clock_out_at if present, else clock_in_at)
    def session_sort_key(session):
        ts = session.get("clock_out_at") or session.get("clock_in_at")
        if not ts:
            return datetime.min
        return datetime.fromisoformat(ts.replace("Z", ""))

    today_sessions.sort(key=session_sort_key, reverse=True)

    for session in today_sessions:
        with st.container(border=True):
            cols = st.columns(6)

            project_name = session.get("project_name", "Unknown")
            clock_in_date, clock_in_time = split_datetime(session.get("clock_in_at"))
            clock_out_date, clock_out_time = split_datetime(session.get("clock_out_at"))
            hours_worked = calculate_hours_worked(
                session.get("clock_in_at"),
                session.get("clock_out_at"),
                session.get("minutes_worked"),
            )

            cols[0].markdown(f"**Project**\n\n{project_name}")
            cols[1].markdown(f"**Work Role**\n\n{session.get('work_role')}")
            cols[2].markdown(f"**Clock In**\n\n{clock_in_time}")
            cols[3].markdown(f"**Clock Out**\n\n{clock_out_time}")
            cols[4].markdown(f"**Hours Worked**\n\n{hours_worked}")
            cols[5].markdown(
                f"**Tasks Completed**\n\n{session.get('tasks_completed', 0)}"
            )

# --- 4. POPUP: CLOCK OUT FORM ---
@st.dialog("Submit timesheet")
def clock_out_dialog():
    c_pop1, c_pop2 = st.columns([1, 2])

    with c_pop1:
        tasks = st.number_input("Tasks Completed", min_value=0, step=1, key="clockout_tasks")

    with c_pop2:
        notes = st.text_area(
            "Session Notes",
            placeholder="Briefly describe what you did...",
            height=100,
            key="clockout_notes",
        )

    st.write("")
    c_confirm, c_cancel = st.columns(2)

    with c_confirm:
        if st.button("Confirm submission", use_container_width=True, type="primary"):
            resp = authenticated_request("PUT", "/time/clock-out", data={
                "tasks_completed": tasks,
                "notes": notes,
            })
            if resp:
                st.success("Saved. Great work today.")
                st.session_state['show_clockout_popup'] = False
                time.sleep(1.5)
                st.rerun()

    with c_cancel:
        if st.button("Cancel", use_container_width=True):
            st.session_state['show_clockout_popup'] = False
            st.rerun()

if st.session_state.get('show_clockout_popup'):
    clock_out_dialog()