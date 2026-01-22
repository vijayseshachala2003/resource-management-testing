import streamlit as st
import requests
from datetime import date, datetime

# ---------------------------------------------------------
# HELPER: FORMAT DURATION HH:MM:SS
# ---------------------------------------------------------
def format_duration_hhmmss(total_seconds: int) -> str:
    if total_seconds <= 0:
        return "-"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# ---------------------------------------------------------
# HELPER: CALCULATE HOURS WORKED
# ---------------------------------------------------------
def calculate_hours_worked(clock_in, clock_out, minutes_worked):
    # Must have clock-out to show duration
    if not clock_in or not clock_out:
        return "-"

    # Prefer backend minutes_worked
    if minutes_worked is not None and minutes_worked > 0:
        total_seconds = int(minutes_worked * 60)
        return format_duration_hhmmss(total_seconds)

    # Fallback: compute from timestamps
    try:
        ci = datetime.fromisoformat(clock_in.replace("Z", ""))
        co = datetime.fromisoformat(clock_out.replace("Z", ""))
        total_seconds = int((co - ci).total_seconds())
        return format_duration_hhmmss(total_seconds)
    except Exception:
        return "-"


# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Attendance Daily", layout="wide")

API_BASE_URL = "http://127.0.0.1:8000"

# ---------------------------------------------------------
# HELPER: SPLIT ISO DATETIME INTO DATE + TIME
# ---------------------------------------------------------
def split_datetime(ts):
    if not ts:
        return "-", "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", ""))
        return dt.date().isoformat(), dt.strftime("%I:%M %p")
    except Exception:
        return "-", "-"

# ---------------------------------------------------------
# HELPER: SORT BY LATEST CLOCK OUT
# ---------------------------------------------------------
def sort_by_latest_clock_out(records):
    def sort_key(r):
        ts = r.get("last_clock_out_at")
        if not ts:
            return datetime.min
        return datetime.fromisoformat(ts.replace("Z", ""))

    return sorted(records, key=sort_key, reverse=True)


# ---------------------------------------------------------
# API HELPERS
# ---------------------------------------------------------
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
        st.error(f"Backend connection error: {e}")
        return None


def authenticated_request(method, endpoint, data=None, params=None):
    token = st.session_state.get("token")

    if not token:
        st.warning("🔒 Please login first from the App page.")
        st.page_link("app.py", label="➡️ Go to App → Login")
        st.stop()

    return api_request(
        method=method,
        endpoint=endpoint,
        token=token,
        json=data,
        params=params,
    )

# ---------------------------------------------------------
# AUTH GUARD + CURRENT USER
# ---------------------------------------------------------
me = authenticated_request("GET", "/me/")
current_user_id = me.get("id")

# ---------------------------------------------------------
# UI HEADER
# ---------------------------------------------------------
st.title("🗓 Attendance Daily")
st.caption("Your daily attendance across projects")
st.markdown("---")

# ---------------------------------------------------------
# FILTERS
# ---------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    selected_date = st.date_input(
    "Select Date",
    value=date.today(),
    max_value=date.today()
)


with col2:
    status_filter = st.selectbox(
        "Attendance Status",
        ["ALL", "PRESENT", "ABSENT", "LEAVE"]
    )


# ---------------------------------------------------------
# FETCH ATTENDANCE DATA
# ---------------------------------------------------------
sessions = authenticated_request(
    "GET",
    "/time/history",
    params={
        "start_date": selected_date.isoformat(),
        "end_date": selected_date.isoformat(),
    }
) or []

sessions = [
    s for s in sessions
    if s.get("clock_out_at") is not None
]

sessions.sort(
    key=lambda s: datetime.fromisoformat(
        s["clock_out_at"].replace("Z", "")
    ),
    reverse=True
)

if not sessions:
    st.info("No clock-in / clock-out sessions found for the selected date.")
    st.stop()

st.subheader("📋 Work Sessions")

for session in sessions:
    with st.container(border=True):
        cols = st.columns(6)

        project_name = session.get("project_name", "Unknown")

        clock_in_date, clock_in_time = split_datetime(session.get("clock_in_at"))
        clock_out_date, clock_out_time = split_datetime(session.get("clock_out_at"))

        cols[0].markdown(f"**Project**\n\n{project_name}")
        cols[1].markdown(f"**Work Role**\n\n{session.get('work_role')}")
        cols[2].markdown(f"**Clock In**\n\n{clock_in_time}")
        cols[3].markdown(f"**Clock Out**\n\n{clock_out_time}")
        hours_worked = calculate_hours_worked(
            session.get("clock_in_at"),
            session.get("clock_out_at"),
            session.get("minutes_worked"),
        )
        
        cols[4].markdown(f"**Hours Worked**\n\n{hours_worked}")


        cols[5].markdown(
            f"**Tasks Completed**\n\n{session.get('tasks_completed', 0)}"
        )
