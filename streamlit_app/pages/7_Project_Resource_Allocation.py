import streamlit as st
from datetime import date, datetime, timedelta
import requests
import csv
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
from dotenv import load_dotenv
from typing import Dict, List, Optional
import time

load_dotenv()

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(
    page_title="Project Resource Allocation",
    layout="wide"
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

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
# HELPER FUNCTIONS
# ---------------------------------------------------------
def format_duration_hhmmss(total_seconds: int) -> str:
    if total_seconds <= 0:
        return "-"
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def format_time(ts):
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", ""))
        return dt.strftime("%I:%M %p")
    except Exception:
        return "-"

def calculate_hours_worked(clock_in, clock_out, minutes_worked):
    if not clock_in or not clock_out:
        return "-"
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

def aggregate_by_user(rows):
    aggregated = {}
    for r in rows:
        uid = r["user_id"]
        if uid not in aggregated:
            aggregated[uid] = r.copy()
        else:
            existing = aggregated[uid]
            if r.get("first_clock_in") and (
                not existing.get("first_clock_in")
                or r["first_clock_in"] < existing["first_clock_in"]
            ):
                existing["first_clock_in"] = r["first_clock_in"]
            if r.get("last_clock_out") and (
                not existing.get("last_clock_out")
                or r["last_clock_out"] > existing["last_clock_out"]
            ):
                existing["last_clock_out"] = r["last_clock_out"]
            existing["minutes_worked"] = (
                (existing.get("minutes_worked") or 0)
                + (r.get("minutes_worked") or 0)
            )
            if existing["attendance_status"] != "PRESENT":
                existing["attendance_status"] = r["attendance_status"]
    return list(aggregated.values())

def export_csv(filename, rows):
    if not rows:
        st.warning("No data to export.")
        return
    csv_rows = []
    for r in rows:
        row = r.copy()
        if "minutes_worked" in row and row.get("minutes_worked"):
            row["hours_worked"] = format_duration_hhmmss(int(row["minutes_worked"] * 60))
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
# Create a session for connection pooling
@st.cache_resource
def get_requests_session():
    """Create a requests session with connection pooling"""
    session = requests.Session()
    # Configure adapter with connection pooling
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=10,
        max_retries=requests.adapters.Retry(
            total=2,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def authenticated_request(method, endpoint, params=None, json_data=None, retries=2):
    """Make authenticated API request with retry logic and connection pooling"""
    token = st.session_state.get("token")
    if not token:
        st.warning("🔒 Please login first.")
        st.page_link("app.py", label="➡️ Go to Login")
        st.stop()
    
    headers = {"Authorization": f"Bearer {token}"}
    session = get_requests_session()
    
    for attempt in range(retries + 1):
        try:
            if method.upper() == "POST" and json_data:
                r = session.post(
                    f"{API_BASE_URL}{endpoint}",
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=(10, 30)  # (connect timeout, read timeout)
                )
            else:
                r = session.request(
                    method,
                    f"{API_BASE_URL}{endpoint}",
                    headers=headers,
                    params=params,
                    timeout=(10, 30)
                )
            if r.status_code >= 400:
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                return None
            return r.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, 
                ConnectionResetError, requests.exceptions.ChunkedEncodingError) as e:
            if attempt < retries:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = min(2 ** attempt, 4)
                time.sleep(wait_time)
                continue
            # Silently return None on final failure
            return None
        except Exception as e:
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            return None
    return None

# Cached API functions
@st.cache_data(ttl=300, show_spinner="Loading projects...")
def get_all_projects_cached():
    """Cache projects list for 5 minutes"""
    return authenticated_request("GET", "/admin/projects") or []

@st.cache_data(ttl=300, show_spinner="Loading user names...")
def get_user_name_mapping():
    """Cache user name mapping for 5 minutes"""
    users = authenticated_request("GET", "/admin/users/", params={"limit": 1000})
    if not users:
        return {}
    return {str(user["id"]): user["name"] for user in users}

@st.cache_data(ttl=60, show_spinner="Loading user data...")
def get_users_with_filter_cached(selected_date_str):
    """Cache user data for 1 minute"""
    return authenticated_request(
        "POST", 
        "/admin/users/users_with_filter",
        json_data={"date": selected_date_str}
    ) or []

@st.cache_data(ttl=60, show_spinner="Loading metrics...")
def get_project_metrics_cached(project_id, start_date_str, end_date_str):
    """Cache project metrics for 1 minute"""
    return authenticated_request("GET", "/admin/metrics/user_daily/", params={
        "project_id": project_id,
        "start_date": start_date_str,
        "end_date": end_date_str
    }) or []

@st.cache_data(ttl=60, show_spinner="Loading allocation data...")
def get_project_allocation_cached(project_id, target_date_str):
    """Cache project allocation for 1 minute"""
    return authenticated_request("GET", "/admin/project-resource-allocation/", params={
        "project_id": project_id,
        "target_date": target_date_str
    })


# ---------------------------------------------------------
# AUTH GUARD
# ---------------------------------------------------------
if "token" not in st.session_state:
    st.warning("🔒 Please login first from the main page.")
    st.stop()

authenticated_request("GET", "/me/")

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
st.title("📊 Project Resource Allocation Dashboard")
st.caption("Comprehensive resource allocation, attendance, and productivity overview")
st.markdown("---")

# ---------------------------------------------------------
# DATE SELECTOR (Global)
# ---------------------------------------------------------
selected_date = st.date_input("Select Date", value=date.today(), max_value=date.today(), key="allocation_date")

# ---------------------------------------------------------
# TABS
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 Overview Dashboard", "📈 Visualizations", "🔍 Detailed Project View"])

# ==========================================
# TAB 1: OVERVIEW DASHBOARD
# ==========================================
with tab1:
    # Fetch all users with role='USER' using cached function
    users_data = get_users_with_filter_cached(selected_date.isoformat())
    
    # Filter users with role='USER' - the API already returns enriched data
    user_role_users = [u for u in users_data if u.get("role") == "USER" or str(u.get("role")) == "USER"]
    
    # Calculate counts
    total_users = len(user_role_users)
    allocated_users = [u for u in user_role_users if u.get("allocated_projects", 0) > 0]
    not_allocated_users = [u for u in user_role_users if u.get("allocated_projects", 0) == 0]
    present_users = [u for u in user_role_users if u.get("today_status") == "PRESENT"]
    absent_users = [u for u in user_role_users if u.get("today_status") == "ABSENT"]
    unknown_users = [u for u in user_role_users if u.get("today_status") == "UNKNOWN" or not u.get("today_status")]
    
    # SECTION 1: USER DASHBOARD
    st.markdown("## 👥 User Overview")
    st.markdown("Dashboard showing Total users count with role 'USER', Count of present, absent, allocated and not allocated/unknown")
    
    # Display clickable metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    # Initialize session state for modals
    if "show_user_list" not in st.session_state:
        st.session_state.show_user_list = None
    if "user_list_data" not in st.session_state:
        st.session_state.user_list_data = []
    
    with col1:
        if st.button(f"**Total Users**\n\n{total_users}", use_container_width=True, key="btn_total_users"):
            st.session_state.show_user_list = "total"
            st.session_state.user_list_data = user_role_users
    
    with col2:
        if st.button(f"**Present**\n\n{len(present_users)}", use_container_width=True, key="btn_present"):
            st.session_state.show_user_list = "present"
            st.session_state.user_list_data = present_users
    
    with col3:
        if st.button(f"**Absent**\n\n{len(absent_users)}", use_container_width=True, key="btn_absent"):
            st.session_state.show_user_list = "absent"
            st.session_state.user_list_data = absent_users
    
    with col4:
        if st.button(f"**Allocated**\n\n{len(allocated_users)}", use_container_width=True, key="btn_allocated"):
            st.session_state.show_user_list = "allocated"
            st.session_state.user_list_data = allocated_users
    
    with col5:
        if st.button(f"**Not Allocated**\n\n{len(not_allocated_users)}", use_container_width=True, key="btn_not_allocated"):
            st.session_state.show_user_list = "not_allocated"
            st.session_state.user_list_data = not_allocated_users
    
    with col6:
        if st.button(f"**Unknown**\n\n{len(unknown_users)}", use_container_width=True, key="btn_unknown"):
            st.session_state.show_user_list = "unknown"
            st.session_state.user_list_data = unknown_users
    
    # Show exportable list when a button is clicked
    if st.session_state.show_user_list and st.session_state.user_list_data:
        list_title = {
            "total": "All Users (Role: USER)",
            "present": "Present Users",
            "absent": "Absent Users",
            "allocated": "Allocated Users",
            "not_allocated": "Not Allocated Users",
            "unknown": "Unknown Status Users"
        }.get(st.session_state.show_user_list, "Users")
        
        st.markdown(f"### 📋 {list_title}")
        df_users = pd.DataFrame(st.session_state.user_list_data)
        if not df_users.empty:
            st.dataframe(df_users, use_container_width=True, height=300)
            export_csv(f"{list_title.replace(' ', '_')}_{selected_date}.csv", st.session_state.user_list_data)
        else:
            st.info("No users found.")
        
        if st.button("Close", key="close_user_list"):
            st.session_state.show_user_list = None
            st.session_state.user_list_data = []
            st.rerun()
    
    st.markdown("---")
    
    # SECTION 2: TOTAL COUNTERS
    st.markdown("## 📊 Overall Statistics")
    
    # Fetch metrics for all projects using cached functions
    all_projects = get_all_projects_cached()
    project_ids = [p["id"] for p in all_projects]
    
    # Fetch user daily metrics for all projects (sequential with caching)
    date_str = selected_date.isoformat()
    total_hours = 0
    total_tasks = 0
    metrics_data = []
    
    for project_id in project_ids:
        metrics = get_project_metrics_cached(project_id, date_str, date_str)
        if metrics:
            for m in metrics:
                total_hours += float(m.get("hours_worked", 0) or 0)
                total_tasks += int(m.get("tasks_completed", 0) or 0)
                metrics_data.append(m)
    
    # Display counters
    counter_col1, counter_col2 = st.columns(2)
    with counter_col1:
        st.metric("Total Hours Worked", f"{total_hours:.2f} hrs")
    with counter_col2:
        st.metric("Total Tasks Completed", f"{int(total_tasks)}")
    
    st.markdown("---")
    
    # SECTION 3: PROJECT CARDS
    st.markdown("## 📁 Project Cards")
    st.markdown("Project cards showing total number of tasks performed, total hours clocked, and count of different roles")
    
    # Fetch project data with metrics (using cached functions)
    projects_with_metrics = []
    date_str = selected_date.isoformat()
    
    for project in all_projects:
        project_id = project["id"]
        
        # Get metrics for this project (cached)
        project_metrics = get_project_metrics_cached(project_id, date_str, date_str)
        
        # Calculate totals
        proj_total_tasks = sum(int(m.get("tasks_completed", 0) or 0) for m in project_metrics)
        proj_total_hours = sum(float(m.get("hours_worked", 0) or 0) for m in project_metrics)
        
        # Count roles
        role_counts = {}
        for m in project_metrics:
            role = m.get("work_role", "Unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
        
        # Get allocation data (cached)
        allocation_data = get_project_allocation_cached(project_id, date_str)
        
        total_users_in_project = 0
        if allocation_data and allocation_data.get("resources"):
            resources = aggregate_by_user(allocation_data["resources"])
            total_users_in_project = len(resources)
        
        projects_with_metrics.append({
            "project": project,
            "total_tasks": proj_total_tasks,
            "total_hours": proj_total_hours,
            "role_counts": role_counts,
            "total_users": total_users_in_project,
            "metrics": project_metrics,
            "allocation_data": allocation_data
        })
    
    # Display project cards in a grid with standardized height
    num_cols = 3
    for i in range(0, len(projects_with_metrics), num_cols):
        cols = st.columns(num_cols)
        for j, col in enumerate(cols):
            if i + j < len(projects_with_metrics):
                proj_data = projects_with_metrics[i + j]
                proj = proj_data["project"]
                
                with col:
                    with st.container(border=True):
                        st.markdown(f"### {proj.get('name', 'Unknown Project')}")
                        
                        # Clickable metrics
                        metric_col1, metric_col2 = st.columns(2)
                        with metric_col1:
                            if st.button(f"**Tasks**\n{proj_data['total_tasks']}", key=f"tasks_{proj['id']}", use_container_width=True):
                                st.session_state.show_project_list = f"tasks_{proj['id']}"
                                st.session_state.project_list_data = proj_data
                        with metric_col2:
                            if st.button(f"**Hours**\n{proj_data['total_hours']:.1f}", key=f"hours_{proj['id']}", use_container_width=True):
                                st.session_state.show_project_list = f"hours_{proj['id']}"
                                st.session_state.project_list_data = proj_data
                        
                        # Role counts - standardized to show max 4 roles, rest in expander
                        st.markdown("**Role Counts:**")
                        roles_list = list(proj_data["role_counts"].items())
                        max_visible_roles = 4
                        
                        # Always show first 4 roles (or all if less than 4)
                        visible_roles = roles_list[:max_visible_roles]
                        for role, count in visible_roles:
                            if st.button(f"{role}: {count}", key=f"role_{proj['id']}_{role}", use_container_width=True):
                                st.session_state.show_project_list = f"role_{proj['id']}_{role}"
                                st.session_state.project_list_data = proj_data
                                st.session_state.selected_role = role
                        
                        # Show remaining roles in expander if there are more than 4
                        if len(roles_list) > max_visible_roles:
                            remaining_count = len(roles_list) - max_visible_roles
                            with st.expander(f"➕ {remaining_count} more role(s)"):
                                for role, count in roles_list[max_visible_roles:]:
                                    if st.button(f"{role}: {count}", key=f"role_{proj['id']}_{role}_exp", use_container_width=True):
                                        st.session_state.show_project_list = f"role_{proj['id']}_{role}"
                                        st.session_state.project_list_data = proj_data
                                        st.session_state.selected_role = role
                        
                        # Add spacing to standardize height
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Total users
                        if st.button(f"**Total Users**\n{proj_data['total_users']}", key=f"users_{proj['id']}", use_container_width=True):
                            st.session_state.show_project_list = f"users_{proj['id']}"
                            st.session_state.project_list_data = proj_data
    
    # Initialize project list state
    if "show_project_list" not in st.session_state:
        st.session_state.show_project_list = None
    if "project_list_data" not in st.session_state:
        st.session_state.project_list_data = None
    
    # Show exportable list when a project metric is clicked
    if st.session_state.show_project_list and st.session_state.project_list_data:
        proj_data = st.session_state.project_list_data
        proj = proj_data["project"]
        
        if st.session_state.show_project_list.startswith("tasks_"):
            st.markdown(f"### 📋 Tasks Details - {proj.get('name')}")
            task_list = []
            user_map = get_user_name_mapping()
            for m in proj_data["metrics"]:
                user_id = str(m.get("user_id"))
                task_list.append({
                    "user_name": user_map.get(user_id, "Unknown"),
                    "tasks_completed": m.get("tasks_completed", 0),
                    "hours_worked": m.get("hours_worked", 0),
                    "work_role": m.get("work_role", "Unknown"),
                    "user_id": user_id
                })
            if task_list:
                df_tasks = pd.DataFrame(task_list)
                # Reorder columns to show name first
                df_tasks = df_tasks[["user_name", "tasks_completed", "hours_worked", "work_role", "user_id"]]
                st.dataframe(df_tasks, use_container_width=True, height=300)
                export_csv(f"{proj.get('name')}_tasks_{selected_date}.csv", task_list)
            else:
                st.info("No task data available.")
        
        elif st.session_state.show_project_list.startswith("hours_"):
            st.markdown(f"### 📋 Hours Details - {proj.get('name')}")
            hours_list = []
            user_map = get_user_name_mapping()
            for m in proj_data["metrics"]:
                user_id = str(m.get("user_id"))
                hours_list.append({
                    "user_name": user_map.get(user_id, "Unknown"),
                    "hours_worked": m.get("hours_worked", 0),
                    "tasks_completed": m.get("tasks_completed", 0),
                    "work_role": m.get("work_role", "Unknown"),
                    "user_id": user_id
                })
            if hours_list:
                df_hours = pd.DataFrame(hours_list)
                # Reorder columns to show name first
                df_hours = df_hours[["user_name", "hours_worked", "tasks_completed", "work_role", "user_id"]]
                st.dataframe(df_hours, use_container_width=True, height=300)
                export_csv(f"{proj.get('name')}_hours_{selected_date}.csv", hours_list)
            else:
                st.info("No hours data available.")
        
        elif st.session_state.show_project_list.startswith("role_"):
            st.markdown(f"### 📋 Role Details - {proj.get('name')} - {st.session_state.get('selected_role', 'Unknown')}")
            role_list = []
            selected_role = st.session_state.get("selected_role", "")
            user_map = get_user_name_mapping()
            for m in proj_data["metrics"]:
                if m.get("work_role") == selected_role:
                    user_id = str(m.get("user_id"))
                    role_list.append({
                        "user_name": user_map.get(user_id, "Unknown"),
                        "user_id": user_id,
                        "work_role": m.get("work_role", "Unknown"),
                        "hours_worked": m.get("hours_worked", 0),
                        "tasks_completed": m.get("tasks_completed", 0)
                    })
            if role_list:
                df_role = pd.DataFrame(role_list)
                # Reorder columns to show name first
                df_role = df_role[["user_name", "work_role", "hours_worked", "tasks_completed", "user_id"]]
                st.dataframe(df_role, use_container_width=True, height=300)
                export_csv(f"{proj.get('name')}_{selected_role}_users_{selected_date}.csv", role_list)
            else:
                st.info(f"No users found for role: {selected_role}")
        
        elif st.session_state.show_project_list.startswith("users_"):
            st.markdown(f"### 📋 Users in Project - {proj.get('name')}")
            if proj_data.get("allocation_data") and proj_data["allocation_data"].get("resources"):
                resources = aggregate_by_user(proj_data["allocation_data"]["resources"])
                user_list = []
                for r in resources:
                    user_metrics = [m for m in proj_data["metrics"] if m.get("user_id") == r.get("user_id")]
                    total_user_hours = sum(float(m.get("hours_worked", 0) or 0) for m in user_metrics)
                    total_user_tasks = sum(int(m.get("tasks_completed", 0) or 0) for m in user_metrics)
                    
                    user_list.append({
                        "name": r.get("name", "-"),
                        "email": r.get("email", "-"),
                        "work_role": r.get("work_role", "-"),
                        "attendance_status": r.get("attendance_status", "-"),
                        "total_hours_clocked": f"{total_user_hours:.2f}",
                        "total_tasks_performed": total_user_tasks
                    })
                if user_list:
                    df_users = pd.DataFrame(user_list)
                    st.dataframe(df_users, use_container_width=True, height=300)
                    export_csv(f"{proj.get('name')}_users_{selected_date}.csv", user_list)
                else:
                    st.info("No users found in this project.")
            else:
                st.info("No allocation data available for this project.")
        
        if st.button("Close", key="close_project_list"):
            st.session_state.show_project_list = None
            st.session_state.project_list_data = None
            st.session_state.selected_role = None
            st.rerun()

# ==========================================
# TAB 2: VISUALIZATIONS
# ==========================================
with tab2:
    st.markdown("## 📈 Visualizations")
    
    # Fetch metrics for all projects (using cached functions)
    all_projects = get_all_projects_cached()
    project_ids = [p["id"] for p in all_projects]
    project_map = {p["id"]: p["name"] for p in all_projects}
    
    # Fetch metrics sequentially (using cached functions)
    date_str = selected_date.isoformat()
    metrics_data = []
    
    for project_id in project_ids:
        metrics = get_project_metrics_cached(project_id, date_str, date_str)
        if metrics:
            metrics_data.extend(metrics)
    
    # Prepare data for charts
    if metrics_data:
        df_metrics = pd.DataFrame(metrics_data)
        df_metrics["date"] = pd.to_datetime(df_metrics.get("metric_date", selected_date))
        df_metrics["project_name"] = df_metrics["project_id"].astype(str).map(project_map)
        
        # Chart 1: Hours Worked by Project
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("#### Total Hours Worked by Project")
            hours_by_project = df_metrics.groupby("project_name")["hours_worked"].sum().reset_index()
            fig1 = px.bar(
                hours_by_project,
                x="project_name",
                y="hours_worked",
                labels={"project_name": "Project", "hours_worked": "Hours Worked"}
            )
            fig1.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig1, use_container_width=True)
        
        with chart_col2:
            st.markdown("#### Total Tasks Completed by Project")
            tasks_by_project = df_metrics.groupby("project_name")["tasks_completed"].sum().reset_index()
            fig2 = px.bar(
                tasks_by_project,
                x="project_name",
                y="tasks_completed",
                labels={"project_name": "Project", "tasks_completed": "Tasks Completed"}
            )
            fig2.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig2, use_container_width=True)
        
        # Chart 3: Role Distribution
        chart_col3, chart_col4 = st.columns(2)
        
        with chart_col3:
            st.markdown("#### Hours Worked by Role")
            hours_by_role = df_metrics.groupby("work_role")["hours_worked"].sum().reset_index()
            fig3 = px.pie(
                hours_by_role,
                values="hours_worked",
                names="work_role",
                title="Hours Distribution by Role"
            )
            fig3.update_layout(height=400)
            st.plotly_chart(fig3, use_container_width=True)
        
        with chart_col4:
            st.markdown("#### Tasks Completed by Role")
            tasks_by_role = df_metrics.groupby("work_role")["tasks_completed"].sum().reset_index()
            fig4 = px.pie(
                tasks_by_role,
                values="tasks_completed",
                names="work_role",
                title="Tasks Distribution by Role"
            )
            fig4.update_layout(height=400)
            st.plotly_chart(fig4, use_container_width=True)
        
        # Chart 5: Project vs Role Heatmap
        st.markdown("#### Hours Worked: Project vs Role Heatmap")
        heatmap_data = df_metrics.groupby(["project_name", "work_role"])["hours_worked"].sum().reset_index()
        heatmap_pivot = heatmap_data.pivot(index="project_name", columns="work_role", values="hours_worked").fillna(0)
        
        fig5 = go.Figure(data=go.Heatmap(
            z=heatmap_pivot.values,
            x=heatmap_pivot.columns,
            y=heatmap_pivot.index,
            colorscale='Blues',
            text=heatmap_pivot.values,
            texttemplate='%{text:.1f}',
            textfont={"size": 10},
            colorbar=dict(title="Hours")
        ))
        fig5.update_layout(height=400, xaxis_title="Role", yaxis_title="Project")
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info("No metrics data available for visualization.")

# ==========================================
# TAB 3: DETAILED PROJECT VIEW
# ==========================================
with tab3:
    st.markdown("## 🔍 Detailed Project View")
    
    # Fetch projects (cached)
    all_projects = get_all_projects_cached()
    
    # Filters
    f1, f2, f3, f4, f5 = st.columns(5)
    
    with f1:
        selected_project = st.selectbox("Project", ["All"] + [p["name"] for p in all_projects], key="detail_project")
    
    with f2:
        detail_date = st.date_input("Date", value=selected_date, max_value=date.today(), key="detail_date")
    
    with f3:
        designation_filter = st.selectbox("Designation", ["ALL", "ADMIN", "USER"], key="detail_designation")
    
    with f4:
        status_filter = st.selectbox(
            "Status", ["ALL", "PRESENT", "ABSENT", "LEAVE", "UNKNOWN"], key="detail_status"
        )
    
    with f5:
        work_role_filter = st.selectbox(
            "Work Role",
            ["ALL"] + WORK_ROLE_OPTIONS,
            key="detail_work_role"
        )
    
    if selected_project and selected_project != "All":
        # Find project ID from project name
        project_id = None
        for p in all_projects:
            if p.get("name") == selected_project:
                project_id = p.get("id")
                break
        
        if project_id:
            # Fetch resource data (cached)
            data = get_project_allocation_cached(project_id, detail_date.isoformat())
            
            if data and data.get("resources"):
                resources = aggregate_by_user(data["resources"])
                
                # Apply filters
                filtered = resources
                if designation_filter != "ALL":
                    filtered = [r for r in filtered if r.get("designation") == designation_filter]
                if work_role_filter != "ALL":
                    filtered = [r for r in filtered if r.get("work_role") == work_role_filter]
                if status_filter != "ALL":
                    filtered = [r for r in filtered if r.get("attendance_status") == status_filter]
                
                # Summary
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
                
                # Export CSV
                export_csv(
                    f"project_allocation_{selected_project}_{detail_date}.csv",
                    filtered
                )
                
                # Allocation List
                st.subheader("👥 Allocation List")
                if not filtered:
                    st.info("No users match the selected filters.")
                else:
                    # Get metrics for tasks calculation
                    project_metrics = get_project_metrics_cached(project_id, detail_date.isoformat(), detail_date.isoformat())
                    # Create a mapping of user_id to total tasks
                    user_tasks_map = {}
                    for m in project_metrics:
                        user_id = str(m.get("user_id"))
                        if user_id not in user_tasks_map:
                            user_tasks_map[user_id] = 0
                        user_tasks_map[user_id] += int(m.get("tasks_completed", 0) or 0)
                    
                    for r in filtered:
                        with st.container(border=True):
                            user_id = str(r.get("user_id"))
                            tasks_completed = user_tasks_map.get(user_id, 0)
                            cols = st.columns(10)
                            cols[0].markdown(f"**Name**\n\n{r.get('name', '-')}")
                            cols[1].markdown(f"**Email**\n\n{r.get('email', '-')}")
                            cols[2].markdown(f"**Designation**\n\n{r.get('designation', '-')}")
                            cols[3].markdown(f"**Work Role**\n\n{r.get('work_role', '-')}")
                            cols[4].markdown(f"**Reporting Manager**\n\n{r.get('reporting_manager') or '-'}")
                            cols[5].markdown(f"**Status**\n\n{r.get('attendance_status', '-')}")
                            cols[6].markdown(f"**Tasks Completed**\n\n{tasks_completed}")
                            cols[7].markdown(f"**Clock In**\n\n{format_time(r.get('first_clock_in'))}")
                            cols[8].markdown(f"**Clock Out**\n\n{format_time(r.get('last_clock_out'))}")
                            hours_worked = calculate_hours_worked(
                                r.get("first_clock_in"),
                                r.get("last_clock_out"),
                                r.get("minutes_worked"),
                            )
                            cols[9].markdown(f"**Hours Worked**\n\n{hours_worked}")
            else:
                st.info("No allocation data found for this project.")
        else:
            st.warning("Project not found.")
    else:
        st.info("Please select a project to view detailed allocation information.")
