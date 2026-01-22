import streamlit as st
from datetime import date, datetime
import requests
import csv
import io

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
    if not clock_in or not clock_out:
        return "-"

    # Prefer aggregated minutes_worked
    if minutes_worked and minutes_worked > 0:
        total_seconds = int(minutes_worked * 60)
        return format_duration_hhmmss(total_seconds)

    try:
        ci = datetime.fromisoformat(str(clock_in).replace("Z", ""))
        co = datetime.fromisoformat(str(clock_out).replace("Z", ""))
        total_seconds = int((co - ci).total_seconds())
        return format_duration_hhmmss(total_seconds)
    except Exception:
        return "-"


# ---------------------------------------------------------
# AGGREGATE DUPLICATE USERS (CRITICAL FIX)
# ---------------------------------------------------------
def aggregate_by_user(rows):
    aggregated = {}

    for r in rows:
        uid = r["user_id"]

        if uid not in aggregated:
            aggregated[uid] = r.copy()
        else:
            existing = aggregated[uid]

            # earliest clock-in
            if r.get("first_clock_in") and (
                not existing.get("first_clock_in")
                or r["first_clock_in"] < existing["first_clock_in"]
            ):
                existing["first_clock_in"] = r["first_clock_in"]

            # latest clock-out
            if r.get("last_clock_out") and (
                not existing.get("last_clock_out")
                or r["last_clock_out"] > existing["last_clock_out"]
            ):
                existing["last_clock_out"] = r["last_clock_out"]

            # sum minutes worked
            existing["minutes_worked"] = (
                (existing.get("minutes_worked") or 0)
                + (r.get("minutes_worked") or 0)
            )

            # status resolution (PRESENT wins)
            if existing["attendance_status"] != "PRESENT":
                existing["attendance_status"] = r["attendance_status"]

    return list(aggregated.values())

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(
    page_title="Project Resource Allocation",
    layout="wide"
)

API_BASE_URL = "http://127.0.0.1:8000"

WORK_ROLE_OPTIONS = [
    "ANNOTATION",
    "QC",
    "LIVE_QC",
    "RETRO_QC",
    "PM",
    "APM",
    "RPM",
]

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def format_time(ts):
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", ""))
        return dt.strftime("%I:%M %p")
    except Exception:
        return "-"

def calculate_hours_worked_hhmmss_for_csv(row):
    clock_in = row.get("first_clock_in")
    clock_out = row.get("last_clock_out")
    minutes_worked = row.get("minutes_worked")

    if not clock_in or not clock_out:
        return "-"

    if minutes_worked and minutes_worked > 0:
        return format_duration_hhmmss(int(minutes_worked * 60))

    try:
        ci = datetime.fromisoformat(str(clock_in).replace("Z", ""))
        co = datetime.fromisoformat(str(clock_out).replace("Z", ""))
        return format_duration_hhmmss(int((co - ci).total_seconds()))
    except Exception:
        return "-"

def export_csv(filename, rows):
    if not rows:
        st.warning("No data to export.")
        return

    csv_rows = []

    for r in rows:
        row = r.copy()

        # ✅ add formatted hours
        row["hours_worked"] = calculate_hours_worked_hhmmss_for_csv(r)

        # ❌ remove raw minutes from CSV
        row.pop("minutes_worked", None)

        csv_rows.append(row)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=csv_rows[0].keys())
    writer.writeheader()
    writer.writerows(csv_rows)

    st.download_button(
        label="⬇️ Download CSV",
        data=buffer.getvalue(),
        file_name=filename,
        mime="text/csv"
    )

# ---------------------------------------------------------
# API HELPERS
# ---------------------------------------------------------
def api_request(method, endpoint, token=None, params=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = requests.request(
        method,
        f"{API_BASE_URL}{endpoint}",
        headers=headers,
        params=params,
    )

    if r.status_code >= 400:
        return None

    return r.json()


def authenticated_request(method, endpoint, params=None):
    token = st.session_state.get("token")
    if not token:
        st.warning("🔒 Please login first.")
        st.page_link("app.py", label="➡️ Go to Login")
        st.stop()

    return api_request(method, endpoint, token=token, params=params)

# ---------------------------------------------------------
# AUTH GUARD
# ---------------------------------------------------------
authenticated_request("GET", "/me/")

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
st.title("📊 Project Resource Allocation")
st.caption("Live allocation & attendance snapshot")
st.markdown("---")

# ---------------------------------------------------------
# FETCH PROJECTS
# ---------------------------------------------------------
projects = authenticated_request("GET", "/admin/projects") or []
project_map = {p["name"]: p["id"] for p in projects}

# ---------------------------------------------------------
# FILTERS
# ---------------------------------------------------------
f1, f2, f3, f4, f5 = st.columns(5)

with f1:
    selected_project = st.selectbox("Project", list(project_map.keys()))

with f2:
    selected_date = st.date_input("Date", value=date.today(), max_value=date.today())

with f3:
    designation_filter = st.selectbox("Designation", ["ALL", "ADMIN", "USER"])

with f4:
    status_filter = st.selectbox(
        "Status", ["ALL", "PRESENT", "ABSENT", "LEAVE", "UNKNOWN"]
    )

if not selected_project:
    st.stop()

project_id = project_map[selected_project]

# ---------------------------------------------------------
# FETCH RESOURCE DATA
# ---------------------------------------------------------
data = authenticated_request(
    "GET",
    "/admin/project-resource-allocation/",
    params={
        "project_id": project_id,
        "target_date": selected_date.isoformat(),
    }
)

if not data or not data.get("resources"):
    st.info("No allocation data found.")
    st.stop()

# 🔴 FIX APPLIED HERE
resources = aggregate_by_user(data["resources"])

# ---------------------------------------------------------
# WORK ROLE FILTER
# ---------------------------------------------------------
with f5:
    work_role_filter = st.selectbox(
        "Work Role",
        ["ALL"] + WORK_ROLE_OPTIONS,
    )

# ---------------------------------------------------------
# APPLY FILTERS
# ---------------------------------------------------------
filtered = resources

if designation_filter != "ALL":
    filtered = [r for r in filtered if r.get("designation") == designation_filter]

if work_role_filter != "ALL":
    filtered = [r for r in filtered if r.get("work_role") == work_role_filter]

if status_filter != "ALL":
    filtered = [r for r in filtered if r.get("attendance_status") == status_filter]

# ---------------------------------------------------------
# KPI SUMMARY
# ---------------------------------------------------------
st.subheader("📌 Summary")

allocated = len(filtered)
present = sum(r["attendance_status"] == "PRESENT" for r in filtered)
absent = sum(r["attendance_status"] == "ABSENT" for r in filtered)
leave = sum(r["attendance_status"] == "LEAVE" for r in filtered)
unknown = sum(r["attendance_status"] == "UNKNOWN" for r in filtered)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Allocated", allocated)
c2.metric("Present", present)
c3.metric("Absent", absent)
c4.metric("Leave", leave)
c5.metric("Unknown", unknown)

# ---------------------------------------------------------
# EXPORT CSV
# ---------------------------------------------------------
export_csv(
    f"project_allocation_{selected_project}_{selected_date}.csv",
    filtered
)

# ---------------------------------------------------------
# ALLOCATION LIST
# ---------------------------------------------------------
st.subheader("👥 Allocation List")

if not filtered:
    st.info("No users match the selected filters.")
    st.stop()

for r in filtered:
    with st.container(border=True):
        cols = st.columns(9)

        cols[0].markdown(f"**Name**\n\n{r.get('name', '-')}")
        cols[1].markdown(f"**Email**\n\n{r.get('email', '-')}")
        cols[2].markdown(f"**Designation**\n\n{r.get('designation', '-')}")
        cols[3].markdown(f"**Work Role**\n\n{r.get('work_role', '-')}")
        cols[4].markdown(f"**Reporting Manager**\n\n{r.get('reporting_manager') or '-'}")
        cols[5].markdown(f"**Status**\n\n{r.get('attendance_status', '-')}")
        cols[6].markdown(f"**Clock In**\n\n{format_time(r.get('first_clock_in'))}")
        cols[7].markdown(f"**Clock Out**\n\n{format_time(r.get('last_clock_out'))}")

        hours_worked = calculate_hours_worked(
            r.get("first_clock_in"),
            r.get("last_clock_out"),
            r.get("minutes_worked"),
        )

        cols[8].markdown(f"**Hours Worked**\n\n{hours_worked}")
