import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from role_guard import setup_role_access

load_dotenv()

# --- CONFIGURATION ---
st.set_page_config(page_title="User History", layout="wide")
setup_role_access(__file__)
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# --- AUTH CHECK ---
if "token" not in st.session_state:
    st.warning("🔒 Please login first from the main page.")
    st.stop()

# --- HELPER ---
def authenticated_request(method, endpoint, params=None):
    token = st.session_state.get("token")
    if not token:
        st.error("⚠️ No authentication token found. Please log in again.")
        print(f"[History Page] No token found for request: {method} {endpoint}")
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    full_url = f"{API_BASE_URL}{endpoint}"
    
    try:
        print(f"[History Page] Making {method} request to: {full_url}")
        if params:
            print(f"[History Page] Request params: {params}")
        
        response = requests.request(
            method, 
            full_url, 
            headers=headers, 
            params=params,
            timeout=(10, 30)
        )
        
        print(f"[History Page] Response status: {response.status_code}")
        
        if response.status_code >= 400:
            error_detail = f"API Error {response.status_code}"
            try:
                error_response = response.json()
                if isinstance(error_response, dict) and "detail" in error_response:
                    error_detail = error_response["detail"]
                print(f"[History Page] API Error Response: {error_response}")
            except:
                error_detail = response.text[:500] if response.text else f"HTTP {response.status_code}"
                print(f"[History Page] API Error Text: {error_detail}")
            
            st.error(f"⚠️ API Error: {error_detail}")
            return None
        
        result = response.json()
        print(f"[History Page] Successfully received {len(result) if isinstance(result, list) else 'response'} from {endpoint}")
        return result
        
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Could not connect to API server at {API_BASE_URL}"
        print(f"[History Page] Connection Error: {error_msg} - {str(e)}")
        st.error(f"⚠️ Connection Error: {error_msg}\n\nPlease check:\n1. Is the API server running?\n2. Is the API_BASE_URL correct? (Current: {API_BASE_URL})")
        return None
    except requests.exceptions.Timeout as e:
        error_msg = f"Request timeout for {endpoint}"
        print(f"[History Page] Timeout Error: {error_msg} - {str(e)}")
        st.error(f"⚠️ Request Timeout: The API server took too long to respond.")
        return None
    except Exception as e:
        error_msg = f"Request failed: {str(e)}"
        print(f"[History Page] Request Error: {error_msg}")
        import traceback
        traceback.print_exc()
        st.error(f"⚠️ Request Error: {error_msg}")
        return None

# --- PAGE HEADER ---
st.title("📋 User History")

# --- FILTERS ROW ---
st.markdown("### 🔍 Filters")
col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 0.5])

# Fetch data first to populate project/role dropdowns
print("[History Page] Initial fetch for dropdowns - calling /time/history without params")
all_history = authenticated_request("GET", "/time/history") or []
print(f"[History Page] Initial fetch returned {len(all_history)} records")

# Default date = last day the user worked (latest sheet_date)
default_date = date.today()
if all_history:
    try:
        df_all = pd.DataFrame(all_history)
        if "sheet_date" in df_all.columns:
            df_all["sheet_date"] = pd.to_datetime(df_all["sheet_date"], errors="coerce").dt.date
            last_worked = df_all["sheet_date"].dropna().max()
            if last_worked:
                default_date = last_worked
    except Exception:
        pass

with col1:
    date_from = st.date_input("📅 Date From", value=default_date)

with col2:
    date_to = st.date_input("📅 Date To", value=default_date)
# Get unique projects and roles for dropdown
projects_list = ["All Projects"]
roles_list = ["All Roles"]

if all_history:
    df_all = pd.DataFrame(all_history)
    if 'project_name' in df_all.columns:
        projects_list += list(df_all['project_name'].dropna().unique())
    if 'work_role' in df_all.columns:
        roles_list += list(df_all['work_role'].dropna().unique())

with col3:
    project_filter = st.selectbox("🏢 Project (Optional)", projects_list)

with col4:
    role_filter = st.selectbox("👤 Role (Optional)", roles_list)

with col5:
    st.markdown("<br>", unsafe_allow_html=True)
    apply_btn = st.button("🔍 Apply", type="primary", use_container_width=True)

st.markdown("---")

# --- FETCH & FILTER DATA ---
if "history_filters_applied" not in st.session_state:
    st.session_state.history_filters_applied = False
if "history_date_from" not in st.session_state:
    st.session_state.history_date_from = default_date
if "history_date_to" not in st.session_state:
    st.session_state.history_date_to = default_date
if "history_project_filter" not in st.session_state:
    st.session_state.history_project_filter = "All Projects"
if "history_role_filter" not in st.session_state:
    st.session_state.history_role_filter = "All Roles"

if apply_btn:
    st.session_state.history_filters_applied = True
    st.session_state.history_date_from = date_from
    st.session_state.history_date_to = date_to
    st.session_state.history_project_filter = project_filter
    st.session_state.history_role_filter = role_filter

if st.session_state.history_filters_applied:
    active_date_from = st.session_state.history_date_from
    active_date_to = st.session_state.history_date_to
    active_project_filter = st.session_state.history_project_filter
    active_role_filter = st.session_state.history_role_filter
else:
    # When filters haven't been applied, show all history (no date filtering)
    active_date_from = None
    active_date_to = None
    active_project_filter = "All Projects"
    active_role_filter = "All Roles"

params = {}
# Only apply date filters if they have been explicitly set by the user
if st.session_state.history_filters_applied:
    if active_date_from:
        params["start_date"] = str(active_date_from)
    if active_date_to:
        params["end_date"] = str(active_date_to)

# 1. Fetch RAW activity logs (for the table & basic total stats)
# If no date params, API will return all history for the user
print(f"[History Page] Fetching history with params: {params}")
time_history = authenticated_request("GET", "/time/history", params=params)
print(f"[History Page] Received time_history: {type(time_history)}, length: {len(time_history) if isinstance(time_history, list) else 'N/A'}")

# 2. Fetch Performance Metrics (for Productivity Scores)
me = authenticated_request("GET", "/me/")
user_id = me.get("id") if me else None

# Fetch from endpoints that the reverted backend actually supports
metrics_raw = []
attendance_raw = []

if user_id:
    # Use active filter dates if filters have been applied, otherwise use date inputs
    metrics_date_from = active_date_from if st.session_state.history_filters_applied else date_from
    metrics_date_to = active_date_to if st.session_state.history_filters_applied else date_to
    
    if metrics_date_from and metrics_date_to:
        m_params = {"user_id": user_id, "start_date": str(metrics_date_from), "end_date": str(metrics_date_to)}
        metrics_raw = authenticated_request("GET", "/admin/metrics/user_daily/", params=m_params) or []
    else:
        # If no date filters, fetch all metrics (or skip if API requires dates)
        m_params = {"user_id": user_id}
        metrics_raw = authenticated_request("GET", "/admin/metrics/user_daily/", params=m_params) or []
    
    # Note: /attendance-daily/ only supports user_id filter, no date range
    a_params = {"user_id": user_id}
    attendance_raw = authenticated_request("GET", "/attendance-daily/", params=a_params) or []
    
    # Filter attendance client-side by date range
    filter_date_from = metrics_date_from if metrics_date_from else date_from
    filter_date_to = metrics_date_to if metrics_date_to else date_to
    if attendance_raw and filter_date_from and filter_date_to:
        attendance_raw = [a for a in attendance_raw if str(filter_date_from) <= a.get('attendance_date', '') <= str(filter_date_to)]

if time_history:
    df_logs = pd.DataFrame(time_history)
    df_metrics = pd.DataFrame(metrics_raw)
    df_attendance = pd.DataFrame(attendance_raw)
    
    # Apply filters to main log df
    if active_project_filter != "All Projects" and 'project_name' in df_logs.columns:
        df_logs = df_logs[df_logs['project_name'] == active_project_filter]
    
    if active_role_filter != "All Roles" and 'work_role' in df_logs.columns:
        df_logs = df_logs[df_logs['work_role'] == active_role_filter]
    
    if df_logs.empty:
        st.info("📭 No records found for the selected filters.")
    else:
        # --- PREPARE ANALYTICS DF ---
        # Group metrics and logs by date to get a unified daily view
        if not df_metrics.empty:
            df_metrics['metric_date'] = pd.to_datetime(df_metrics['metric_date']).dt.date
            # Filter metrics for selected project if needed
            if active_project_filter != "All Projects":
                p_id = next((p["project_id"] for p in all_history if p.get("project_name") == active_project_filter), None)
                if p_id:
                    df_metrics = df_metrics[df_metrics['project_id'] == str(p_id)]
        
        # --- ANALYTICS DASHBOARD ---
        st.subheader("📊 Analytics Overview")
        
        # KPI Row 1: Productivity
        total_hours = df_logs['minutes_worked'].sum() / 60 if 'minutes_worked' in df_logs.columns else 0
        total_tasks = int(df_logs['tasks_completed'].sum()) if 'tasks_completed' in df_logs.columns else 0
        avg_score = df_metrics['productivity_score'].mean() if not df_metrics.empty else 0
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("⏱️ Total Hours", f"{total_hours:.1f}h")
        m_col2.metric("✅ Tasks Completed", total_tasks)
        m_col3.metric("📈 Avg Productivity", f"{avg_score:.1f}/10")

        st.markdown("---")

        # --- TREND CHARTS ---
        if not df_metrics.empty:
            st.subheader("📈 Performance Trends")
            df_plot = df_metrics.sort_values('metric_date')

            c1, c2 = st.columns(2)
            
            with c1:
                fig_prod = px.line(df_plot, x='metric_date', y='productivity_score', 
                                  title='Productivity Score Trend', markers=True,
                                  line_shape='spline')
                fig_prod.update_layout(yaxis_range=[0, 11])
                st.plotly_chart(fig_prod, use_container_width=True)
            
            with c2:
                fig_hours = px.bar(df_plot, x='metric_date', y='hours_worked', 
                                  title='Daily Hours Worked', color='hours_worked')
                st.plotly_chart(fig_hours, use_container_width=True)
        
        # --- TIMESHEET TABLE ---
        st.subheader("📋 Detailed Work Logs")
        
        # Prepare display dataframe
        display_cols = ['sheet_date', 'project_name', 'work_role', 'clock_in_at', 'clock_out_at', 
                       'minutes_worked', 'tasks_completed', 'status']
        available = [c for c in display_cols if c in df_logs.columns]
        df_display = df_logs[available].copy()
        
        if 'minutes_worked' in df_display.columns:
            # Convert to numeric in case it's stored as string
            df_display['minutes_worked'] = pd.to_numeric(df_display['minutes_worked'], errors='coerce').fillna(0)
            df_display['hours'] = (df_display['minutes_worked'] / 60).round(1)
        
        # Rename columns for UI
        rename_map = {'sheet_date': 'Date', 'project_name': 'Project', 'work_role': 'Role', 'clock_in_at': 'In', 'clock_out_at': 'Out', 'hours': 'Hours', 'tasks_completed': 'Tasks', 'status': 'Status'}
        df_display.rename(columns={k: v for k, v in rename_map.items() if k in df_display.columns}, inplace=True)
        
        # Format time
        for col in ['In', 'Out']:
            if col in df_display.columns:
                try: df_display[col] = pd.to_datetime(df_display[col]).dt.strftime('%H:%M')
                except: pass

        st.dataframe(df_display.drop(columns=['minutes_worked'] if 'minutes_worked' in df_display.columns else []), 
                     use_container_width=True, hide_index=True)

        # --- EXPORT ---
        csv_data = df_logs.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Report (CSV)", csv_data, f"user_report_{date.today()}.csv", "text/csv")

else:
    st.info("📭 No work history found for this period. Start clocking in to track your time!")
    st.caption("Make sure you're logged in and have time entries recorded.")
    
    # Debug information
    with st.expander("🔍 Debug Information", expanded=False):
        st.write(f"**API Base URL:** {API_BASE_URL}")
        st.write(f"**Endpoint:** `/time/history`")
        st.write(f"**Request Params:** {params}")
        st.write(f"**Response Type:** {type(time_history)}")
        st.write(f"**Response Value:** {time_history}")
        st.write(f"**Token Present:** {'Yes' if st.session_state.get('token') else 'No'}")
        
        if st.button("🔄 Retry API Call"):
            st.cache_data.clear()
            st.rerun()