import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from role_guard import get_user_role
import plotly.express as px
import plotly.graph_objects as go
import time

load_dotenv()

# --- CONFIGURATION ---
st.set_page_config(page_title="Team Stats", layout="wide")

# Basic role check
role = get_user_role()
if not role or role not in ["USER", "ADMIN", "MANAGER"]:
    st.error("Access denied. Please log in.")
    st.stop()
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# --- AUTH CHECK ---
if "token" not in st.session_state:
    st.warning("🔒 Please login first from the main page.")
    st.stop()

# --- HELPER FUNCTIONS ---
@st.cache_resource
def get_requests_session():
    """Create a cached requests session for connection pooling"""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=3
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def authenticated_request(method, endpoint, params=None, json_data=None, retries=2, show_error=True):
    """Make authenticated API request with retry logic and connection pooling.
    If show_error=False, errors are logged but not shown in the UI (for optional/fallback calls)."""
    token = st.session_state.get("token")
    if not token:
        st.warning("🔒 Please login first.")
        if st.button("➡️ Go to Login"):
            st.session_state.clear()
            st.rerun()
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
                    timeout=(10, 30)
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
                error_detail = f"API Error {r.status_code}"
                try:
                    error_response = r.json()
                    if isinstance(error_response, dict) and "detail" in error_response:
                        error_detail = error_response["detail"]
                    # Also log full response for debugging
                    print(f"[API Error Response] {method} {endpoint}: {error_response}")
                except:
                    error_detail = r.text[:500] if r.text else f"HTTP {r.status_code}"
                    print(f"[API Error Text] {method} {endpoint}: {error_detail}")
                
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                # Log error for debugging
                print(f"[API Error] {method} {endpoint}: {error_detail}")
                if show_error:
                    st.error(f"⚠️ API Error: {error_detail}")
                return None
            return r.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, 
                ConnectionResetError, requests.exceptions.ChunkedEncodingError) as e:
            if attempt < retries:
                wait_time = min(2 ** attempt, 4)
                time.sleep(wait_time)
                continue
            print(f"[Connection Error] {method} {endpoint}: {str(e)}")
            if show_error:
                st.error(f"⚠️ Connection Error: {str(e)}")
            return None
        except Exception as e:
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            print(f"[Request Error] {method} {endpoint}: {str(e)}")
            if show_error:
                st.error(f"⚠️ Request Error: {str(e)}")
            return None
    return None

def export_csv(filename, rows):
    if not rows:
        st.warning("No data to export.")
        return
    df = pd.DataFrame(rows)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        f"📥 Download {filename}",
        csv,
        filename,
        "text/csv",
        key=f"download_{filename}"
    )

# Cached API functions
@st.cache_data(ttl=300, show_spinner="Loading projects...")
def get_all_projects_cached(reference_date=None):
    """Cache projects list for 5 minutes, optionally filtered by reference_date"""
    params = {}
    if reference_date:
        params["reference_date"] = reference_date.isoformat()
    return authenticated_request("GET", "/admin/projects", params=params) or []

@st.cache_data(ttl=300, show_spinner="Loading your projects...")
def get_user_projects_cached(reference_date=None):
    """Get projects where the current user is a member, optionally filtered by reference_date"""
    # Pass reference_date to API if provided
    params = {}
    if reference_date:
        params["reference_date"] = reference_date.isoformat()
    
    all_projects = authenticated_request("GET", "/admin/projects", params=params) or []
    # Filter projects where current_user_role is not "N/A" (user is a member)
    user_projects = [
        p for p in all_projects 
        if p.get("current_user_role") and p.get("current_user_role") != "N/A"
    ]
    return user_projects

@st.cache_data(ttl=60, show_spinner="Loading team members...")
def get_team_members_cached(user_project_ids, selected_date=None):
    """Get all team members from user's projects, filtering by date if provided"""
    from datetime import date as date_type
    if selected_date is None:
        selected_date = date_type.today()
    
    team_member_ids = set()
    for project_id in user_project_ids:
        members = authenticated_request("GET", f"/admin/projects/{project_id}/members") or []
        if not members:
            # Debug: Log if no members found for a project
            print(f"[DEBUG] No members returned for project {project_id}")
        for member in members:
            if isinstance(member, dict):
                # Check if member is active and within date range
                is_active = member.get("is_active", True)
                assigned_from = member.get("assigned_from")
                assigned_to = member.get("assigned_to")
                
                # Skip inactive members
                if not is_active:
                    continue
                
                # Check date range if dates are provided
                if assigned_from:
                    try:
                        from_date = date_type.fromisoformat(str(assigned_from)) if isinstance(assigned_from, str) else assigned_from
                        if selected_date < from_date:
                            continue  # Assignment hasn't started yet
                    except:
                        pass
                
                if assigned_to:
                    try:
                        to_date = date_type.fromisoformat(str(assigned_to)) if isinstance(assigned_to, str) else assigned_to
                        if selected_date > to_date:
                            continue  # Assignment has ended
                    except:
                        pass
                
                # API returns user_id, not id - ensure we convert to string for consistent comparison
                user_id = member.get("user_id") or member.get("id")
                if user_id:
                    # Convert UUID to string for consistent comparison
                    team_member_ids.add(str(user_id))
    return team_member_ids

@st.cache_data(ttl=60, show_spinner="Loading user data...")
def get_users_with_filter_cached(selected_date_str, silent_fail=False):
    """Cache user data for 1 minute. If silent_fail=True, don't show API error in UI (for fallback flow)."""
    response = authenticated_request(
        "POST", 
        "/admin/users/users_with_filter",
        json_data={"date": selected_date_str},
        show_error=not silent_fail
    )
    # API returns {"items": [...], "meta": {...}}
    if response and isinstance(response, dict) and "items" in response:
        return response["items"]
    # If response is None, API call failed (error shown only if not silent_fail)
    return []

def get_user_data_from_project_members(project_ids, selected_date):
    """Fallback: Get user data directly from project members if users_with_filter fails"""
    from datetime import date as date_type
    if selected_date is None:
        selected_date = date_type.today()
    
    users_dict = {}  # {user_id: user_data}
    
    for project_id in project_ids:
        members = authenticated_request("GET", f"/admin/projects/{project_id}/members") or []
        for member in members:
            if isinstance(member, dict):
                # Check if member is active and within date range
                is_active = member.get("is_active", True)
                if not is_active:
                    continue
                
                assigned_from = member.get("assigned_from")
                assigned_to = member.get("assigned_to")
                
                # Check date range
                if assigned_from:
                    try:
                        from_date = date_type.fromisoformat(str(assigned_from)) if isinstance(assigned_from, str) else assigned_from
                        if selected_date < from_date:
                            continue
                    except:
                        pass
                
                if assigned_to:
                    try:
                        to_date = date_type.fromisoformat(str(assigned_to)) if isinstance(assigned_to, str) else assigned_to
                        if selected_date > to_date:
                            continue
                    except:
                        pass
                
                user_id = str(member.get("user_id") or member.get("id") or "")
                if user_id and user_id not in users_dict:
                    # Build user data from project member data
                    users_dict[user_id] = {
                        "id": user_id,
                        "user_id": user_id,
                        "name": member.get("name", "Unknown"),
                        "email": member.get("email", ""),
                        "work_role": member.get("work_role", ""),
                        "is_active": is_active,
                        "allocated_projects": 1,  # At least 1 since they're in a project
                        "today_status": "UNKNOWN",  # We don't have attendance data from this endpoint
                        "role": "USER",  # Default, we don't have this from project members
                        "shift_id": None,
                        "shift_name": None,
                        "rpm_user_id": None,
                    }
    
    return list(users_dict.values())

@st.cache_data(ttl=10, show_spinner="Loading metrics...")  # Reduced to 10 seconds for more real-time updates
def get_project_metrics_cached(project_id, start_date_str, end_date_str):
    """Cache project metrics for 10 seconds"""
    return authenticated_request("GET", "/admin/metrics/user_daily/", params={
        "project_id": project_id,
        "start_date": start_date_str,
        "end_date": end_date_str
    }) or []

@st.cache_data(ttl=10, show_spinner="Loading role counts...")  # Reduced to 10 seconds for more real-time updates
def get_project_role_counts_cached(project_id, target_date_str):
    """Cache project role counts for 10 seconds
    
    Returns role counts where each unique (user_id, work_role) combination is counted separately.
    This means if a user works in multiple roles, each role is counted.
    
    Args:
        project_id: UUID string of the project
        target_date_str: Date string in YYYY-MM-DD format
    """
    project_id_str = str(project_id) if project_id else None
    if not project_id_str:
        return None
    
    result = authenticated_request("GET", "/admin/project-resource-allocation/role-counts", params={
        "project_id": project_id_str,
        "target_date": target_date_str
    }, show_error=False)
    
    return result

@st.cache_data(ttl=10, show_spinner="Loading allocation data...")  # Reduced to 10 seconds for more real-time updates
def get_project_allocation_cached(project_id, target_date_str, only_active=True):
    """Cache project allocation for 10 seconds
    
    Args:
        project_id: UUID string of the project
        target_date_str: Date string in YYYY-MM-DD format
        only_active: If True, only return active project members (default: True)
    """
    project_id_str = str(project_id) if project_id else None
    if not project_id_str:
        return None
    
    result = authenticated_request("GET", "/admin/project-resource-allocation/", params={
        "project_id": project_id_str,
        "target_date": target_date_str,
        "only_active": only_active
    }, show_error=False)
    
    return result

def aggregate_by_user(rows):
    """Aggregate multiple rows for the same user into a single row"""
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

@st.cache_data(ttl=10, show_spinner="Loading weekly metrics...")  # Reduced to 10 seconds for more real-time updates
def get_user_daily_metrics_cached(user_id=None, project_ids=None, start_date_str=None, end_date_str=None):
    """Get user daily metrics for a date range"""
    params = {}
    if user_id:
        params["user_id"] = user_id
    if project_ids:
        # API might need project_id as a list, but let's fetch all and filter
        pass
    if start_date_str:
        params["start_date"] = start_date_str
    if end_date_str:
        params["end_date"] = end_date_str
    
    return authenticated_request("GET", "/admin/metrics/user_daily/", params=params) or []

# --- PAGE HEADER ---
st.title("📊 Team Stats")
st.markdown("Allocation count according to the status and roles of **your team** (people who share the same projects as you) including the total hours clocked, tasks performed, average time worked in a day. Use the project selector to view stats for a specific project or all projects combined.")
st.info("ℹ️ **Real-time Updates:** Data refreshes every 10 seconds automatically. Use the 'Refresh Data' button to see your latest tasks and hours immediately after completing work or after approval.")

# --- DATE SELECTOR AND REFRESH BUTTON ---
col_date, col_refresh = st.columns([3, 1])
with col_date:
    selected_date = st.date_input("Select Date", value=date.today(), max_value=date.today(), key="team_stats_date")
with col_refresh:
    st.write("")  # Spacing
    if st.button("🔄 Refresh Data", use_container_width=True, help="Clear cache and reload all data to see latest updates"):
        # Clear all relevant caches
        get_project_metrics_cached.clear()
        get_user_daily_metrics_cached.clear()
        get_team_members_cached.clear()
        get_user_projects_cached.clear()
        get_user_data_cached.clear()
        st.cache_data.clear()  # Clear all remaining caches
        st.success("✅ Cache cleared! Data will refresh...")
        time.sleep(0.5)
        st.rerun()

# --- GET USER'S PROJECTS AND TEAM MEMBERS ---
# Pass selected_date to get projects valid for that date
user_projects = get_user_projects_cached(reference_date=selected_date)
if not user_projects:
    st.warning("⚠️ You are not assigned to any projects. Team stats will be empty.")
    st.info("Please contact an administrator to be assigned to a project.")
    st.stop()

# Helper function to get project display name with fallback
def get_project_display_name(project):
    """Get project name with fallback to code or ID if name is missing"""
    name = project.get("name")
    if name and str(name).strip():
        return str(name).strip()
    
    # Log warning if name is missing (for debugging)
    project_id = project.get("id")
    code = project.get("code")
    print(f"[WARNING] Project {project_id} (code: {code}) has missing or empty name field")
    
    # Fallback to code if name is missing
    if code and str(code).strip():
        return f"{str(code).strip()} (No Name)"
    # Last resort: use ID
    if project_id:
        return f"Project {str(project_id)[:8]}"
    return "Unknown Project"

# --- PROJECT SELECTOR ---
project_options = ["All Projects"] + [get_project_display_name(p) for p in user_projects]
selected_project_name = st.selectbox(
    "Select Project",
    options=project_options,
    index=0,
    key="team_stats_project",
    help="Choose a specific project to view its team stats, or 'All Projects' to see combined stats"
)

# Determine which project(s) to use
if selected_project_name == "All Projects":
    selected_project_ids = [p["id"] for p in user_projects]
    selected_project = None
else:
    # Match by display name (handles cases where name might be missing)
    selected_project = next(
        (p for p in user_projects if get_project_display_name(p) == selected_project_name), 
        None
    )
    if selected_project:
        selected_project_ids = [selected_project["id"]]
    else:
        selected_project_ids = [p["id"] for p in user_projects]

st.markdown("---")

# Get team member IDs from selected project(s) (filter by selected date)
team_member_ids = get_team_members_cached(selected_project_ids, selected_date)

# Ensure current user is included in team members
current_user_id = None
if st.session_state.get("user"):
    user_obj = st.session_state.get("user")
    if isinstance(user_obj, dict):
        current_user_id = str(user_obj.get("id") or user_obj.get("user_id") or "")
    elif hasattr(user_obj, "id"):
        current_user_id = str(user_obj.id)
    
    if current_user_id and current_user_id not in team_member_ids:
        team_member_ids.add(current_user_id)

if not team_member_ids:
    st.warning("⚠️ No team members found in your projects.")
    st.stop()

# Display selected project info
if selected_project:
    display_name = get_project_display_name(selected_project)
    st.info(f"📁 **Viewing:** {display_name} (Your role: {selected_project.get('current_user_role', 'N/A')})")
else:
    with st.expander(f"📁 Your Projects ({len(user_projects)})", expanded=False):
        for proj in user_projects:
            display_name = get_project_display_name(proj)
            st.caption(f"• {display_name} (Your role: {proj.get('current_user_role', 'N/A')})")

# --- CALCULATE WEEKLY AVERAGES ---
# Calculate week start (Monday) and end (Sunday) for the selected date
week_start = selected_date - timedelta(days=selected_date.weekday())  # Monday
week_end = week_start + timedelta(days=6)  # Sunday

# Fetch metrics for the week
week_start_str = week_start.isoformat()
week_end_str = week_end.isoformat()

# Get current user's metrics for the week
user_weekly_metrics = []
if current_user_id:
    all_weekly_metrics = get_user_daily_metrics_cached(
        user_id=current_user_id,
        start_date_str=week_start_str,
        end_date_str=week_end_str
    )
    # Filter to only selected project(s)
    user_weekly_metrics = [
        m for m in all_weekly_metrics 
        if isinstance(m, dict) and str(m.get("project_id", "")) in selected_project_ids
    ]

# Calculate user's average hours per day for the week
user_total_hours_week = sum(float(m.get("hours_worked", 0) or 0) for m in user_weekly_metrics)
user_days_with_data = len(set(m.get("metric_date") for m in user_weekly_metrics if m.get("metric_date")))
user_avg_hours_per_day = user_total_hours_week / 7 if user_days_with_data > 0 else 0  # Average over 7 days

# Get teammates' metrics for the week (excluding current user)
teammates_weekly_metrics = []
teammate_ids = [tid for tid in team_member_ids if str(tid).lower().strip() != str(current_user_id).lower().strip()] if current_user_id else list(team_member_ids)

for team_member_id in teammate_ids:
    member_metrics = get_user_daily_metrics_cached(
        user_id=team_member_id,
        start_date_str=week_start_str,
        end_date_str=week_end_str
    )
    # Filter to only selected project(s)
    for m in member_metrics:
        if isinstance(m, dict):
            project_id = str(m.get("project_id", ""))
            if project_id in selected_project_ids:
                teammates_weekly_metrics.append(m)

# Calculate teammates' average hours per day for the week
# Group by user and date to avoid double counting across projects
teammates_hours_by_user_date = {}
for m in teammates_weekly_metrics:
    if isinstance(m, dict):
        user_id = str(m.get("user_id") or m.get("id") or "")
        metric_date = m.get("metric_date")
        hours = float(m.get("hours_worked", 0) or 0)
        if user_id and metric_date:
            key = f"{user_id}_{metric_date}"
            # Sum hours if user worked on multiple projects on same day
            teammates_hours_by_user_date[key] = teammates_hours_by_user_date.get(key, 0) + hours

# Calculate total hours for teammates across the week
teammates_total_hours_week = sum(teammates_hours_by_user_date.values())
# Average hours per teammate per day = total hours / (number of teammates * 7 days)
teammates_avg_hours_per_day = teammates_total_hours_week / (len(teammate_ids) * 7) if teammate_ids else 0

# Display Average Hours Metrics
st.markdown("### ⏱️ Average Working Hours")
col1, col2 = st.columns(2)

with col1:
    st.metric(
        label="My Average Hours/Day (This Week)",
        value=f"{user_avg_hours_per_day:.2f} hrs",
        help=f"Your average working hours per day for the week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
    )

with col2:
    st.metric(
        label="Teammates Average Hours/Day (This Week)",
        value=f"{teammates_avg_hours_per_day:.2f} hrs",
        help=f"Average working hours per day for your teammates (excluding you) for the week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
    )

st.markdown("---")

# --- FETCH DATA ---
# Use silent_fail=True so we don't show API error when fallback will succeed
users_data = get_users_with_filter_cached(selected_date.isoformat(), silent_fail=True)

# If users API failed, try fallback: get user data from project members
used_fallback = False
if not users_data and team_member_ids:
    users_data = get_user_data_from_project_members(selected_project_ids, selected_date)
    if users_data:
        used_fallback = True
        st.info(f"ℹ️ Showing {len(users_data)} team member(s) from your projects.")

# Only show "no data" if we have neither primary nor fallback data
if not users_data:
    st.info(f"ℹ️ No users data for date {selected_date.isoformat()}. This might be normal if there are no users in the system.")

# Ensure users_data is a list of dictionaries
if not isinstance(users_data, list):
    users_data = []

# Fetch task counts and hours per user early (needed for user list display)
date_str = selected_date.isoformat()
user_task_counts = {}  # Dictionary to store task counts per user: {user_id: total_tasks}
user_hours_counts = {}  # Dictionary to store hours per user: {user_id: total_hours}

for project_id in selected_project_ids:
    metrics = get_project_metrics_cached(project_id, date_str, date_str)
    if metrics:
        for m in metrics:
            tasks = int(m.get("tasks_completed", 0) or 0)
            hours = float(m.get("hours_worked", 0) or 0)
            user_id = str(m.get("user_id") or m.get("id") or "")
            if user_id:
                user_task_counts[user_id] = user_task_counts.get(user_id, 0) + tasks
                user_hours_counts[user_id] = user_hours_counts.get(user_id, 0) + hours
    else:
        # Debug: Show if no metrics found
        if len(selected_project_ids) == 1:
            st.info(f"ℹ️ No metrics found for project {selected_project_ids[0]} on {date_str}. This might be normal if no work was logged for this date.")

# Filter to only team members (users who share the same projects)
# Include all team members regardless of role (USER, ADMIN, etc.)
# Normalize team_member_ids for comparison (convert to lowercase set) - do this once
normalized_team_ids = {str(uid).lower().strip() for uid in team_member_ids}

user_role_users = []
for u in users_data:
    if not isinstance(u, dict):
        continue  # Skip non-dict items
    # Get user ID - could be "id" or "user_id" depending on API response
    # Normalize UUID to string for consistent comparison
    user_id_raw = u.get("id") or u.get("user_id") or ""
    user_id = str(user_id_raw).lower().strip() if user_id_raw else ""
    
    # Only include if user is in the team (shares same projects)
    if user_id and user_id in normalized_team_ids:
        user_role_users.append(u)

# Debug: Show filtering results
if not user_role_users and users_data:
    st.warning(f"⚠️ Found {len(users_data)} users from API, but none match your team members.")
    st.info(f"🔍 **Debug Info:**\n- Team member IDs found: {len(team_member_ids)}\n- Users from API: {len(users_data)}\n- First 3 team member IDs: {list(team_member_ids)[:3] if team_member_ids else 'None'}\n- First 3 user IDs from API: {[str(u.get('id') or u.get('user_id') or '') for u in users_data[:3]]}")
    
    # Try to help: show if there's a format mismatch
    if team_member_ids:
        sample_team_id = list(team_member_ids)[0]
        sample_user_ids = [str(u.get("id") or u.get("user_id") or "") for u in users_data[:3] if u.get("id") or u.get("user_id")]
        if sample_user_ids:
            st.caption(f"💡 **Tip:** Check if IDs match format. Team ID sample: `{sample_team_id}` vs User ID sample: `{sample_user_ids[0]}`")
elif not user_role_users and not users_data:
    st.warning("⚠️ No users data and no team members found.")
    if team_member_ids:
        st.info(f"ℹ️ Found {len(team_member_ids)} team member(s) in your projects for this date, but could not load their details.")

# Also filter to only show USER role for the main display (but keep all for team membership)
# This ensures we show all team members, not just those with role='USER'

# Calculate counts
total_users = len(user_role_users)
allocated_users = [u for u in user_role_users if u.get("allocated_projects", 0) > 0]
not_allocated_users = [u for u in user_role_users if u.get("allocated_projects", 0) == 0]
present_users = [u for u in user_role_users if u.get("today_status") == "PRESENT"]
absent_users = [u for u in user_role_users if u.get("today_status") == "ABSENT"]
unknown_users = [u for u in user_role_users if u.get("today_status") == "UNKNOWN" or not u.get("today_status")]

# --- SECTION 1: TEAM OVERVIEW METRICS ---
st.markdown("## 👥 Team Overview")
if selected_project:
    display_name = get_project_display_name(selected_project)
    st.markdown(f"Dashboard showing team members for **{display_name}** - total count, present, and absent")
else:
    st.markdown("Dashboard showing your team members (people who share the same projects as you) - total count, present, and absent")

# Display clickable metrics
col1, col2, col3 = st.columns(3)

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

# Show exportable list when a button is clicked
if st.session_state.show_user_list and st.session_state.user_list_data:
    list_title = {
        "total": "All Users (Role: USER)",
        "present": "Present Users",
        "absent": "Absent Users"
    }.get(st.session_state.show_user_list, "Users")
    
    st.markdown(f"### 📋 {list_title}")
    
    # Add task counts to user data
    user_list_with_tasks = []
    for user in st.session_state.user_list_data:
        user_id = str(user.get("id") or user.get("user_id") or "")
        tasks_count = user_task_counts.get(user_id, 0)
        user_copy = user.copy()
        user_copy["tasks_completed"] = tasks_count
        user_list_with_tasks.append(user_copy)
    
    df_users = pd.DataFrame(user_list_with_tasks)
    if not df_users.empty:
        # Reorder columns to show tasks_completed prominently
        if "tasks_completed" in df_users.columns:
            cols = ["name", "email", "tasks_completed"] + [c for c in df_users.columns if c not in ["name", "email", "tasks_completed"]]
            cols = [c for c in cols if c in df_users.columns]  # Only include existing columns
            df_users = df_users[cols]
        st.dataframe(df_users, use_container_width=True, height=300)
        export_csv(f"{list_title.replace(' ', '_')}_{selected_date}.csv", user_list_with_tasks)
    else:
        st.info("No users found.")
    
    if st.button("Close", key="close_user_list"):
        st.session_state.show_user_list = None
        st.session_state.user_list_data = []
        st.rerun()

st.markdown("---")

# --- SECTION 2: ROLE ALLOCATION BREAKDOWN ---
st.markdown("## 📊 Role Allocation Breakdown")
st.markdown("Allocation count according to the status and roles of **your team** (people who share the same projects as you)")

# Group users by work_role from metrics data (not user data)
# First, get all unique work_roles from metrics for the selected date and project(s)
role_stats = {}
role_user_mapping = {}  # Track which users belong to which roles based on metrics

# Build role distribution from metrics data
for project_id in selected_project_ids:
    metrics = get_project_metrics_cached(project_id, date_str, date_str)
    if metrics:
        for m in metrics:
            if isinstance(m, dict):
                work_role = m.get("work_role")
                user_id = str(m.get("user_id") or m.get("id") or "")
                
                # Skip if no role or user_id
                if not work_role or not user_id:
                    continue
                
                work_role = str(work_role).strip()
                if not work_role:
                    continue
                
                # Track which users have this role
                if work_role not in role_user_mapping:
                    role_user_mapping[work_role] = set()
                role_user_mapping[work_role].add(user_id)
                
                # Initialize role_stats if not exists
                if work_role not in role_stats:
                    role_stats[work_role] = {
                        "total": 0,
                        "present": 0,
                        "absent": 0,
                        "unknown": 0,
                        "allocated": 0,
                        "not_allocated": 0
                    }

# Now count users per role and their status
for work_role, user_ids in role_user_mapping.items():
    for user_id in user_ids:
        # Find the user in user_role_users
        user = next((u for u in user_role_users if str(u.get("id") or u.get("user_id") or "") == user_id), None)
        if user:
            role_stats[work_role]["total"] += 1
            status = user.get("today_status", "UNKNOWN")
            allocated = user.get("allocated_projects", 0) > 0
            
            if status == "PRESENT":
                role_stats[work_role]["present"] += 1
            elif status == "ABSENT":
                role_stats[work_role]["absent"] += 1
            else:
                role_stats[work_role]["unknown"] += 1
            
            if allocated:
                role_stats[work_role]["allocated"] += 1
            else:
                role_stats[work_role]["not_allocated"] += 1

# Display role breakdown table
if role_stats:
    role_df = pd.DataFrame([
        {
            "Role": role,
            "Total": stats["total"],
            "Present": stats["present"],
            "Absent": stats["absent"],
            "Unknown": stats["unknown"],
            "Allocated": stats["allocated"],
            "Not Allocated": stats["not_allocated"]
        }
        for role, stats in role_stats.items()
    ])
    st.dataframe(role_df, use_container_width=True, hide_index=True)
    export_csv(f"Role_Allocation_{selected_date}.csv", role_df.to_dict('records'))
else:
    st.info("No role allocation data available.")

st.markdown("---")

# --- SECTION 3: OVERALL STATISTICS ---
st.markdown("## 📈 Overall Statistics")
if selected_project:
    display_name = get_project_display_name(selected_project)
    st.markdown(f"Total hours clocked, tasks performed, and average time worked in a day for **{display_name}**")
else:
    st.markdown("Total hours clocked, tasks performed, and average time worked in a day for **your team's projects**")

# Fetch metrics only for selected project(s)
project_ids = selected_project_ids

# Fetch user daily metrics for all projects (reuse date_str and user_task_counts from above)
total_hours = 0
total_tasks = 0
total_days_with_work = 0
metrics_data = []

for project_id in project_ids:
    metrics = get_project_metrics_cached(project_id, date_str, date_str)
    if metrics:
        for m in metrics:
            hours = float(m.get("hours_worked", 0) or 0)
            tasks = int(m.get("tasks_completed", 0) or 0)
            total_hours += hours
            total_tasks += tasks
            if hours > 0:
                total_days_with_work += 1
            metrics_data.append(m)

# Calculate average hours per day (for users who worked)
avg_hours_per_day = total_hours / total_days_with_work if total_days_with_work > 0 else 0

# Display counters
counter_col1, counter_col2, counter_col3 = st.columns(3)
with counter_col1:
    st.metric("Total Hours Worked", f"{total_hours:.2f} hrs")
with counter_col2:
    st.metric("Total Tasks Completed", f"{int(total_tasks)}")
with counter_col3:
    st.metric("Average Time Worked (per day)", f"{avg_hours_per_day:.2f} hrs")

st.markdown("---")

# --- SECTION 4: PROJECT CARDS ---
st.markdown("## 📁 Project Cards")
if selected_project:
    display_name = get_project_display_name(selected_project)
    st.markdown(f"Project card showing total number of tasks performed, total hours clocked, and count of different roles for **{display_name}**")
else:
    st.markdown("Project cards showing total number of tasks performed, total hours clocked, and count of different roles for **your projects**")

# Fetch project data with metrics (only for selected project(s))
projects_with_metrics = []
date_str = selected_date.isoformat()

# Get projects to display
projects_to_display = [selected_project] if selected_project else user_projects

for project in projects_to_display:
    project_id = project["id"]
    
    # Get metrics for this project
    project_metrics = get_project_metrics_cached(project_id, date_str, date_str)
    
    # Calculate totals
    proj_total_tasks = sum(int(m.get("tasks_completed", 0) or 0) for m in project_metrics)
    proj_total_hours = sum(float(m.get("hours_worked", 0) or 0) for m in project_metrics)
    
    # Count roles from metrics (shows allocated roles from ProjectMember)
    role_counts = {}
    for m in project_metrics:
        role = m.get("work_role", "Unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
    
    projects_with_metrics.append({
        "project": project,
        "total_tasks": proj_total_tasks,
        "total_hours": proj_total_hours,
        "role_counts": role_counts,
        "metrics": project_metrics
    })

# Display project cards in a grid
num_cols = 3
for i in range(0, len(projects_with_metrics), num_cols):
    cols = st.columns(num_cols)
    for j, col in enumerate(cols):
        if i + j < len(projects_with_metrics):
            proj_data = projects_with_metrics[i + j]
            proj = proj_data["project"]
            
            with col:
                with st.container(border=True):
                    display_name = get_project_display_name(proj)
                    st.markdown(f"### {display_name}")
                    
                    # Metrics
                    metric_col1, metric_col2 = st.columns(2)
                    with metric_col1:
                        st.metric("Tasks", proj_data['total_tasks'])
                    with metric_col2:
                        st.metric("Hours", f"{proj_data['total_hours']:.1f}")
                    
                    # Role counts
                    st.markdown("**Role Counts:**")
                    roles_list = list(proj_data["role_counts"].items())
                    max_visible_roles = 4
                    
                    visible_roles = roles_list[:max_visible_roles]
                    for role, count in visible_roles:
                        st.caption(f"• {role}: {count}")
                    
                    # Show remaining roles in expander if there are more than 4
                    if len(roles_list) > max_visible_roles:
                        remaining_count = len(roles_list) - max_visible_roles
                        with st.expander(f"➕ {remaining_count} more role(s)"):
                            for role, count in roles_list[max_visible_roles:]:
                                st.caption(f"• {role}: {count}")

st.markdown("---")

# --- SECTION 5: VISUALIZATIONS ---
st.markdown("## 📊 Visualizations")

viz_col1, viz_col2 = st.columns(2)

with viz_col1:
    # Role distribution pie chart
    if role_stats:
        role_names = [str(r) if r else "Unknown" for r in role_stats.keys()]
        role_totals = [stats["total"] for stats in role_stats.values()]
        fig_roles = px.pie(
            values=role_totals,
            names=role_names,
            title="Team Distribution by Role",
            labels={"names": "Role", "values": "Count"}
        )
        fig_roles.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_roles, use_container_width=True)

with viz_col2:
    # Status distribution
    status_data = {
        "Present": len(present_users),
        "Absent": len(absent_users),
        "Unknown": len(unknown_users)
    }
    if sum(status_data.values()) > 0:
        fig_status = px.bar(
            x=list(status_data.keys()),
            y=list(status_data.values()),
            title="Team Status Distribution",
            labels={"x": "Status", "y": "Count"}
        )
        st.plotly_chart(fig_status, use_container_width=True)

# Tasks and Hours by Team Members Bar Charts
if user_role_users and (user_task_counts or user_hours_counts):
    # Prepare data for both tasks and hours comparison
    member_data = []
    for user in user_role_users:
        user_id = str(user.get("id") or user.get("user_id") or "")
        user_name = user.get("name", user.get("email", "Unknown"))
        tasks = user_task_counts.get(user_id, 0)
        hours = user_hours_counts.get(user_id, 0)
        member_data.append({
            "name": user_name,
            "tasks": tasks,
            "hours": hours
        })
    
    if member_data:
        # Tasks Chart
        member_tasks_data = sorted(member_data, key=lambda x: x["tasks"], reverse=True)
        member_names_tasks = [d["name"] for d in member_tasks_data]
        member_tasks = [d["tasks"] for d in member_tasks_data]
        
        fig_member_tasks = px.bar(
            x=member_names_tasks,
            y=member_tasks,
            title="Tasks Completed by Team Members",
            labels={"x": "Team Member", "y": "Tasks Completed"},
            text=member_tasks  # Show values on bars
        )
        fig_member_tasks.update_traces(texttemplate='%{text}', textposition='outside')
        fig_member_tasks.update_layout(
            xaxis_title="Team Member",
            yaxis_title="Tasks Completed",
            xaxis_tickangle=-45 if len(member_names_tasks) > 5 else 0
        )
        st.plotly_chart(fig_member_tasks, use_container_width=True)
        
        # Hours Chart
        member_hours_data = sorted(member_data, key=lambda x: x["hours"], reverse=True)
        member_names_hours = [d["name"] for d in member_hours_data]
        member_hours = [round(d["hours"], 2) for d in member_hours_data]
        
        fig_member_hours = px.bar(
            x=member_names_hours,
            y=member_hours,
            title="Hours Worked by Team Members",
            labels={"x": "Team Member", "y": "Hours Worked"},
            text=member_hours  # Show values on bars
        )
        fig_member_hours.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig_member_hours.update_layout(
            xaxis_title="Team Member",
            yaxis_title="Hours Worked",
            xaxis_tickangle=-45 if len(member_names_hours) > 5 else 0
        )
        st.plotly_chart(fig_member_hours, use_container_width=True)

st.markdown("---")

# Hours and Tasks by Project
if projects_with_metrics:
    proj_names = [get_project_display_name(p["project"]) for p in projects_with_metrics]
    proj_hours = [p["total_hours"] for p in projects_with_metrics]
    proj_tasks = [p["total_tasks"] for p in projects_with_metrics]
    
    fig_projects = go.Figure()
    fig_projects.add_trace(go.Bar(
        x=proj_names,
        y=proj_hours,
        name="Hours",
        yaxis="y",
        offsetgroup=1,
        text=proj_hours,
        textposition='outside'
    ))
    fig_projects.add_trace(go.Bar(
        x=proj_names,
        y=proj_tasks,
        name="Tasks",
        yaxis="y2",
        offsetgroup=2,
        text=proj_tasks,
        textposition='outside'
    ))
    fig_projects.update_layout(
        title="Hours and Tasks by Project",
        xaxis_title="Project",
        yaxis_title="Hours",
        yaxis2=dict(title="Tasks", overlaying="y", side="right"),
        barmode="group"
    )
    st.plotly_chart(fig_projects, use_container_width=True)
