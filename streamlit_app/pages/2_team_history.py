import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from role_guard import setup_role_access

load_dotenv()

# --- CONFIGURATION ---
st.set_page_config(page_title="Team History", layout="wide")
setup_role_access(__file__)
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# --- AUTH CHECK ---
if "token" not in st.session_state:
    st.warning("🔒 Please login first from the main page.")
    st.stop()

# --- HELPER FUNCTIONS ---
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
st.title("👥 Team History")
st.markdown("View work history and productivity of your team members.")

# --- ACCESS CONTROL: Project Managers Only ---
# Check if the user has any projects they manage
manager_projects = authenticated_request("GET", "/project_manager/projects")

# Also check the user's role from /me endpoint
me = authenticated_request("GET", "/me/")
user_role = me.get("role", "").upper() if me else ""

# Allow access if:
# 1. User has projects they manage (is a project manager for at least one project)
# 2. OR User has a manager/admin role
is_manager = bool(manager_projects)
is_admin_role = user_role in ["ADMIN", "PROJECT_MANAGER", "MANAGER", "LEAD"]

if not is_manager and not is_admin_role:
    st.error("🚫 **Access Denied**")
    st.warning("This page is only available to **Project Managers** or users who are leading teams.")
    st.info("If you believe you should have access, please contact your administrator.")
    st.stop()

if not manager_projects:
    st.info("👋 You have manager access, but you're not currently assigned to manage any projects.")
    st.caption("Please ask an admin to assign you to a project as a manager.")
    st.stop()

# --- FILTERS ---
st.markdown("### 🔍 Filter Team Data")

# 1. Member Selector (First for admin mode, so we can filter projects by member)
member_options = {}
selected_member_name = None
selected_member_id = None
selected_project_id = None
member_projects = []  # Projects the selected member has worked on

col1, col2, col3, col4 = st.columns([1.5, 1.5, 1, 1])

with col1:
    # Check if user is an admin - if so, allow search across all users
    if is_admin_role:
        st.caption("🔍 Admin Mode: Search any user")
        # Fetch all users for admin search
        all_users = authenticated_request("GET", "/admin/users/") or []
        
        # Use text input with autocomplete-like selectbox
        search_query = st.text_input("Search by name", placeholder="Type to search...")
        
        if search_query:
            # Filter users matching the search query
            matching_users = [u for u in all_users if search_query.lower() in u.get("name", "").lower()]
            if matching_users:
                matching_options = {u["name"]: u["id"] for u in matching_users}
                selected_member_name = st.selectbox("Select from matches", list(matching_options.keys()), key="admin_member_select")
                selected_member_id = matching_options[selected_member_name]
            else:
                st.info("No users found matching your search.")
        else:
            st.info("Type a name to search for team members.")
    else:
        # Regular project manager view - first select project
        project_options = {p["name"]: p["id"] for p in manager_projects}
        selected_project_name = st.selectbox("1. Select Project", list(project_options.keys()))
        selected_project_id = project_options[selected_project_name]
        
        # Then get members of that project
        if selected_project_id:
            team_members = authenticated_request("GET", f"/project_manager/projects/{selected_project_id}/members")
            if team_members:
                member_options = {m["name"]: m["id"] for m in team_members}

with col2:
    if is_admin_role:
        # For admin: Show projects the selected member has worked on
        if selected_member_id:
            # Fetch member's project history from metrics
            member_metrics = authenticated_request("GET", "/admin/metrics/user_daily/", params={"user_id": selected_member_id}) or []
            
            # Get unique project IDs from their metrics
            project_ids = list(set([m.get("project_id") for m in member_metrics if m.get("project_id")]))
            
            if project_ids:
                # Fetch project details
                all_projects = authenticated_request("GET", "/admin/projects/") or []
                member_projects = [p for p in all_projects if p.get("id") in project_ids]
                
                if member_projects:
                    st.caption(f"📁 Projects {selected_member_name} worked on:")
                    project_options = {"All Projects": None}
                    project_options.update({p["name"]: p["id"] for p in member_projects})
                    selected_project_name = st.selectbox("Filter by Project", list(project_options.keys()), key="admin_project_select")
                    selected_project_id = project_options[selected_project_name]
                else:
                    st.caption("No project history found for this user.")
            else:
                st.caption("No project history found for this user.")
        else:
            st.info("👈 Select a member first to see their projects.")
    else:
        # Regular PM view - member selector
        if member_options:
            selected_member_name = st.selectbox("2. Select Team Member", list(member_options.keys()))
            selected_member_id = member_options[selected_member_name]
        else:
            st.warning("No active members found in this project.")

# 3. Date Filters
with col3:
    date_from = st.date_input("From Date", value=date.today() - timedelta(days=30))

with col4:
    date_to = st.date_input("To Date", value=date.today())

st.markdown("---")

# --- FETCH PROJECT-WIDE ROLE BREAKDOWN ---
if selected_project_id:
    st.subheader("📊 Role Allocation Breakdown")
    # Fetch all members of this project to calculate breakdown
    all_members = authenticated_request("GET", f"/project_manager/projects/{selected_project_id}/members")
    if all_members:
        members_df = pd.DataFrame(all_members)
        if 'work_role' in members_df.columns:
            role_counts = members_df['work_role'].value_counts().reset_index()
            role_counts.columns = ['Role', 'Allocated Count']
            
            # Fetch real attendance data for today to calculate Present/Absent
            from datetime import datetime
            today_str = str(datetime.now().date())
            
            # For each member, check their attendance status today
            present_by_role = {}
            absent_by_role = {}
            
            for _, member in members_df.iterrows():
                member_id = member.get('id')
                member_role = member.get('work_role', 'Unknown')
                
                # Fetch attendance for this member (today only)
                attendance = authenticated_request("GET", "/attendance-daily/", params={"user_id": member_id})
                
                # Find today's attendance
                today_status = "UNKNOWN"
                if attendance:
                    for a in attendance:
                        if a.get('attendance_date') == today_str:
                            today_status = a.get('status', 'UNKNOWN')
                            break
                
                # Count by role
                if member_role not in present_by_role:
                    present_by_role[member_role] = 0
                    absent_by_role[member_role] = 0
                
                if today_status in ["PRESENT", "WFH", "LEAVE"]:
                    present_by_role[member_role] += 1
                elif today_status in ["ABSENT"]:
                    absent_by_role[member_role] += 1
                # UNKNOWN status counts as neither
            
            # Add real counts to the table
            role_counts['Present Today'] = role_counts['Role'].apply(lambda r: present_by_role.get(r, 0))
            role_counts['Absent Today'] = role_counts['Role'].apply(lambda r: absent_by_role.get(r, 0))
            
            st.table(role_counts)
    st.markdown("---")

# --- FETCH & DISPLAY MEMBER DATA ---
if selected_project_id and selected_member_id:
    # 1. Fetch Performance Metrics (from existing endpoint)
    m_params = {
        "user_id": selected_member_id, 
        "project_id": selected_project_id,
        "start_date": str(date_from), 
        "end_date": str(date_to)
    }
    metrics_data = authenticated_request("GET", "/admin/metrics/user_daily/", params=m_params) or []
    
    # 2. Fetch Attendance Data (endpoint only supports user_id, not date ranges)
    a_params = {"user_id": selected_member_id}
    attendance_data = authenticated_request("GET", "/attendance-daily/", params=a_params) or []
    
    # Filter attendance client-side by date range
    if attendance_data and date_from and date_to:
        attendance_data = [a for a in attendance_data if str(date_from) <= a.get('attendance_date', '') <= str(date_to)]
    
    attendances = {a['attendance_date']: a for a in attendance_data}

    if metrics_data:
        df = pd.DataFrame(metrics_data)
        
        # --- ALL-TIME SNAPSHOT ---
        st.subheader(f"🏆 {selected_member_name} Performance Snapshot")
        s1, s2, s3 = st.columns(3)
        
        total_hours = df['hours_worked'].sum()
        total_tasks = int(df['tasks_completed'].sum())
        avg_score = df['productivity_score'].mean()
        
        s1.metric("Total Hours", f"{total_hours:.1f}h")
        s2.metric("Total Tasks", total_tasks)
        s3.metric("Avg Score", f"{avg_score:.1f}/10")

        # --- TREND CHARTS ---
        st.subheader("📈 Productivity & Hours Trends")
        import plotly.express as px
        df['metric_date'] = pd.to_datetime(df['metric_date'])
        df = df.sort_values('metric_date')
        
        c1, c2 = st.columns(2)
        with c1:
            fig_p = px.line(df, x='metric_date', y='productivity_score', title='Productivity Trend', markers=True)
            fig_p.update_layout(yaxis_range=[0, 11])
            st.plotly_chart(fig_p, use_container_width=True)
        with c2:
            fig_h = px.bar(df, x='metric_date', y='hours_worked', title='Daily Hours', color='hours_worked')
            st.plotly_chart(fig_h, use_container_width=True)

        st.markdown("---")
        
        st.subheader("📋 Daily Work Breakdown")
        # Prepare Display Table
        df_display = df[['metric_date', 'hours_worked', 'tasks_completed', 'productivity_score', 'notes']].copy()
        
        # Enrich with attendance status
        df_display['Status'] = df_display['metric_date'].apply(lambda x: attendances.get(str(x.date()), {}).get('status', 'PRESENT'))
        
        df_display.columns = ['Date', 'Hours', 'Tasks', 'Score', 'Notes', 'Status']
        df_display['Date'] = df_display['Date'].dt.date
        
        # Reorder columns
        df_display = df_display[['Date', 'Hours', 'Tasks', 'Score', 'Status', 'Notes']]
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Export
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Summary (CSV)", csv, f"team_member_report_{selected_member_name}.csv", "text/csv")
        
    else:
        st.info(f"ℹ️ No analytics data found for **{selected_member_name}** in this period.")

elif not selected_member_id:
    st.info("👈 Please select a team member to view their history.")
