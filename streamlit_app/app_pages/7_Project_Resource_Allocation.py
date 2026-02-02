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
from role_guard import get_user_role
import base64

load_dotenv()

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(
    page_title="Project Resource Allocation",
    layout="wide",
)

# Basic role check
role = get_user_role()
if not role or role not in ["ADMIN", "MANAGER"]:
    st.error("Access denied. Admin or Manager role required.")
    st.stop()

# Add CSS and JavaScript to style dialogs: 90vw width, centered, prevent double scroll
st.markdown("""
<style>
/* Target all possible dialog selectors - center and set width */
div[data-testid="stDialog"],
section[data-testid="stDialog"] {
    width: 90vw !important;
    max-width: 90vw !important;
    min-width: 90vw !important;
    position: fixed !important;
    left: 50% !important;
    top: 35% !important;
    transform: translate(-50%, -50%) !important;
    z-index: 10000 !important;
    overflow: visible !important;
    max-height: none !important;
}

/* Prevent scroll on dialog containers - fix double scroll */
div[data-testid="stDialog"] > div,
section[data-testid="stDialog"] > div {
    width: 90vw !important;
    max-width: 90vw !important;
    min-width: 90vw !important;
    overflow-y: hidden !important;
    overflow-x: hidden !important;
    max-height: none !important;
}

/* Prevent scroll on inner sections */
div[data-testid="stDialog"] > section,
section[data-testid="stDialog"] > section {
    overflow: hidden !important;
    max-height: none !important;
}

/* Prevent body scroll when dialog is open */
body:has(div[data-testid="stDialog"]) {
    overflow: hidden !important;
}

/* Allow scrolling only for dataframes inside dialog */
div[data-testid="stDialog"] [data-testid="stDataFrame"],
section[data-testid="stDialog"] [data-testid="stDataFrame"] {
    max-height: 60vh !important;
    overflow-y: auto !important;
    overflow-x: auto !important;
}

/* Remove any nested scroll containers */
div[data-testid="stDialog"] [style*="overflow"],
section[data-testid="stDialog"] [style*="overflow"] {
    overflow: visible !important;
}
</style>
<script>
// Apply width aggressively - target all dialog elements
function applyDialogWidth() {
    var dialogs = document.querySelectorAll('div[data-testid="stDialog"], section[data-testid="stDialog"], div[role="dialog"], section[role="dialog"]');
    dialogs.forEach(function(dialog) {
        // Set width using multiple methods
        dialog.style.width = '90vw';
        dialog.style.maxWidth = '90vw';
        dialog.style.minWidth = '90vw';
        dialog.style.setProperty('width', '90vw', 'important');
        dialog.style.setProperty('max-width', '90vw', 'important');
        dialog.style.setProperty('min-width', '90vw', 'important');
        
        // Also set on first child if it exists
        if (dialog.firstElementChild) {
            dialog.firstElementChild.style.setProperty('width', '90vw', 'important');
            dialog.firstElementChild.style.setProperty('max-width', '90vw', 'important');
        }
    });
}

// Run immediately and on interval
applyDialogWidth();
setInterval(applyDialogWidth, 50);

// Run when DOM changes
var observer = new MutationObserver(applyDialogWidth);
observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style'] });
</script>
""", unsafe_allow_html=True)

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
    # Don't retry on 500 errors - if server is broken, retrying won't help
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=10,
        max_retries=requests.adapters.Retry(
            total=1,  # Reduced retries
            backoff_factor=0.3,
            status_forcelist=[502, 503, 504],  # Removed 500 - don't retry on server errors
            allowed_methods=["GET", "POST"]
        )
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
                error_detail = f"API Error {r.status_code}"
                try:
                    error_response = r.json()
                    if isinstance(error_response, dict) and "detail" in error_response:
                        error_detail = error_response["detail"]
                    print(f"[API Error Response] {method} {endpoint}: {error_response}")
                except:
                    error_detail = r.text[:500] if r.text else f"HTTP {r.status_code}"
                    print(f"[API Error Text] {method} {endpoint}: {error_detail}")
                
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
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
                # Exponential backoff: 1s, 2s, 4s
                wait_time = min(2 ** attempt, 4)
                time.sleep(wait_time)
                continue
            print(f"[Connection Error] {method} {endpoint}: {str(e)}")
            if show_error:
                st.error(f"⚠️ Connection Error: {str(e)}")
            return None
        except requests.exceptions.HTTPError as e:
            # Handle HTTP errors (like too many 500s)
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            error_msg = str(e)
            print(f"[HTTP Error] {method} {endpoint}: {error_msg}")
            if show_error:
                if "500" in error_msg or "too many" in error_msg.lower():
                    st.error(f"⚠️ **API Server Error**: The API server at `{API_BASE_URL}` is returning errors. Please check:\n"
                            f"1. Is the API server running?\n"
                            f"2. Check API server logs for errors\n"
                            f"3. Verify database connection\n"
                            f"4. Check API server console for stack traces")
                else:
                    st.error(f"⚠️ Request Error: {error_msg}")
            return None
        except Exception as e:
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            error_msg = str(e)
            print(f"[Request Error] {method} {endpoint}: {error_msg}")
            if show_error:
                if "500" in error_msg or "too many" in error_msg.lower() or "ConnectionPool" in error_msg:
                    st.error(f"⚠️ **API Server Issue**: The API server appears to be having problems.\n"
                            f"- Server: `{API_BASE_URL}`\n"
                            f"- Error: {error_msg}\n\n"
                            f"**Please check:**\n"
                            f"1. Is the API server running? (Check terminal/console where you started it)\n"
                            f"2. Check API server logs for error messages\n"
                            f"3. Restart the API server if needed")
                else:
                    st.error(f"⚠️ Request Error: {error_msg}")
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
    users = authenticated_request("GET", "/admin/users/", params={"limit": 1000}, show_error=False)
    if not users:
        print(f"[DEBUG] get_user_name_mapping: API returned empty, returning empty dict")
        return {}
    mapping = {str(user["id"]): user.get("name", "Unknown") for user in users if isinstance(user, dict)}
    print(f"[DEBUG] get_user_name_mapping: Created mapping with {len(mapping)} users")
    return mapping

def get_user_name_mapping_from_data(users_data):
    """Create user name mapping from existing users_data (fallback when API fails)
    Stores both original and lowercase versions of IDs for better matching"""
    if not users_data:
        print(f"[DEBUG] get_user_name_mapping_from_data: No users_data provided")
        return {}
    mapping = {}
    for user in users_data:
        if isinstance(user, dict):
            # Try multiple ways to get user_id
            user_id = str(user.get("id") or user.get("user_id") or "")
            user_name = user.get("name", "Unknown")
            if user_id and user_id != "None" and user_id != "":
                # Store with both original and lowercase key for better matching
                mapping[user_id] = user_name
                mapping[user_id.lower()] = user_name  # Also store lowercase version
                mapping[user_id.upper()] = user_name  # Also store uppercase version
            else:
                print(f"[DEBUG] get_user_name_mapping_from_data: Skipping user with no valid ID: {user}")
    print(f"[DEBUG] get_user_name_mapping_from_data: Created mapping with {len(set(mapping.values()))} unique users (with {len(mapping)} ID variants)")
    if len(mapping) > 0:
        # Get unique user names
        unique_names = list(set(mapping.values()))[:3]
        print(f"[DEBUG] Sample user names: {unique_names}")
    return mapping

@st.cache_data(ttl=30, show_spinner="Loading user data...")
def get_users_with_filter_cached(selected_date_str, silent_fail=False):
    """Cache user data for 30 seconds. If silent_fail=True, don't show API error in UI (for fallback flow)."""
    response = authenticated_request(
        "POST", 
        "/admin/users/users_with_filter",
        json_data={"date": selected_date_str},
        show_error=not silent_fail
    )
    # API returns {"items": [...], "meta": {...}}
    if response and isinstance(response, dict) and "items" in response:
        items = response["items"]
        print(f"[DEBUG] Primary API: Got {len(items)} users from users_with_filter")
        return items
    # If response is None, API call failed (error shown only if not silent_fail)
    print(f"[DEBUG] Primary API: Failed or returned empty. Response: {response}")
    return []

def get_users_fallback():
    """Fallback: Get users from simpler /admin/users/ endpoint if users_with_filter fails"""
    users = authenticated_request("GET", "/admin/users/", params={"limit": 1000}, show_error=False) or []
    print(f"[DEBUG] Fallback: Got {len(users)} users from /admin/users/ endpoint")
    # Convert to same format as users_with_filter returns
    # Add default values for fields that users_with_filter provides
    result = []
    for user in users:
        if isinstance(user, dict):
            # Handle role - could be enum, string, or enum value
            role = user.get("role")
            if hasattr(role, 'value'):
                role_value = role.value
            elif hasattr(role, '__str__'):
                role_value = str(role)
            else:
                role_value = role if role else "USER"
            
            result.append({
                "id": user.get("id"),
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "role": role_value,  # Use actual role, not default
                "work_role": user.get("work_role", ""),
                "is_active": user.get("is_active", True),
                "allocated_projects": 0,  # We don't have this from simple endpoint
                "today_status": "ABSENT",  # Default to ABSENT if no attendance data
                "shift_id": user.get("default_shift_id"),
                "shift_name": None,
                "rpm_user_id": user.get("rpm_user_id"),
            })
    print(f"[DEBUG] Fallback: Converted to {len(result)} user objects")
    return result

@st.cache_data(ttl=10, show_spinner="Loading metrics...")  # Reduced to 10 seconds for more real-time updates
def get_project_metrics_cached(project_id, start_date_str, end_date_str):
    """Cache project metrics for 1 minute"""
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
    """Cache project allocation for 1 minute
    
    Args:
        project_id: UUID string of the project
        target_date_str: Date string in YYYY-MM-DD format
        only_active: If True, only return active project members (default: True)
    """
    # Convert project_id to string if it's a UUID object
    project_id_str = str(project_id) if project_id else None
    if not project_id_str:
        print(f"[ERROR] get_project_allocation_cached: project_id is None or empty")
        return None
    
    result = authenticated_request("GET", "/admin/project-resource-allocation/", params={
        "project_id": project_id_str,
        "target_date": target_date_str,
        "only_active": only_active
    }, show_error=False)  # Don't show error in UI, we'll handle it in the calling code
    
    if result:
        print(f"[DEBUG] get_project_allocation_cached: project_id={project_id_str}, date={target_date_str}, only_active={only_active}, "
              f"total_resources={result.get('total_resources')}, resources_count={len(result.get('resources', []))}")
    else:
        print(f"[DEBUG] get_project_allocation_cached: project_id={project_id_str}, date={target_date_str}, API returned None")
    return result

@st.cache_data(ttl=60, show_spinner="Loading user projects mapping...")
def get_user_projects_mapping_cached(target_date_str):
    """Cache user to projects mapping for 1 minute
    Returns a dictionary mapping user_id (as string) to list of project names
    
    Args:
        target_date_str: Date string in YYYY-MM-DD format
    """
    all_projects = get_all_projects_cached()
    user_projects_map = {}
    
    # For each project, get allocation data and map users to project names
    for project in all_projects:
        project_id = project.get("id")
        project_name = project.get("name", "Unknown Project")
        
        if not project_id:
            continue
        
        # Get allocation data for this project
        allocation_data = get_project_allocation_cached(project_id, target_date_str, only_active=True)
        
        if allocation_data and allocation_data.get("resources"):
            for resource in allocation_data["resources"]:
                user_id = str(resource.get("user_id", "")).strip()
                if user_id and user_id != "None":
                    # Store with multiple ID format variants for better matching
                    if user_id not in user_projects_map:
                        user_projects_map[user_id] = []
                    if project_name not in user_projects_map[user_id]:
                        user_projects_map[user_id].append(project_name)
                    
                    # Also store with lowercase and no-dash variants
                    user_id_lower = user_id.lower()
                    user_id_no_dashes = user_id.replace("-", "")
                    if user_id_lower not in user_projects_map:
                        user_projects_map[user_id_lower] = []
                    if project_name not in user_projects_map[user_id_lower]:
                        user_projects_map[user_id_lower].append(project_name)
                    
                    if user_id_no_dashes not in user_projects_map:
                        user_projects_map[user_id_no_dashes] = []
                    if project_name not in user_projects_map[user_id_no_dashes]:
                        user_projects_map[user_id_no_dashes].append(project_name)
    
    print(f"[DEBUG] get_user_projects_mapping_cached: Created mapping for {len(set([k for k in user_projects_map.keys() if not k.islower() and '-' in k]))} unique users")
    return user_projects_map


# ---------------------------------------------------------
# AUTH GUARD
# ---------------------------------------------------------
if "token" not in st.session_state:
    st.warning("🔒 Please login first from the main page.")
    st.stop()

authenticated_request("GET", "/me/")

# ---------------------------------------------------------
# INITIALIZE POPUP STATES (Reset on page load)
# ---------------------------------------------------------
# Use a unique key to detect fresh page loads
if "allocation_page_init" not in st.session_state:
    st.session_state.allocation_page_init = True
    # Reset all popup states on fresh page load
    st.session_state.show_user_list = None
    st.session_state.user_list_data = []
    st.session_state.show_project_list = None
    st.session_state.project_list_data = None
    st.session_state.show_allocation_popup = False
    st.session_state.allocation_popup_data = None
    if "selected_role" in st.session_state:
        st.session_state.selected_role = None

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
st.title("📊 Project Resource Allocation Dashboard")
st.caption("Comprehensive resource allocation, attendance, and productivity overview")
st.info("ℹ️ **Real-time Updates:** Data refreshes every 10 seconds automatically. Use the 'Refresh Data' button to see your latest tasks and hours immediately after completing work.")
st.markdown("---")

# ---------------------------------------------------------
# DATE SELECTOR (Global) AND REFRESH BUTTON
# ---------------------------------------------------------
col_date, col_refresh = st.columns([4, 1])
with col_date:
    selected_date = st.date_input("Select Date", value=date.today(), max_value=date.today(), key="allocation_date")
with col_refresh:
    st.write("")  # Spacing
    if st.button("🔄 Refresh Data", use_container_width=True, help="Clear cache and reload all data to see latest updates"):
        # Clear all relevant caches
        get_all_projects_cached.clear()
        get_project_metrics_cached.clear()
        get_project_allocation_cached.clear()
        get_user_projects_mapping_cached.clear()
        get_users_with_filter_cached.clear()
        get_user_name_mapping.clear()
        st.cache_data.clear()  # Clear all remaining caches
        st.success("✅ Cache cleared! Data will refresh...")
        time.sleep(0.5)
        st.rerun()

# ---------------------------------------------------------
# TABS
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 Overview Dashboard", "📈 Visualizations", "🔍 Detailed Project View"])

# ==========================================
# TAB 1: OVERVIEW DASHBOARD
# ==========================================
with tab1:
    # Fetch all users with role='USER' using cached function
    # Use silent_fail=True so we don't show API error when fallback will succeed
    users_data = get_users_with_filter_cached(selected_date.isoformat(), silent_fail=True)
    print(f"[DEBUG] After primary API: users_data length = {len(users_data) if users_data else 0}")
    
    # Debug: Print status of first few users
    if users_data:
        print(f"[DEBUG STATUS] Sample user statuses:")
        for u in users_data[:5]:
            print(f"  - {u.get('name', 'Unknown')}: status={u.get('today_status', 'N/A')}, role={u.get('role', 'N/A')}")
    
    # If users API failed, try fallback: get users from simpler endpoint
    used_fallback = False
    if not users_data:
        print(f"[DEBUG] Primary API returned empty, trying fallback...")
        # Clear cache for primary API to force fresh call next time
        get_users_with_filter_cached.clear()
        users_data = get_users_fallback()
        print(f"[DEBUG] After fallback: users_data length = {len(users_data) if users_data else 0}")
        if users_data:
            used_fallback = True
            st.info(f"ℹ️ Showing {len(users_data)} user(s) from basic user list (detailed filter unavailable).")
        else:
            # If fallback also fails, try the user name mapping endpoint which we know works
            print(f"[DEBUG] Fallback also empty, trying get_user_name_mapping...")
            name_mapping = get_user_name_mapping()
            if name_mapping:
                # Convert name mapping back to user list format
                users_data = []
                for user_id, name in name_mapping.items():
                    users_data.append({
                        "id": user_id,
                        "name": name,
                        "email": "",
                        "role": "USER",  # Assume USER role
                        "work_role": "",
                        "is_active": True,
                        "allocated_projects": 0,
                        "today_status": "ABSENT",
                        "shift_id": None,
                        "shift_name": None,
                        "rpm_user_id": None,
                    })
                print(f"[DEBUG] Got {len(users_data)} users from name mapping")
                if users_data:
                    st.info(f"ℹ️ Showing {len(users_data)} user(s) from user name list.")
    
    # Ensure users_data is a list of dictionaries
    if not isinstance(users_data, list):
        users_data = []
    
    # Debug: Show what we got
    if not users_data:
        st.error(f"⚠️ **No users data available**\n\n"
                f"The API server at `{API_BASE_URL}` is not responding correctly. All endpoints failed:\n"
                f"- Primary endpoint: `/admin/users/users_with_filter` ❌\n"
                f"- Fallback endpoint: `/admin/users/` ❌\n\n"
                f"**This indicates the API server has a problem.** Please:\n"
                f"1. Check if the API server is running\n"
                f"2. Check API server terminal/console for error messages\n"
                f"3. Verify the API server can connect to the database\n"
                f"4. Restart the API server\n\n"
                f"*The page cannot function without a working API server.*")
        print(f"[DEBUG] No users_data returned. Primary API failed, fallback also returned empty.")
    
    # Filter users with role='USER' or role='ADMIN' - handle both string and enum role values
    user_role_users = []
    for u in users_data:
        if not isinstance(u, dict):
            continue  # Skip non-dict items
        role = u.get("role")
        # Handle role as string, enum, or enum value
        if hasattr(role, 'value'):
            role_str = str(role.value).upper()
        else:
            role_str = str(role).upper() if role else ""
        
        # Only print first few for debugging
        if len(user_role_users) < 3:
            print(f"[DEBUG] User {u.get('name', 'Unknown')}: role={role}, role_str={role_str}")
        
        # Include both USER and ADMIN roles
        if role_str == "USER" or role_str == "ADMIN":
            user_role_users.append(u)
    
    # Debug: Show filtering results
    if users_data and not user_role_users:
        st.warning(f"⚠️ Found {len(users_data)} user(s) but none have role='USER' or 'ADMIN'. Showing all users instead.")
        # If no USER/ADMIN role users found, show all users
        user_role_users = users_data
        sample_roles = [str(u.get('role', 'N/A')) for u in users_data[:5]]
        print(f"[DEBUG] No users with role='USER' or 'ADMIN' found. Roles found: {sample_roles}")
    
    # Calculate counts
    total_users = len(user_role_users)
    print(f"[DEBUG] Final total_users count: {total_users}")
    print(f"[DEBUG] Sample user data: {user_role_users[0] if user_role_users else 'No users'}")
    
    allocated_users = [u for u in user_role_users if u.get("allocated_projects", 0) > 0]
    not_allocated_users = [u for u in user_role_users if u.get("allocated_projects", 0) == 0]
        # Fetch weekoffs for users to identify weekoff users
    # Get today's weekday name (e.g., "MONDAY", "SUNDAY")
    today_weekday = selected_date.strftime("%A").upper()
    
    # Fetch full user data with weekoffs from /admin/users/ endpoint
    all_users_with_weekoffs = authenticated_request("GET", "/admin/users/", params={"limit": 1000}, show_error=False) or []
    
    # Create a mapping of user_id to weekoffs (store multiple ID formats for matching)
    user_weekoffs_map = {}
    user_id_variants_map = {}  # Map all ID variants to canonical ID
    
    for user in all_users_with_weekoffs:
        if isinstance(user, dict):
            user_id = str(user.get("id", "")).strip()
            if not user_id or user_id == "None":
                continue
                
            weekoffs = user.get("weekoffs", [])
            # Convert weekoffs to list of strings - handle various formats
            weekoff_strings = []
            if weekoffs:
                for w in weekoffs:
                    weekoff_value = None
                    # Handle different formats: string, enum object, dict
                    if isinstance(w, str):
                        weekoff_value = w.upper().strip()
                    elif isinstance(w, dict):
                        # Pydantic might serialize enum as {"value": "SATURDAY"} or {"name": "SATURDAY"}
                        weekoff_value = (w.get("value") or w.get("name") or "").upper().strip()
                    elif hasattr(w, 'value'):
                        weekoff_value = str(w.value).upper().strip()
                    elif hasattr(w, 'name'):
                        weekoff_value = str(w.name).upper().strip()
                    elif hasattr(w, '__str__'):
                        weekoff_value = str(w).upper().strip()
                    
                    if weekoff_value and weekoff_value in ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]:
                        weekoff_strings.append(weekoff_value)
            
            if weekoff_strings:
                # Store with canonical ID
                user_weekoffs_map[user_id] = weekoff_strings
                # Also store ID variants for flexible matching
                user_id_lower = user_id.lower()
                user_id_upper = user_id.upper()
                user_id_no_dashes = user_id.replace("-", "")
                user_id_variants_map[user_id_lower] = user_id
                user_id_variants_map[user_id_upper] = user_id
                user_id_variants_map[user_id_no_dashes] = user_id
                user_id_variants_map[user_id_no_dashes.lower()] = user_id
                
                # Debug: Print all users with weekoffs
                print(f"[DEBUG WEEKOFF] User '{user.get('name', 'Unknown')}' (ID: {user_id}): weekoffs={weekoff_strings}, today={today_weekday}, match={today_weekday in weekoff_strings}")
    
    # Categorize users by status - default to ABSENT if not marked as PRESENT
    present_users = []
    absent_users = []
    leave_users = []
    weekoff_users = []
    
    for u in user_role_users:
        user_id = str(u.get("id", "")).strip()
        if not user_id or user_id == "None":
            continue
            
        # Try to find canonical ID using variants map
        canonical_id = user_id_variants_map.get(user_id.lower(), user_id)
        canonical_id = user_id_variants_map.get(user_id.upper(), canonical_id)
        canonical_id = user_id_variants_map.get(user_id.replace("-", ""), canonical_id)
        
        # Get the attendance status first - prioritize actual attendance over weekoff
        status = u.get("today_status")
        
        # Check if today is a weekoff for this user
        user_weekoffs = user_weekoffs_map.get(canonical_id, user_weekoffs_map.get(user_id, []))
        is_weekoff_today = today_weekday in user_weekoffs if user_weekoffs else False
        
        # Debug: Log weekoff check for users with weekoffs or potential matches
        if user_weekoffs or len(weekoff_users) < 5:
            print(f"[DEBUG CHECK] User '{u.get('name', 'Unknown')}' (ID: {user_id}): canonical={canonical_id}, weekoffs={user_weekoffs}, today={today_weekday}, match={is_weekoff_today}, status={status}")
        
        # IMPORTANT: If user has clocked in (status is PRESENT), prioritize that over weekoff
        # This means if someone works on their weekoff, they should show as PRESENT
        if status == "PRESENT":
            present_users.append(u)
            print(f"[DEBUG] User '{u.get('name', 'Unknown')}' is PRESENT (even if weekoff)")
        elif is_weekoff_today and status not in ["PRESENT", "LEAVE"]:
            # Only mark as weekoff if they haven't clocked in and it's their weekoff
            # Create a copy of the user dict and update status to WEEKOFF
            weekoff_user = u.copy()
            weekoff_user["today_status"] = "WEEKOFF"
            weekoff_users.append(weekoff_user)
            print(f"[DEBUG MATCH] ✅ User '{u.get('name', 'Unknown')}' added to weekoff list with status WEEKOFF!")
        elif status == "LEAVE":
            leave_users.append(u)
        elif status == "ABSENT":
            absent_users.append(u)
        elif status == "WFH":
            # WFH users are counted as ABSENT for total calculation
            absent_users.append(u)
        elif not status or status == "":
            # Handle None, empty string, and missing key - default to ABSENT if not marked as present
            absent_users.append(u)  # Default to ABSENT if no status
        else:
            # Any other status value - default to absent
            absent_users.append(u)
    
    # Calculate counts for display
    present_count = len(present_users)
    absent_count = len(absent_users)  # Includes WFH users
    leave_count = len(leave_users)
    weekoff_count = len(weekoff_users)
    
    # Verify: Present + Absent + Leave should equal Total Users
    calculated_total = present_count + absent_count + leave_count
    
    # Create user name mapping from the data we already have (fallback for get_user_name_mapping)
    # Store it in session state so other parts of the page can use it
    # Use users_data (all users) not just user_role_users, so we have names for all users
    if users_data:
        name_mapping = get_user_name_mapping_from_data(users_data)
        st.session_state.user_name_mapping_fallback = name_mapping
        print(f"[DEBUG] Created name mapping with {len(name_mapping)} users in session state")
        # Debug: Show a sample
        if name_mapping:
            sample = list(name_mapping.items())[:2]
            print(f"[DEBUG] Sample name mapping: {sample}")
    else:
        st.session_state.user_name_mapping_fallback = {}
        print(f"[DEBUG] No users_data, setting empty name mapping")
    
    # Debug: Check if any users with weekoffs are not in user_role_users
    user_role_user_ids = {str(u.get("id", "")).strip() for u in user_role_users}
    # Also create normalized versions (lowercase, no dashes) for comparison
    user_role_user_ids_normalized = set()
    for uid in user_role_user_ids:
        if uid and uid != "None":
            user_role_user_ids_normalized.add(uid.lower())
            user_role_user_ids_normalized.add(uid.replace("-", "").lower())
    
    weekoff_user_ids_in_map = set()
    for uid, weekoffs in user_weekoffs_map.items():
        if today_weekday in weekoffs:
            weekoff_user_ids_in_map.add(uid)
            weekoff_user_ids_in_map.add(uid.lower())
            weekoff_user_ids_in_map.add(uid.replace("-", "").lower())
    
    # Find users with weekoffs that are not in the role list
    weekoff_users_not_in_role_list = []
    for uid, weekoffs in user_weekoffs_map.items():
        if today_weekday in weekoffs:
            uid_normalized = uid.lower()
            uid_no_dashes = uid.replace("-", "").lower()
            if uid not in user_role_user_ids and uid_normalized not in user_role_user_ids_normalized and uid_no_dashes not in user_role_user_ids_normalized:
                # Find user name
                for user in all_users_with_weekoffs:
                    if isinstance(user, dict) and str(user.get("id", "")).strip() == uid:
                        weekoff_users_not_in_role_list.append({
                            "id": uid,
                            "name": user.get("name", "Unknown"),
                            "role": user.get("role", "Unknown"),
                            "weekoffs": weekoffs
                        })
                        break
    
    # Debug display in UI (collapsible)
    with st.expander("🔍 Debug Info (Click to see)", expanded=False):
        st.write(f"**Users Data:** {len(users_data) if users_data else 0} users loaded")
        st.write(f"**User Role Users (USER/ADMIN):** {len(user_role_users)} users after filtering")
        st.write(f"**Name Mapping:** {len(st.session_state.get('user_name_mapping_fallback', {}))} users in mapping")
        st.write(f"**Today's Weekday:** {today_weekday}")
        st.write(f"**Selected Date:** {selected_date.isoformat()}")
        st.write(f"**Users with Weekoffs Mapped:** {len(user_weekoffs_map)} users")
        st.write(f"**Users with Today as Weekoff (in map):** {len(weekoff_user_ids_in_map)} users")
        st.write(f"**Weekoff Users Found (in role list):** {weekoff_count} users")
        
        # Show status breakdown
        if user_role_users:
            status_counts = {}
            for u in user_role_users:
                status = u.get("today_status", "N/A")
                status_counts[status] = status_counts.get(status, 0) + 1
            st.write(f"**Status Breakdown:** {status_counts}")
            
            # Show users with PRESENT status
            present_users_debug = [u for u in user_role_users if u.get("today_status") == "PRESENT"]
            if present_users_debug:
                st.write(f"**Users with PRESENT status ({len(present_users_debug)}):**")
                for u in present_users_debug[:5]:
                    st.write(f"  - {u.get('name', 'Unknown')} (ID: {u.get('id', 'N/A')}, Role: {u.get('role', 'N/A')})")
            else:
                st.warning("⚠️ **No users found with PRESENT status!**")
                # Show sample of what statuses we do have
                sample_statuses = [u.get("today_status", "N/A") for u in user_role_users[:10]]
                st.write(f"**Sample statuses from first 10 users:** {sample_statuses}")
        if weekoff_users_not_in_role_list:
            st.warning(f"⚠️ **{len(weekoff_users_not_in_role_list)} user(s) with weekoff today are NOT in the USER/ADMIN role list!** They may be MANAGER or filtered out.")
            missing_info = []
            for missing_user in weekoff_users_not_in_role_list[:5]:
                missing_info.append(f"{missing_user['name']} (Role: {missing_user['role']}, Weekoffs: {missing_user['weekoffs']})")
            if missing_info:
                st.write(f"**Missing users:** {', '.join(missing_info)}")
        if user_weekoffs_map:
            sample_weekoffs = dict(list(user_weekoffs_map.items())[:3])
            st.write(f"**Sample Weekoffs Mapping:** {sample_weekoffs}")
        if users_data:
            st.write(f"**Sample user:** {users_data[0] if users_data else 'None'}")
        if st.session_state.get('user_name_mapping_fallback'):
            sample_mapping = dict(list(st.session_state.user_name_mapping_fallback.items())[:3])
            st.write(f"**Sample mapping:** {sample_mapping}")
    
    # SECTION 1: USER DASHBOARD
    st.markdown("## 👥 User Overview")
    st.markdown("Dashboard showing Total users count with role 'USER' or 'ADMIN', Count of present, absent, leave, allocated, not allocated, and weekoff")
    st.caption("📊 **How Total Users are Calculated:** Total Users = All users in the system with role 'USER' or 'ADMIN' (excluding MANAGER role). Total Users = Present + Absent + Leave + Weekoff. WFH users are included in the Absent count. Weekoff users are determined by checking if today's weekday matches their configured weekoff days.")
    
    # Display clickable metrics
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
    # Initialize session state for modals (already initialized at top level)
    if "show_user_list" not in st.session_state:
        st.session_state.show_user_list = None
    if "user_list_data" not in st.session_state:
        st.session_state.user_list_data = []
    
    with col1:
        if st.button(f"**Total Users**\n\n{total_users}", use_container_width=True, key="btn_total_users"):
            st.session_state.show_user_list = "total"
            st.session_state.user_list_data = user_role_users
            # Clear project list state to avoid conflicts
            st.session_state.show_project_list = None
            st.session_state.project_list_data = None
            st.rerun()
    
    with col2:
        if st.button(f"**Present**\n\n{present_count}", use_container_width=True, key="btn_present"):
            st.session_state.show_user_list = "present"
            st.session_state.user_list_data = present_users
            # Clear project list state to avoid conflicts
            st.session_state.show_project_list = None
            st.session_state.project_list_data = None
            st.rerun()
    
    with col3:
        if st.button(f"**Absent**\n\n{absent_count}", use_container_width=True, key="btn_absent"):
            st.session_state.show_user_list = "absent"
            st.session_state.user_list_data = absent_users
            # Clear project list state to avoid conflicts
            st.session_state.show_project_list = None
            st.session_state.project_list_data = None
            st.rerun()
    
    with col4:
        if st.button(f"**Leave**\n\n{leave_count}", use_container_width=True, key="btn_leave"):
            st.session_state.show_user_list = "leave"
            st.session_state.user_list_data = leave_users
            # Clear project list state to avoid conflicts
            st.session_state.show_project_list = None
            st.session_state.project_list_data = None
            st.rerun()
    
    with col5:
        if st.button(f"**Allocated**\n\n{len(allocated_users)}", use_container_width=True, key="btn_allocated"):
            st.session_state.show_user_list = "allocated"
            st.session_state.user_list_data = allocated_users
            # Clear project list state to avoid conflicts
            st.session_state.show_project_list = None
            st.session_state.project_list_data = None
            st.rerun()
    
    with col6:
        if st.button(f"**Not Allocated**\n\n{len(not_allocated_users)}", use_container_width=True, key="btn_not_allocated"):
            st.session_state.show_user_list = "not_allocated"
            st.session_state.user_list_data = not_allocated_users
            # Clear project list state to avoid conflicts
            st.session_state.show_project_list = None
            st.session_state.project_list_data = None
            st.rerun()
    
    with col7:
        if st.button(f"**Weekoff**\n\n{weekoff_count}", use_container_width=True, key="btn_weekoff"):
            st.session_state.show_user_list = "weekoff"
            st.session_state.user_list_data = weekoff_users
            # Clear project list state to avoid conflicts
            st.session_state.show_project_list = None
            st.session_state.project_list_data = None
            st.rerun()
    
    # Explanation text for attendance status logic
    # Note: Weekoff users are excluded from Present/Absent/Leave counts
    total_without_weekoff = present_count + absent_count + leave_count
    if total_without_weekoff + weekoff_count == total_users:
        st.caption(f"ℹ️ **Status Breakdown:** Present ({present_count}) + Absent ({absent_count}) + Leave ({leave_count}) + Weekoff ({weekoff_count}) = {total_users} | Total Users: {total_users} ✅")
    else:
        st.warning(f"⚠️ **Mismatch:** Present ({present_count}) + Absent ({absent_count}) + Leave ({leave_count}) + Weekoff ({weekoff_count}) = {total_without_weekoff + weekoff_count} | Total Users: {total_users} (Difference: {total_users - (total_without_weekoff + weekoff_count)})")
    
    # Show exportable list popup when a button is clicked
    # Only show dialog if explicitly triggered (not on page reload)
    # Check if we have valid data and it wasn't just persisted from previous session
    if (st.session_state.show_user_list and 
        st.session_state.user_list_data and 
        len(st.session_state.user_list_data) > 0):
        
        list_title = {
            "total": "All Users (Role: USER or ADMIN)",
            "present": "Present Users",
            "absent": "Absent Users",
            "leave": "Leave Users",
            "allocated": "Allocated Users",
            "not_allocated": "Not Allocated Users",
            "weekoff": "Users on Weekoff Today"
        }.get(st.session_state.show_user_list, "Users")
        
        # Only show user list dialog if project list is not active
        if not st.session_state.show_project_list:
            @st.dialog(f"📋 {list_title}")
            def show_user_list_dialog():
                # For allocated users, fetch and add project names
                if st.session_state.show_user_list == "allocated":
                    # Get user to projects mapping
                    user_projects_map = get_user_projects_mapping_cached(selected_date.isoformat())
                    
                    # Enhance user data with project names
                    enhanced_user_data = []
                    for user in st.session_state.user_list_data:
                        user_id = str(user.get("id", "")).strip()
                        if not user_id or user_id == "None":
                            user_id = ""
                        
                        # Try to find projects for this user
                        projects = user_projects_map.get(user_id, [])
                        if not projects:
                            # Try lowercase, uppercase, and no-dash variants
                            user_id_lower = user_id.lower()
                            user_id_upper = user_id.upper()
                            user_id_no_dashes = user_id.replace("-", "")
                            projects = (user_projects_map.get(user_id_lower) or 
                                       user_projects_map.get(user_id_upper) or 
                                       user_projects_map.get(user_id_no_dashes) or
                                       user_projects_map.get(user_id_no_dashes.lower()) or
                                       [])
                        
                        # Create enhanced user dict with project names
                        enhanced_user = user.copy()
                        enhanced_user["allocated_projects_list"] = ", ".join(projects) if projects else "No projects"
                        enhanced_user["allocated_projects_count"] = len(projects)
                        enhanced_user_data.append(enhanced_user)
                    
                    # Create DataFrame with project names column
                    df_users = pd.DataFrame(enhanced_user_data)
                    if not df_users.empty:
                        # Reorder columns to show project names prominently
                        columns_order = ["name", "email", "allocated_projects_list", "allocated_projects_count", "work_role", "today_status"]
                        # Add any other columns that exist
                        other_cols = [col for col in df_users.columns if col not in columns_order]
                        columns_order.extend(other_cols)
                        # Only use columns that exist in the dataframe
                        columns_order = [col for col in columns_order if col in df_users.columns]
                        df_users = df_users[columns_order]
                        # Rename for display
                        df_users = df_users.rename(columns={
                            "allocated_projects_list": "Allocated Projects",
                            "allocated_projects_count": "Projects Count"
                        })
                        st.dataframe(df_users, use_container_width=True, height=400)
                        export_csv(f"{list_title.replace(' ', '_')}_{selected_date}.csv", enhanced_user_data)
                    else:
                        st.info("No users found.")
                elif st.session_state.show_user_list == "leave":
                    # For Leave users, add a "View History" column using custom table
                    df_users = pd.DataFrame(st.session_state.user_list_data)
                    if not df_users.empty:
                        # Get column names from dataframe
                        columns = list(df_users.columns)
                        
                        # Create header row
                        header_cols = st.columns([1] * len(columns) + [1.2])  # Extra column for View History
                        for idx, col in enumerate(columns):
                            with header_cols[idx]:
                                st.markdown(f"**{col}**")
                        with header_cols[-1]:
                            st.markdown("**View History**")
                        
                        st.markdown("---")
                        
                        # Create data rows with View History buttons
                        for row_idx, user in enumerate(st.session_state.user_list_data):
                            row_cols = st.columns([1] * len(columns) + [1.2])
                            
                            # Display data columns
                            for col_idx, col in enumerate(columns):
                                with row_cols[col_idx]:
                                    value = user.get(col, "")
                                    st.write(str(value) if value is not None else "")
                            
                            # View History button column
                            with row_cols[-1]:
                                user_id = str(user.get("id", "")).strip()
                                user_name = user.get("name", "Unknown")
                                if st.button("📋 View History", key=f"view_history_{user_id}_{row_idx}", use_container_width=True):
                                    # Store navigation parameters in session state
                                    st.session_state.navigate_to_approvals = True
                                    st.session_state.approval_tab = "history"
                                    st.session_state.approval_user_id = user_id
                                    st.session_state.approval_user_name = user_name
                                    st.session_state.approval_date_from = selected_date.isoformat()
                                    st.session_state.approval_date_to = selected_date.isoformat()
                                    # Navigate to attendance approvals page
                                    st.switch_page("app_pages/6_Attendance_Approvals.py")
                            
                            if row_idx < len(st.session_state.user_list_data) - 1:
                                st.markdown("---")
                        
                        # Also show export option
                        export_csv(f"{list_title.replace(' ', '_')}_{selected_date}.csv", st.session_state.user_list_data)
                    else:
                        st.info("No users found.")
                else:
                    # For other user lists, show as before
                    df_users = pd.DataFrame(st.session_state.user_list_data)
                    if not df_users.empty:
                        st.dataframe(df_users, use_container_width=True, height=400)
                        export_csv(f"{list_title.replace(' ', '_')}_{selected_date}.csv", st.session_state.user_list_data)
                    else:
                        st.info("No users found.")
                
                col1, col2 = st.columns([4, 1])
                with col2:
                    if st.button("Close", key="close_user_list", use_container_width=True, type="primary"):
                        st.session_state.show_user_list = None
                        st.session_state.user_list_data = []
                        st.rerun()
            
            show_user_list_dialog()
    
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
    st.caption("ℹ️ **Note:** The 'Total Users' count in project cards shows users with role='USER' or 'ADMIN' to match the 'Allocated' card count. Click 'Total Users' to see all project members including MANAGER roles.")
    
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
        
        # Count roles from metrics (shows allocated roles from ProjectMember)
        role_counts = {}
        for m in project_metrics:
            role = m.get("work_role", "Unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
        
        # Get allocation data (cached) - try with only_active=True first (default)
        allocation_data = get_project_allocation_cached(project_id, date_str, only_active=True)
        
        total_users_in_project = 0
        total_user_admin_role_members = 0  # Count USER and ADMIN role members (to match Allocated card)
        if allocation_data:
            # First, try to use total_resources from API response (most reliable)
            if "total_resources" in allocation_data:
                total_all_members = allocation_data.get("total_resources", 0)
                # Filter to count only USER and ADMIN role members (to match Allocated card logic)
                if allocation_data.get("resources"):
                    resources = aggregate_by_user(allocation_data["resources"])
                    # Count only members with designation='USER' or 'ADMIN' (matching Allocated card filter)
                    user_admin_role_resources = [
                        r for r in resources 
                        if r.get("designation", "").upper() in ["USER", "ADMIN"]
                    ]
                    total_user_admin_role_members = len(user_admin_role_resources)
                    total_users_in_project = total_user_admin_role_members  # Use filtered count
                    print(f"[DEBUG] Project {project.get('name', project_id)}: Total members={total_all_members}, USER/ADMIN role members={total_user_admin_role_members} (showing USER/ADMIN count to match Allocated card)")
                else:
                    total_users_in_project = total_all_members
                    print(f"[DEBUG] Project {project.get('name', project_id)}: Using total_resources={total_users_in_project} (active members only, no role filter)")
            # Fallback: calculate from resources array if total_resources not available
            elif allocation_data.get("resources"):
                resources = aggregate_by_user(allocation_data["resources"])
                # Filter to count only USER and ADMIN role members
                user_admin_role_resources = [
                    r for r in resources 
                    if r.get("designation", "").upper() in ["USER", "ADMIN"]
                ]
                total_user_admin_role_members = len(user_admin_role_resources)
                total_users_in_project = total_user_admin_role_members  # Use filtered count
                print(f"[DEBUG] Project {project.get('name', project_id)}: Calculated from resources - Total={len(resources)}, USER/ADMIN role={total_user_admin_role_members} (showing USER/ADMIN count)")
            
            # If we got 0 active members, try fetching all members (including inactive) to see if that's the issue
            if total_users_in_project == 0:
                print(f"[DEBUG] Project {project.get('name', project_id)} (ID: {project_id}): No active USER/ADMIN role members found. "
                      f"Trying with only_active=False to check for inactive members...")
                # Try with inactive members (different cache key, so no need to clear)
                allocation_data_all = get_project_allocation_cached(project_id, date_str, only_active=False)
                if allocation_data_all and allocation_data_all.get("resources"):
                    resources_all = aggregate_by_user(allocation_data_all["resources"])
                    # Still filter by USER/ADMIN role even for inactive members
                    user_admin_role_resources_all = [
                        r for r in resources_all 
                        if r.get("designation", "").upper() in ["USER", "ADMIN"]
                    ]
                    total_user_admin_role_members = len(user_admin_role_resources_all)
                    total_users_in_project = total_user_admin_role_members
                    print(f"[DEBUG] Project {project.get('name', project_id)}: Found {total_user_admin_role_members} USER/ADMIN role members (including inactive) out of {len(resources_all)} total members")
                    # Update allocation_data to include all members
                    allocation_data = allocation_data_all
                elif allocation_data_all and allocation_data_all.get("total_resources", 0) > 0:
                    # If we can't filter by role, use total but note it might include non-USER/ADMIN roles
                    total_users_in_project = allocation_data_all.get("total_resources", 0)
                    print(f"[DEBUG] Project {project.get('name', project_id)}: Found {total_users_in_project} total members (including inactive, may include non-USER/ADMIN roles)")
                    allocation_data = allocation_data_all
        else:
            print(f"[DEBUG] Project {project.get('name', project_id)} (ID: {project_id}): allocation_data is None - API call failed or returned no data")
            # Try with only_active=False as fallback
            allocation_data = get_project_allocation_cached(project_id, date_str, only_active=False)
            if allocation_data and allocation_data.get("resources"):
                resources = aggregate_by_user(allocation_data["resources"])
                # Filter to count only USER and ADMIN role members
                user_admin_role_resources = [
                    r for r in resources 
                    if r.get("designation", "").upper() in ["USER", "ADMIN"]
                ]
                total_user_admin_role_members = len(user_admin_role_resources)
                total_users_in_project = total_user_admin_role_members
                print(f"[DEBUG] Project {project.get('name', project_id)}: Fallback succeeded, found {total_user_admin_role_members} USER/ADMIN role members (including inactive) out of {len(resources)} total")
            elif allocation_data and "total_resources" in allocation_data:
                total_users_in_project = allocation_data.get("total_resources", 0)
                print(f"[DEBUG] Project {project.get('name', project_id)}: Fallback succeeded, found {total_users_in_project} members (including inactive, may include non-USER/ADMIN roles)")
            else:
                # Show a warning in the UI for debugging (only once per project)
                if not hasattr(st.session_state, 'allocation_warnings_shown'):
                    st.session_state.allocation_warnings_shown = set()
                if project_id not in st.session_state.allocation_warnings_shown:
                    st.session_state.allocation_warnings_shown.add(project_id)
                    st.warning(f"⚠️ Could not fetch allocation data for project: {project.get('name', project_id)}. "
                              f"Check API server logs and verify project has members assigned.")
        
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
                                # Clear user list state to avoid conflicts
                                st.session_state.show_user_list = None
                                st.session_state.user_list_data = []
                                st.rerun()
                        with metric_col2:
                            if st.button(f"**Hours**\n{proj_data['total_hours']:.1f}", key=f"hours_{proj['id']}", use_container_width=True):
                                st.session_state.show_project_list = f"hours_{proj['id']}"
                                st.session_state.project_list_data = proj_data
                                # Clear user list state to avoid conflicts
                                st.session_state.show_user_list = None
                                st.session_state.user_list_data = []
                                st.rerun()
                        
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
                                # Clear user list state to avoid conflicts
                                st.session_state.show_user_list = None
                                st.session_state.user_list_data = []
                                st.rerun()
                        
                        # Show remaining roles in expander if there are more than 4
                        if len(roles_list) > max_visible_roles:
                            remaining_count = len(roles_list) - max_visible_roles
                            with st.expander(f"➕ {remaining_count} more role(s)"):
                                for role, count in roles_list[max_visible_roles:]:
                                    if st.button(f"{role}: {count}", key=f"role_{proj['id']}_{role}_exp", use_container_width=True):
                                        st.session_state.show_project_list = f"role_{proj['id']}_{role}"
                                        st.session_state.project_list_data = proj_data
                                        st.session_state.selected_role = role
                                        # Clear user list state to avoid conflicts
                                        st.session_state.show_user_list = None
                                        st.session_state.user_list_data = []
                                        st.rerun()
                        
                        # Add spacing to standardize height
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Total users
                        if st.button(f"**Total Users**\n{proj_data['total_users']}", key=f"users_{proj['id']}", use_container_width=True):
                            st.session_state.show_project_list = f"users_{proj['id']}"
                            st.session_state.project_list_data = proj_data
                            # Clear user list state to avoid conflicts
                            st.session_state.show_user_list = None
                            st.session_state.user_list_data = []
                            st.rerun()
    
    # Initialize project list state (already initialized at top level)
    if "show_project_list" not in st.session_state:
        st.session_state.show_project_list = None
    if "project_list_data" not in st.session_state:
        st.session_state.project_list_data = None
    
    # Single dialog function to handle all project list types
    # Only show dialog if explicitly triggered (not on page load)
    if st.session_state.show_project_list and st.session_state.project_list_data:
        # Only show project list dialog if user list is not active
        if not st.session_state.show_user_list:
            @st.dialog("📋 Project Details")
            def show_project_list_dialog():
                if not st.session_state.show_project_list or not st.session_state.project_list_data:
                    st.info("No data to display.")
                    return
                
                proj_data = st.session_state.project_list_data
                proj = proj_data["project"]
                
                if st.session_state.show_project_list.startswith("tasks_"):
                    st.markdown(f"### 📋 Tasks Details - {proj.get('name')}")
                    task_list = []
                    
                    # Build name mapping from allocation_data first (most reliable - has names directly)
                    user_map = {}
                    if proj_data.get("allocation_data") and proj_data["allocation_data"].get("resources"):
                        for resource in proj_data["allocation_data"]["resources"]:
                            res_user_id = str(resource.get("user_id", "")).strip()
                            res_name = resource.get("name", "").strip()
                            if res_user_id and res_user_id != "None" and res_name and res_name != "None":
                                # Store with multiple ID format variants for better matching
                                user_map[res_user_id] = res_name
                                user_map[res_user_id.lower()] = res_name
                                user_map[res_user_id.upper()] = res_name
                                # Also store without dashes in case of UUID format differences
                                user_map[res_user_id.replace("-", "")] = res_name
                                user_map[res_user_id.replace("-", "").lower()] = res_name
                        print(f"[DEBUG] Tasks dialog: Created mapping from allocation_data with {len(set(user_map.values()))} unique users, {len(user_map)} ID variants")
                    
                    # Fallback to API mapping if allocation_data didn't have names
                    if not user_map:
                        user_map = get_user_name_mapping()
                        if not user_map:
                            user_map = st.session_state.get("user_name_mapping_fallback", {})
                        print(f"[DEBUG] Tasks dialog: Using API/fallback mapping with {len(user_map)} users")
                    
                    # Debug: Show sample user IDs from metrics
                    if proj_data["metrics"]:
                        sample_metric_user_ids = [str(m.get("user_id")) for m in proj_data["metrics"][:3]]
                        print(f"[DEBUG] Tasks dialog: Sample metric user_ids: {sample_metric_user_ids}")
                        print(f"[DEBUG] Tasks dialog: Can find names? {[user_map.get(uid, 'NOT_FOUND') for uid in sample_metric_user_ids]}")
                    
                    for m in proj_data["metrics"]:
                        user_id = str(m.get("user_id") or m.get("id") or "").strip()
                        if not user_id or user_id == "None":
                            user_id = ""
                        # Try to find name, with multiple ID format attempts
                        user_name = user_map.get(user_id, "Unknown")
                        if user_name == "Unknown":
                            # Try lowercase, uppercase, and without dashes
                            user_id_lower = user_id.lower()
                            user_id_upper = user_id.upper()
                            user_id_no_dashes = user_id.replace("-", "")
                            user_name = (user_map.get(user_id_lower) or 
                                        user_map.get(user_id_upper) or 
                                        user_map.get(user_id_no_dashes) or
                                        user_map.get(user_id_no_dashes.lower()) or
                                        "Unknown")
                        # If still unknown, try to get from allocation_data directly with exact match
                        if user_name == "Unknown" and proj_data.get("allocation_data") and user_id:
                            for resource in proj_data["allocation_data"].get("resources", []):
                                res_id = str(resource.get("user_id", "")).strip()
                                # Try exact match and normalized matches
                                if (res_id == user_id or 
                                    res_id.lower() == user_id.lower() or
                                    res_id.replace("-", "") == user_id.replace("-", "")):
                                    user_name = resource.get("name", "Unknown")
                                    if user_name and user_name != "None":
                                        break
                        task_list.append({
                            "user_name": user_name,
                            "tasks_completed": m.get("tasks_completed", 0),
                            "hours_worked": m.get("hours_worked", 0),
                            "work_role": m.get("work_role", "Unknown"),
                            "user_id": user_id
                        })
                    if task_list:
                        df_tasks = pd.DataFrame(task_list)
                        df_tasks = df_tasks[["user_name", "tasks_completed", "hours_worked", "work_role", "user_id"]]
                        st.dataframe(df_tasks, use_container_width=True, height=400)
                        export_csv(f"{proj.get('name')}_tasks_{selected_date}.csv", task_list)
                    else:
                        st.info("No task data available.")
                
                elif st.session_state.show_project_list.startswith("hours_"):
                    st.markdown(f"### 📋 Hours Details - {proj.get('name')}")
                    hours_list = []
                    
                    # Build name mapping from allocation_data first (most reliable)
                    user_map = {}
                    if proj_data.get("allocation_data") and proj_data["allocation_data"].get("resources"):
                        for resource in proj_data["allocation_data"]["resources"]:
                            res_user_id = str(resource.get("user_id", "")).strip()
                            res_name = resource.get("name", "").strip()
                            if res_user_id and res_user_id != "None" and res_name and res_name != "None":
                                # Store with multiple ID format variants for better matching
                                user_map[res_user_id] = res_name
                                user_map[res_user_id.lower()] = res_name
                                user_map[res_user_id.upper()] = res_name
                                user_map[res_user_id.replace("-", "")] = res_name
                                user_map[res_user_id.replace("-", "").lower()] = res_name
                        print(f"[DEBUG] Hours dialog: Created mapping from allocation_data with {len(set(user_map.values()))} unique users, {len(user_map)} ID variants")
                    
                    # Fallback to API mapping if allocation_data didn't have names
                    if not user_map:
                        user_map = get_user_name_mapping()
                        if not user_map:
                            user_map = st.session_state.get("user_name_mapping_fallback", {})
                        print(f"[DEBUG] Hours dialog: Using API/fallback mapping with {len(user_map)} users")
                    
                    for m in proj_data["metrics"]:
                        user_id = str(m.get("user_id") or m.get("id") or "").strip()
                        if not user_id or user_id == "None":
                            user_id = ""
                        # Try to find name, with multiple ID format attempts
                        user_name = user_map.get(user_id, "Unknown")
                        if user_name == "Unknown":
                            user_id_lower = user_id.lower()
                            user_id_upper = user_id.upper()
                            user_id_no_dashes = user_id.replace("-", "")
                            user_name = (user_map.get(user_id_lower) or 
                                        user_map.get(user_id_upper) or 
                                        user_map.get(user_id_no_dashes) or
                                        user_map.get(user_id_no_dashes.lower()) or
                                        "Unknown")
                        # If still unknown, try to get from allocation_data directly with exact match
                        if user_name == "Unknown" and proj_data.get("allocation_data") and user_id:
                            for resource in proj_data["allocation_data"].get("resources", []):
                                res_id = str(resource.get("user_id", "")).strip()
                                if (res_id == user_id or 
                                    res_id.lower() == user_id.lower() or
                                    res_id.replace("-", "") == user_id.replace("-", "")):
                                    user_name = resource.get("name", "Unknown")
                                    if user_name and user_name != "None":
                                        break
                        hours_list.append({
                            "user_name": user_name,
                            "hours_worked": m.get("hours_worked", 0),
                            "tasks_completed": m.get("tasks_completed", 0),
                            "work_role": m.get("work_role", "Unknown"),
                            "user_id": user_id
                        })
                    if hours_list:
                        df_hours = pd.DataFrame(hours_list)
                        df_hours = df_hours[["user_name", "hours_worked", "tasks_completed", "work_role", "user_id"]]
                        st.dataframe(df_hours, use_container_width=True, height=400)
                        export_csv(f"{proj.get('name')}_hours_{selected_date}.csv", hours_list)
                    else:
                        st.info("No hours data available.")
                
                elif st.session_state.show_project_list.startswith("role_"):
                    selected_role = st.session_state.get("selected_role", "Unknown")
                    st.markdown(f"### 📋 Role Details - {proj.get('name')} - {selected_role}")
                    role_list = []
                    
                    # Build name mapping from allocation_data first (most reliable)
                    user_map = {}
                    if proj_data.get("allocation_data") and proj_data["allocation_data"].get("resources"):
                        for resource in proj_data["allocation_data"]["resources"]:
                            res_user_id = str(resource.get("user_id", "")).strip()
                            res_name = resource.get("name", "").strip()
                            if res_user_id and res_user_id != "None" and res_name and res_name != "None":
                                # Store with multiple ID format variants for better matching
                                user_map[res_user_id] = res_name
                                user_map[res_user_id.lower()] = res_name
                                user_map[res_user_id.upper()] = res_name
                                user_map[res_user_id.replace("-", "")] = res_name
                                user_map[res_user_id.replace("-", "").lower()] = res_name
                        print(f"[DEBUG] Role dialog: Created mapping from allocation_data with {len(set(user_map.values()))} unique users, {len(user_map)} ID variants")
                    
                    # Fallback to API mapping if allocation_data didn't have names
                    if not user_map:
                        user_map = get_user_name_mapping()
                        if not user_map:
                            user_map = st.session_state.get("user_name_mapping_fallback", {})
                        print(f"[DEBUG] Role dialog: Using API/fallback mapping with {len(user_map)} users")
                    
                    for m in proj_data["metrics"]:
                        if m.get("work_role") == selected_role:
                            user_id = str(m.get("user_id") or m.get("id") or "").strip()
                            if not user_id or user_id == "None":
                                user_id = ""
                            # Try to find name, with multiple ID format attempts
                            user_name = user_map.get(user_id, "Unknown")
                            if user_name == "Unknown":
                                user_id_lower = user_id.lower()
                                user_id_upper = user_id.upper()
                                user_id_no_dashes = user_id.replace("-", "")
                                user_name = (user_map.get(user_id_lower) or 
                                            user_map.get(user_id_upper) or 
                                            user_map.get(user_id_no_dashes) or
                                            user_map.get(user_id_no_dashes.lower()) or
                                            "Unknown")
                            # If still unknown, try to get from allocation_data directly with exact match
                            if user_name == "Unknown" and proj_data.get("allocation_data") and user_id:
                                for resource in proj_data["allocation_data"].get("resources", []):
                                    res_id = str(resource.get("user_id", "")).strip()
                                    if (res_id == user_id or 
                                        res_id.lower() == user_id.lower() or
                                        res_id.replace("-", "") == user_id.replace("-", "")):
                                        user_name = resource.get("name", "Unknown")
                                        if user_name and user_name != "None":
                                            break
                            role_list.append({
                                "user_name": user_name,
                                "user_id": user_id,
                                "work_role": m.get("work_role", "Unknown"),
                                "hours_worked": m.get("hours_worked", 0),
                                "tasks_completed": m.get("tasks_completed", 0)
                            })
                    
                    if role_list:
                        df_role = pd.DataFrame(role_list)
                        df_role = df_role[["user_name", "work_role", "hours_worked", "tasks_completed", "user_id"]]
                        st.dataframe(df_role, use_container_width=True, height=400)
                        export_csv(f"{proj.get('name')}_{selected_role}_users_{selected_date}.csv", role_list)
                    else:
                        st.info(f"No users found for role: {selected_role}")
                
                elif st.session_state.show_project_list.startswith("users_"):
                    st.markdown(f"### 📋 Users in Project - {proj.get('name')}")
                    st.caption("ℹ️ Showing users with role='USER' or 'ADMIN' to match the Total Users count. Use the expander below to see all members including MANAGER roles.")
                    if proj_data.get("allocation_data") and proj_data["allocation_data"].get("resources"):
                        resources = aggregate_by_user(proj_data["allocation_data"]["resources"])
                        # Filter to show only USER and ADMIN role members (to match the count)
                        user_admin_resources = [
                            r for r in resources 
                            if r.get("designation", "").upper() in ["USER", "ADMIN"]
                        ]
                        user_list = []
                        for r in user_admin_resources:
                            user_metrics = [m for m in proj_data["metrics"] if m.get("user_id") == r.get("user_id")]
                            total_user_hours = sum(float(m.get("hours_worked", 0) or 0) for m in user_metrics)
                            total_user_tasks = sum(int(m.get("tasks_completed", 0) or 0) for m in user_metrics)
                            
                            user_list.append({
                                "name": r.get("name", "-"),
                                "email": r.get("email", "-"),
                                "designation": r.get("designation", "-"),
                                "work_role": r.get("work_role", "-"),
                                "attendance_status": r.get("attendance_status", "-"),
                                "total_hours_clocked": f"{total_user_hours:.2f}",
                                "total_tasks_performed": total_user_tasks
                            })
                        if user_list:
                            df_users = pd.DataFrame(user_list)
                            st.dataframe(df_users, use_container_width=True, height=400)
                            export_csv(f"{proj.get('name')}_users_{selected_date}.csv", user_list)
                        else:
                            st.info("No users with USER/ADMIN roles found in this project.")
                        
                        # Show all members (including MANAGER) in an expander
                        if len(resources) > len(user_admin_resources):
                            with st.expander(f"📋 Show All Members (including MANAGER roles) - {len(resources)} total"):
                                all_user_list = []
                                for r in resources:
                                    user_metrics = [m for m in proj_data["metrics"] if m.get("user_id") == r.get("user_id")]
                                    total_user_hours = sum(float(m.get("hours_worked", 0) or 0) for m in user_metrics)
                                    total_user_tasks = sum(int(m.get("tasks_completed", 0) or 0) for m in user_metrics)
                                    
                                    all_user_list.append({
                                        "name": r.get("name", "-"),
                                        "email": r.get("email", "-"),
                                        "designation": r.get("designation", "-"),
                                        "work_role": r.get("work_role", "-"),
                                        "attendance_status": r.get("attendance_status", "-"),
                                        "total_hours_clocked": f"{total_user_hours:.2f}",
                                        "total_tasks_performed": total_user_tasks
                                    })
                                if all_user_list:
                                    df_all_users = pd.DataFrame(all_user_list)
                                    st.dataframe(df_all_users, use_container_width=True, height=400)
                    else:
                        st.info("No allocation data available for this project.")
                
                col1, col2 = st.columns([4, 1])
                with col2:
                    if st.button("Close", key="close_project_modal", use_container_width=True, type="primary"):
                        st.session_state.show_project_list = None
                        st.session_state.project_list_data = None
                        if "selected_role" in st.session_state:
                            st.session_state.selected_role = None
                        st.rerun()
            
            show_project_list_dialog()

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
    
    st.markdown("---")
    
    # Fetch projects (cached)
    all_projects = get_all_projects_cached()
    
    # Filters (using global selected_date)
    f1, f2, f3, f4 = st.columns(4)
    
    with f1:
        selected_project = st.selectbox("Project", ["All"] + [p["name"] for p in all_projects], key="detail_project")
    
    with f2:
        designation_filter = st.selectbox("Designation", ["ALL", "ADMIN", "USER"], key="detail_designation")
    
    with f3:
        status_filter = st.selectbox(
            "Status", ["ALL", "PRESENT", "ABSENT", "LEAVE"], key="detail_status"
        )
    
    with f4:
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
            # Fetch resource data (cached) - using global selected_date
            data = get_project_allocation_cached(project_id, selected_date.isoformat())
            
            if data and data.get("resources"):
                resources = aggregate_by_user(data["resources"])
                
                # Get weekoffs for users to identify weekoff users (consistent with Dashboard Overview)
                detail_weekday = selected_date.strftime("%A").upper()
                all_users_with_weekoffs = authenticated_request("GET", "/admin/users/", params={"limit": 1000}, show_error=False) or []
                
                # Create a mapping of user_id to weekoffs
                user_weekoffs_map = {}
                for user in all_users_with_weekoffs:
                    if isinstance(user, dict):
                        user_id = str(user.get("id", "")).strip()
                        if not user_id or user_id == "None":
                            continue
                        weekoffs = user.get("weekoffs", [])
                        weekoff_strings = []
                        if weekoffs:
                            for w in weekoffs:
                                weekoff_value = None
                                if isinstance(w, str):
                                    weekoff_value = w.upper().strip()
                                elif isinstance(w, dict):
                                    weekoff_value = (w.get("value") or w.get("name") or "").upper().strip()
                                elif hasattr(w, 'value'):
                                    weekoff_value = str(w.value).upper().strip()
                                elif hasattr(w, 'name'):
                                    weekoff_value = str(w.name).upper().strip()
                                elif hasattr(w, '__str__'):
                                    weekoff_value = str(w).upper().strip()
                                
                                if weekoff_value and weekoff_value in ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]:
                                    weekoff_strings.append(weekoff_value)
                        
                        if weekoff_strings:
                            user_weekoffs_map[user_id] = weekoff_strings
                            # Also store ID variants for flexible matching
                            user_weekoffs_map[user_id.lower()] = weekoff_strings
                            user_weekoffs_map[user_id.upper()] = weekoff_strings
                            user_weekoffs_map[user_id.replace("-", "")] = weekoff_strings
                            user_weekoffs_map[user_id.replace("-", "").lower()] = weekoff_strings
                
                # Normalize attendance status (consistent with Dashboard Overview logic)
                # WFH should be treated as ABSENT, and handle weekoffs
                normalized_resources = []
                for r in resources:
                    user_id = str(r.get("user_id", "")).strip()
                    attendance_status = r.get("attendance_status", "ABSENT")
                    
                    # Check if today is a weekoff for this user
                    user_weekoffs = user_weekoffs_map.get(user_id, user_weekoffs_map.get(user_id.lower(), user_weekoffs_map.get(user_id.upper(), [])))
                    is_weekoff = detail_weekday in user_weekoffs if user_weekoffs else False
                    
                    # Normalize status: WFH -> ABSENT (consistent with Dashboard Overview)
                    normalized_status = attendance_status
                    if attendance_status == "WFH":
                        normalized_status = "ABSENT"
                    elif not attendance_status or attendance_status == "":
                        normalized_status = "ABSENT"
                    
                    # Add normalized status and weekoff flag
                    # IMPORTANT: If user clocked in (PRESENT), show PRESENT even on weekoff
                    # Weekoff is only for display if they didn't clock in
                    r_normalized = r.copy()
                    r_normalized["attendance_status_normalized"] = normalized_status
                    r_normalized["is_weekoff"] = is_weekoff
                    # Only show WEEKOFF if they didn't clock in (status is not PRESENT)
                    if is_weekoff and normalized_status != "PRESENT":
                        r_normalized["attendance_status_display"] = "WEEKOFF"
                    else:
                        r_normalized["attendance_status_display"] = normalized_status
                    normalized_resources.append(r_normalized)
                
                # Apply filters (use normalized status for filtering)
                filtered = normalized_resources
                if designation_filter != "ALL":
                    filtered = [r for r in filtered if r.get("designation") == designation_filter]
                if work_role_filter != "ALL":
                    filtered = [r for r in filtered if r.get("work_role") == work_role_filter]
                if status_filter != "ALL":
                    # Filter by normalized status (consistent with Dashboard Overview)
                    if status_filter == "PRESENT":
                        filtered = [r for r in filtered if r.get("attendance_status_normalized") == "PRESENT" and not r.get("is_weekoff")]
                    elif status_filter == "ABSENT":
                        filtered = [r for r in filtered if r.get("attendance_status_normalized") == "ABSENT" and not r.get("is_weekoff")]
                    elif status_filter == "LEAVE":
                        filtered = [r for r in filtered if r.get("attendance_status_normalized") == "LEAVE" and not r.get("is_weekoff")]
                
                # Summary (consistent with Dashboard Overview: exclude weekoffs from counts)
                st.subheader("📌 Summary")
                allocated = len(filtered)
                # Count only non-weekoff users (consistent with Dashboard Overview)
                non_weekoff_filtered = [r for r in filtered if not r.get("is_weekoff")]
                present = sum(r.get("attendance_status_normalized") == "PRESENT" for r in non_weekoff_filtered)
                absent = sum(r.get("attendance_status_normalized") == "ABSENT" for r in non_weekoff_filtered)
                leave = sum(r.get("attendance_status_normalized") == "LEAVE" for r in non_weekoff_filtered)
                weekoff_count = sum(r.get("is_weekoff") for r in filtered)
                
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Allocated", allocated)
                c2.metric("Present", present)
                c3.metric("Absent", absent)
                c4.metric("Leave", leave)
                c5.metric("Weekoff", weekoff_count)
                
                # Allocation List - Show directly in table
                st.subheader("👥 Daily Roster")
                st.caption(f"📅 Showing tasks completed by members on **{selected_date.strftime('%B %d, %Y')}**")
                if not filtered:
                    st.info("No users match the selected filters.")
                else:
                    # Get metrics for tasks calculation - using global selected_date
                    project_metrics = get_project_metrics_cached(project_id, selected_date.isoformat(), selected_date.isoformat())
                    # Create a mapping of user_id to total tasks (normalize user_id for matching)
                    user_tasks_map = {}
                    # Create a mapping of user_id to task details by work_role
                    user_tasks_details_map = {}
                    for m in project_metrics:
                        user_id = str(m.get("user_id", "")).strip().lower()
                        tasks_count = int(m.get("tasks_completed", 0) or 0)
                        work_role = m.get("work_role", "Unknown")
                        
                        if user_id and user_id != "none":
                            # Sum total tasks
                            if user_id not in user_tasks_map:
                                user_tasks_map[user_id] = 0
                            user_tasks_map[user_id] += tasks_count
                            
                            # Store task details by work_role
                            if user_id not in user_tasks_details_map:
                                user_tasks_details_map[user_id] = []
                            if tasks_count > 0:
                                user_tasks_details_map[user_id].append({
                                    "work_role": work_role,
                                    "tasks": tasks_count
                                })
                    
                    # Prepare data for table
                    allocation_table_data = []
                    for r in filtered:
                        user_id = str(r.get("user_id", "")).strip().lower()
                        # Try to get tasks with normalized user_id
                        tasks_completed = user_tasks_map.get(user_id, 0)
                        task_details = user_tasks_details_map.get(user_id, [])
                        
                        # Format tasks done as a readable string with better formatting
                        tasks_done_str = "-"
                        if task_details:
                            task_parts = []
                            for detail in task_details:
                                role = detail.get("work_role", "Unknown")
                                count = detail.get("tasks", 0)
                                if count > 0:
                                    task_parts.append(f"{role}: {count}")
                            if task_parts:
                                tasks_done_str = " | ".join(task_parts)
                        elif tasks_completed > 0:
                            # Fallback: if we have total but no breakdown, show total
                            tasks_done_str = f"{tasks_completed} tasks"
                        
                        hours_worked = calculate_hours_worked(
                            r.get("first_clock_in"),
                            r.get("last_clock_out"),
                            r.get("minutes_worked"),
                        )
                        # Use normalized status for display (consistent with Dashboard Overview)
                        status_display = r.get("attendance_status_display", r.get("attendance_status_normalized", r.get("attendance_status", "-")))
                        allocation_table_data.append({
                            "Name": r.get("name", "-"),
                            "Email": r.get("email", "-"),
                            "Designation": r.get("designation", "-"),
                            "Work Role": r.get("work_role", "-"),
                            "Status": status_display,  # Use normalized status (WEEKOFF, PRESENT, ABSENT, LEAVE)
                            "Tasks Done": tasks_done_str,  # Tasks completed on selected date - breakdown by role
                            "Total Tasks": tasks_completed,  # Total count for quick reference
                            "Clock In": format_time(r.get("first_clock_in")),
                            "Clock Out": format_time(r.get("last_clock_out")),
                            "Hours Worked": hours_worked,
                            "Reporting Manager": r.get("reporting_manager") or "-"
                        })
                    
                    if allocation_table_data:
                        df_allocation = pd.DataFrame(allocation_table_data)
                        # Ensure tasks columns are always included and prominently displayed
                        # Verify tasks columns exist
                        if "Tasks Done" not in df_allocation.columns:
                            df_allocation["Tasks Done"] = "-"
                        if "Total Tasks" not in df_allocation.columns:
                            df_allocation["Total Tasks"] = 0
                        
                        # Reorder columns to put tasks more prominently
                        column_order = ["Name", "Email", "Designation", "Work Role", "Status", 
                                       "Tasks Done", "Total Tasks", "Clock In", "Clock Out", 
                                       "Hours Worked", "Reporting Manager"]
                        # Only use columns that exist in the dataframe, but ensure tasks columns are included
                        available_columns = list(df_allocation.columns)
                        # Ensure tasks columns are in the order
                        final_column_order = []
                        for col in column_order:
                            if col in available_columns:
                                final_column_order.append(col)
                        # Add any remaining columns that weren't in the order
                        for col in available_columns:
                            if col not in final_column_order:
                                final_column_order.append(col)
                        df_allocation = df_allocation[final_column_order]
                        st.dataframe(df_allocation, use_container_width=True, height=400)
                        export_csv(
                            f"project_allocation_{selected_project}_{selected_date}.csv",
                            allocation_table_data
                        )
                    else:
                        st.info("No allocation data available.")
            else:
                st.info("No allocation data found for this project.")
        else:
            st.warning("Project not found.")
    else:
        st.info("Please select a project to view detailed allocation information.")
