import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
st.set_page_config(page_title="User History", layout="wide")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# --- AUTH CHECK ---
if "token" not in st.session_state:
    st.warning("🔒 Please login first from the main page.")
    st.stop()

# --- HELPER ---
def authenticated_request(method, endpoint, params=None):
    token = st.session_state.get("token")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.request(method, f"{API_BASE_URL}{endpoint}", headers=headers, params=params)
        if response.status_code >= 400:
            return None
        return response.json()
    except:
        return None

# --- PAGE HEADER ---
st.title("📋 User History")

# --- FILTERS ROW ---
st.markdown("### 🔍 Filters")
col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 0.5])

# Fetch data first to populate project/role dropdowns
all_history = authenticated_request("GET", "/time/history") or []

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
params = {}
if date_from: params["start_date"] = str(date_from)
if date_to: params["end_date"] = str(date_to)

# 1. Fetch RAW activity logs (for the table & basic total stats)
time_history = authenticated_request("GET", "/time/history", params=params)

# 2. Fetch Performance Metrics (for Productivity Scores)
me = authenticated_request("GET", "/me/")
user_id = me.get("id") if me else None

# Fetch from endpoints that the reverted backend actually supports
metrics_raw = []
attendance_raw = []

if user_id:
    m_params = {"user_id": user_id, "start_date": str(date_from), "end_date": str(date_to)}
    metrics_raw = authenticated_request("GET", "/admin/metrics/user_daily/", params=m_params) or []
    
    # Note: /attendance-daily/ only supports user_id filter, no date range
    a_params = {"user_id": user_id}
    attendance_raw = authenticated_request("GET", "/attendance-daily/", params=a_params) or []
    
    # Filter attendance client-side by date range
    if attendance_raw and date_from and date_to:
        attendance_raw = [a for a in attendance_raw if str(date_from) <= a.get('attendance_date', '') <= str(date_to)]

if time_history:
    df_logs = pd.DataFrame(time_history)
    df_metrics = pd.DataFrame(metrics_raw)
    df_attendance = pd.DataFrame(attendance_raw)
    
    # Apply filters to main log df
    if project_filter != "All Projects" and 'project_name' in df_logs.columns:
        df_logs = df_logs[df_logs['project_name'] == project_filter]
    
    if role_filter != "All Roles" and 'work_role' in df_logs.columns:
        df_logs = df_logs[df_logs['work_role'] == role_filter]
    
    if df_logs.empty:
        st.info("📭 No records found for the selected filters.")
    else:
        # --- PREPARE ANALYTICS DF ---
        # Group metrics and logs by date to get a unified daily view
        if not df_metrics.empty:
            df_metrics['metric_date'] = pd.to_datetime(df_metrics['metric_date']).dt.date
            # Filter metrics for selected project if needed
            if project_filter != "All Projects":
                p_id = next((p["project_id"] for p in all_history if p.get("project_name") == project_filter), None)
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

        # KPI Row 2: Attendance Distribution
        if not df_attendance.empty:
            a_counts = df_attendance['status'].value_counts().to_dict()
            st.markdown("**🕒 Attendance Summary**")
            ac1, ac2, ac3 = st.columns(3)
            ac1.metric("Present", a_counts.get("PRESENT", 0))
            ac2.metric("Absent", a_counts.get("ABSENT", 0))
            ac3.metric("Leave", a_counts.get("LEAVE", 0))

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

        # --- DAILY DETAILS VIEWER ---
        st.markdown("---")
        st.subheader("🔍 Daily Details Viewer")
        selected_row_date = st.selectbox("Select a date to see more details:", df_display['Date'].unique())
        
        if selected_row_date:
            try:
                detail_row = df_logs[df_logs['sheet_date'].astype(str) == str(selected_row_date)].iloc[0]
                with st.container(border=True):
                    d1, d2, d3 = st.columns(3)
                    d1.markdown(f"**Status**: {detail_row.get('status', 'N/A')}")
                    d2.markdown(f"**Approved By**: {detail_row.get('approved_by_user_id', 'N/A')}")
                    d3.markdown(f"**Approved At**: {detail_row.get('approved_at', 'N/A')}")
                    
                    st.markdown(f"**User Notes**: {detail_row.get('notes', 'No notes provided.')}")
                    st.markdown(f"**Manager Comment**: {detail_row.get('approval_comment', 'No comments provided.')}")
            except (IndexError, KeyError):
                st.warning("Could not load details for this date.")
        
        # --- EXPORT ---
        csv_data = df_logs.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Report (CSV)", csv_data, f"user_report_{date.today()}.csv", "text/csv")

else:
    st.info("📭 No work history found for this period. Start clocking in to track your time!")
    st.caption("Make sure you're logged in and have time entries recorded.")
