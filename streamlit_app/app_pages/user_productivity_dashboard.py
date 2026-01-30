from role_guard import get_user_role

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
import numpy as np
import requests
import os
from dotenv import load_dotenv
from typing import Dict, Optional, List

load_dotenv()

# =====================================================================
# PAGE CONFIG
# =====================================================================
st.set_page_config(page_title="User Productivity & Quality Dashboard", layout="wide")

# Basic role check
role = get_user_role()
if not role or role not in ["ADMIN", "MANAGER"]:
    st.error("Access denied. Admin or Manager role required.")
    st.stop()

# =====================================================================
# API CONFIGURATION
# =====================================================================
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# =====================================================================
# API HELPER FUNCTIONS
# =====================================================================
def authenticated_request(method: str, endpoint: str, params: Optional[Dict] = None):
    """Make authenticated API request"""
    token = st.session_state.get("token")
    if not token:
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        full_url = f"{API_BASE_URL}{endpoint}"
        # Debug logging
        if st.session_state.get("debug_mode", False):
            st.write(f"🔍 Making {method} request to: {full_url}")
            if params:
                st.write(f"🔍 Params: {params}")
        
        response = requests.request(
            method=method,
            url=full_url,
            headers=headers,
            params=params,
            timeout=30
        )
        if response.status_code >= 400:
            error_text = response.text
            st.error(f"API Error: {response.status_code} - {error_text}")
            # Print to console for debugging
            print(f"API Error {response.status_code} for {method} {full_url}: {error_text}")
            return None
        return response.json()
    except requests.exceptions.Timeout:
        st.error(f"Request timeout: Server took too long to respond for {endpoint}")
        print(f"Request timeout for {method} {endpoint}")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"Connection error: Could not reach server at {API_BASE_URL}")
        print(f"Connection error for {method} {endpoint}")
        return None
    except Exception as e:
        error_msg = f"Request failed: {str(e)}"
        st.error(error_msg)
        print(f"Request exception for {method} {endpoint}: {error_msg}")
        return None

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_user_name_mapping() -> Dict[str, str]:
    """Fetch all users and create UUID -> name mapping"""
    users = authenticated_request("GET", "/admin/users/", params={"limit": 1000})
    if not users:
        return {}
    return {str(user["id"]): user["name"] for user in users}

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_user_soul_id_mapping() -> Dict[str, str]:
    """Fetch all users and create UUID -> soul_id mapping"""
    users = authenticated_request("GET", "/admin/users/", params={"limit": 1000})
    if not users:
        return {}
    return {str(user["id"]): str(user.get("soul_id", "")) if user.get("soul_id") else "" for user in users}

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_project_name_mapping() -> Dict[str, str]:
    """Fetch all projects and create UUID -> name mapping"""
    projects = authenticated_request("GET", "/admin/projects/", params={"limit": 1000})
    if not projects:
        return {}
    return {str(project["id"]): project["name"] for project in projects}

@st.cache_data(ttl=60, show_spinner="Loading productivity data...")  # Cache for 1 minute - data changes frequently
def fetch_user_productivity_data(start_date: Optional[date] = None, end_date: Optional[date] = None, 
                                  user_id: Optional[str] = None, project_id: Optional[str] = None,
                                  fetch_all: bool = True) -> pd.DataFrame:
    """
    Fetch real user productivity data from API and combine with user/project names,
    attendance.
    """
    # Get name mappings
    user_map = get_user_name_mapping()
    project_map = get_project_name_mapping()
    
    # Fetch user daily metrics
    params = {}
    if user_id:
        params["user_id"] = user_id
    if project_id:
        params["project_id"] = project_id
    # Only add date filters if fetch_all is False (for optimization)
    if not fetch_all:
        if start_date:
            params["start_date"] = str(start_date)
        if end_date:
            params["end_date"] = str(end_date)
    else:
        # Fetch last 90 days by default to avoid loading too much data
        if not start_date:
            start_date = date.today() - timedelta(days=90)
        if not end_date:
            end_date = date.today()
        params["start_date"] = str(start_date)
        params["end_date"] = str(end_date)
    
    metrics = authenticated_request("GET", "/admin/metrics/user_daily/", params=params)
    if not metrics:
        return pd.DataFrame()
    
    # Convert to DataFrame
    df_metrics = pd.DataFrame(metrics)
    
    # Add user and project names
    df_metrics["user"] = df_metrics["user_id"].astype(str).map(user_map)
    df_metrics["project"] = df_metrics["project_id"].astype(str).map(project_map)
    df_metrics["role"] = df_metrics["work_role"]
    
    # Rename columns to match expected format
    df_metrics = df_metrics.rename(columns={
        "metric_date": "date",
        "hours_worked": "hours_worked",
        "tasks_completed": "tasks_completed",
        "productivity_score": "productivity_score"
    })
    
    # Fetch attendance data for the same date range
    attendance_params = {}
    if user_id:
        attendance_params["user_id"] = user_id
    if project_id:
        attendance_params["project_id"] = project_id
    
    attendance_data = authenticated_request("GET", "/attendance-daily/", params=attendance_params)
    
    # Create attendance mapping: (user_id, project_id, date) -> status
    attendance_map = {}
    if attendance_data:
        for att in attendance_data:
            att_date = pd.to_datetime(att.get("attendance_date")).date() if att.get("attendance_date") else None
            if att_date and start_date and end_date:
                if start_date <= att_date <= end_date:
                    key = (str(att["user_id"]), str(att["project_id"]), att_date)
                    attendance_map[key] = att.get("status", "UNKNOWN")
    
    # Map attendance status
    df_metrics["date_obj"] = pd.to_datetime(df_metrics["date"]).dt.date
    df_metrics["attendance_status"] = df_metrics.apply(
        lambda row: attendance_map.get(
            (str(row["user_id"]), str(row["project_id"]), row["date_obj"]), 
            "UNKNOWN"
        ), axis=1
    )
    
    # Normalize attendance status to match expected values
    # Database uses: PRESENT, ABSENT, LEAVE, UNKNOWN, WFH (if applicable)
    # Dashboard expects: Present, WFH, Leave, Absent
    def normalize_status(status):
        if pd.isna(status) or status is None:
            return "Absent"
        status_str = str(status).upper()
        status_mapping = {
            "PRESENT": "Present",
            "WFH": "WFH",
            "LEAVE": "Leave",
            "ABSENT": "Absent",
            "UNKNOWN": "Absent"
        }
        return status_mapping.get(status_str, "Absent")
    
    df_metrics["attendance_status"] = df_metrics["attendance_status"].apply(normalize_status)
    
    # Fetch quality ratings from API
    quality_params = {}
    if user_id:
        quality_params["user_id"] = user_id
    if project_id:
        quality_params["project_id"] = project_id
    if start_date:
        quality_params["start_date"] = str(start_date)
    if end_date:
        quality_params["end_date"] = str(end_date)
    
    quality_data = authenticated_request("GET", "/admin/metrics/user_daily/quality-ratings", params=quality_params)
    
    # Create quality mapping: (user_id, project_id, date) -> quality info
    quality_map = {}
    quality_score_map = {}
    quality_source_map = {}
    if quality_data:
        for q in quality_data:
            key = (str(q["user_id"]), str(q["project_id"]), pd.to_datetime(q["metric_date"]).date())
            # Normalize rating: "GOOD" -> "Good", "AVERAGE" -> "Average", "BAD" -> "Bad", None -> "Not Assessed"
            rating = q.get("quality_rating")
            if rating == "GOOD":
                quality_map[key] = "Good"
            elif rating == "AVERAGE":
                quality_map[key] = "Average"
            elif rating == "BAD":
                quality_map[key] = "Bad"
            else:
                quality_map[key] = "Not Assessed"
            
            # Store quality score and source
            quality_score_map[key] = q.get("quality_score")
            quality_source_map[key] = q.get("source", "MANUAL")
    
    # Map quality ratings to metrics
    df_metrics["quality_rating"] = df_metrics.apply(
        lambda row: quality_map.get(
            (str(row["user_id"]), str(row["project_id"]), row["date_obj"]),
            "Not Assessed"  # Default if not found - quality must be manually assessed
        ), axis=1
    )
    
    # Map quality scores
    df_metrics["quality_score"] = df_metrics.apply(
        lambda row: quality_score_map.get(
            (str(row["user_id"]), str(row["project_id"]), row["date_obj"]),
            None
        ), axis=1
    )
    
    # Map quality source
    df_metrics["quality_source"] = df_metrics.apply(
        lambda row: quality_source_map.get(
            (str(row["user_id"]), str(row["project_id"]), row["date_obj"]),
            None
        ), axis=1
    )
    
    # Select and reorder columns to match expected format
    result_df = df_metrics[[
        "date", "user", "project", "role", "hours_worked", 
        "tasks_completed", "quality_rating", "quality_score", "quality_source",
        "productivity_score", "attendance_status"
    ]].copy()
    
    # Fill missing values
    result_df["hours_worked"] = result_df["hours_worked"].fillna(0)
    result_df["tasks_completed"] = result_df["tasks_completed"].fillna(0)
    result_df["productivity_score"] = result_df["productivity_score"].fillna(0)
    result_df["quality_rating"] = result_df["quality_rating"].fillna("Not Assessed")
    # quality_score can remain None for unassessed days
    
    return result_df

def generate_mock_user_data():
    """
    MOCK DATA GENERATOR - Replace with Supabase API call
    
    Expected Supabase table: 'user_productivity'
    Columns needed:
    - date (DATE): Date of the record
    - user (TEXT): User name
    - project (TEXT): Project name
    - role (TEXT): User role (Manager, Developer, Designer, etc.)
    - hours_worked (NUMERIC): Total hours worked
    - tasks_completed (INTEGER): Number of tasks completed
    - productivity_score (NUMERIC): Productivity score (0-100)
    - attendance_status (TEXT): Present/WFH/Leave/Absent
    
    API Call Example:
    response = supabase.table("user_productivity").select("*").execute()
    return pd.DataFrame(response.data)
    """
    users = ["Alice Johnson", "Bob Smith", "Charlie Davis", "Diana Miller", "Eve Wilson"]
    projects = ["Project Alpha", "Project Beta", "Project Gamma"]
    roles = ["Manager", "Developer", "Designer", "QA", "Developer"]
    attendance_statuses = ["Present", "WFH", "Leave", "Absent"]
    
    data = []
    base_date = datetime.now() - timedelta(days=60)
    
    for i in range(60):
        current_date = base_date + timedelta(days=i)
        for idx, user in enumerate(users):
            attendance = np.random.choice(attendance_statuses, p=[0.4, 0.4, 0.1, 0.1])
            data.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "user": user,
                "project": np.random.choice(projects),
                "role": roles[idx],
                "hours_worked": np.random.uniform(6, 10) if attendance in ["Present", "WFH"] else 0,
                "tasks_completed": np.random.randint(3, 12) if attendance in ["Present", "WFH"] else 0,
                "productivity_score": np.random.uniform(60, 95) if attendance in ["Present", "WFH"] else 0,
                "attendance_status": attendance
            })
    
    return pd.DataFrame(data)

# =====================================================================
# UTILITY FUNCTIONS
# =====================================================================

def calculate_moving_average(df, column, window=7):
    """Calculate moving average for smoothing trends"""
    return df[column].rolling(window=window, min_periods=1).mean()

def filter_data_by_date(df, start_date, end_date):
    """Filter dataframe by date range"""
    df["date"] = pd.to_datetime(df["date"])
    return df[(df["date"] >= pd.to_datetime(start_date)) & 
              (df["date"] <= pd.to_datetime(end_date))]

# =====================================================================
# AUTH CHECK
# =====================================================================
if "token" not in st.session_state:
    st.warning("🔒 Please login first from the main page.")
    st.stop()

# =====================================================================
# HEADER
# =====================================================================
st.title("👤 User Productivity & Quality Dashboard")
st.markdown("Comprehensive analytics for individual user performance tracking")
st.markdown("---")

# =====================================================================
# LOAD AND PREPARE DATA
# =====================================================================
# Fetch real data from API (will be filtered by date range below)
with st.spinner("Loading data from API..."):
    # Fetch all available data first, then filter by UI selections
    df = fetch_user_productivity_data()
    
    if df.empty:
        st.warning("⚠️ No data available. Please ensure metrics are calculated.")
        st.stop()
    
    df["date"] = pd.to_datetime(df["date"])

# =====================================================================
# VIEW MODE SELECTOR (All Users vs Specific User)
# =====================================================================
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    view_mode = st.selectbox("View Mode", ["All Users", "Specific User"])

with col2:
    if view_mode == "Specific User":
        # Get soul_id mapping for search
        soul_id_map = get_user_soul_id_mapping()
        user_map = get_user_name_mapping()
        
        if not user_map:
            st.error("⚠️ Unable to load users. Please check your connection and try again.")
            st.stop()
        
        # Create reverse mapping: soul_id -> user_id
        soul_to_user_id = {v: k for k, v in soul_id_map.items() if v}
        # Create user options with soul_id display
        user_options = []
        for user_id, user_name in user_map.items():
            soul_id = soul_id_map.get(user_id, "")
            if soul_id:
                user_options.append(f"{user_name} (Soul ID: {soul_id})")
            else:
                user_options.append(user_name)
        
        if not user_options:
            st.error("⚠️ No users available to select.")
            st.stop()
        
        selected_user_display = st.selectbox("Select User", sorted(user_options))
        
        # Extract user name from selection
        if selected_user_display:
            if "(Soul ID:" in selected_user_display:
                selected_user = selected_user_display.split(" (Soul ID:")[0]
            else:
                selected_user = selected_user_display
            df_filtered = df[df["user"] == selected_user].copy()
        else:
            selected_user = None
            df_filtered = pd.DataFrame()
    else:
        selected_user = None
        df_filtered = df.copy()

with col3:
    # Soul ID Search (only for All Users mode)
    if view_mode == "All Users":
        if "user_filter_soul_id" not in st.session_state:
            st.session_state.user_filter_soul_id = ""
        soul_id_search = st.text_input(
            "🔍 Search by Soul ID", 
            placeholder="Enter Soul ID...", 
            value=st.session_state.user_filter_soul_id,
            key="soul_id_search_input"
        )
    else:
        soul_id_search = None

# =====================================================================
# FILTERS (Date Range, Role, Project)
# =====================================================================
st.markdown("### 🔍 Filters")
filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

# Initialize filter state
if "user_filters_applied" not in st.session_state:
    st.session_state.user_filters_applied = False
if "user_filter_date_range" not in st.session_state:
    st.session_state.user_filter_date_range = None
if "user_filter_roles" not in st.session_state:
    st.session_state.user_filter_roles = []
if "user_filter_projects" not in st.session_state:
    st.session_state.user_filter_projects = []
if "user_filter_soul_id" not in st.session_state:
    st.session_state.user_filter_soul_id = ""
if "user_filter_quality" not in st.session_state:
    st.session_state.user_filter_quality = []

with filter_col1:
    min_date = df["date"].min().date()
    max_date = max(df["date"].max().date(), date.today())
    date_range = st.date_input(
        "Date Range",
        value=st.session_state.user_filter_date_range if st.session_state.user_filter_date_range else (min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="user_date_range"
    )

with filter_col2:
    if view_mode == "All Users":
        all_roles = sorted(df["role"].unique())
        filter_roles = st.multiselect(
            "Filter by Role",
            options=all_roles,
            default=st.session_state.user_filter_roles if st.session_state.user_filter_roles else all_roles,
            key="user_filter_roles_input"
        )
    else:
        filter_roles = []

with filter_col3:
    all_projects = sorted(df["project"].unique())
    filter_projects = st.multiselect(
        "Filter by Project",
        options=all_projects,
        default=st.session_state.user_filter_projects if st.session_state.user_filter_projects else all_projects,
        key="user_filter_projects_input"
    )

with filter_col4:
    filter_quality = st.multiselect(
        "Filter by Quality",
        options=["Good", "Average", "Bad", "Not Assessed"],
        default=st.session_state.user_filter_quality if st.session_state.user_filter_quality else ["Good", "Average", "Bad", "Not Assessed"],
        key="user_filter_quality_input"
    )


# Apply Filters Button
apply_col1, apply_col2 = st.columns([4, 1])
with apply_col2:
    apply_filters = st.button("🔍 Apply Filters", type="primary", use_container_width=True, key="apply_user_filters")

if apply_filters:
    st.session_state.user_filters_applied = True
    st.session_state.user_filter_date_range = date_range
    st.session_state.user_filter_roles = filter_roles
    st.session_state.user_filter_projects = filter_projects
    st.session_state.user_filter_quality = filter_quality
    if view_mode == "All Users":
        st.session_state.user_filter_soul_id = soul_id_search if soul_id_search else ""
    st.rerun()

# Apply filters only if button was pressed
if st.session_state.user_filters_applied:
    # Apply role filter
    if view_mode == "All Users" and st.session_state.user_filter_roles:
        df_filtered = df_filtered[df_filtered["role"].isin(st.session_state.user_filter_roles)]
    
    # Apply project filter
    if st.session_state.user_filter_projects:
        df_filtered = df_filtered[df_filtered["project"].isin(st.session_state.user_filter_projects)]
    
    # Apply quality filter
    if st.session_state.user_filter_quality:
        df_filtered = df_filtered[df_filtered["quality_rating"].isin(st.session_state.user_filter_quality)]
    
    # Apply date filter
    if st.session_state.user_filter_date_range and len(st.session_state.user_filter_date_range) == 2:
        df_filtered = filter_data_by_date(df_filtered, st.session_state.user_filter_date_range[0], st.session_state.user_filter_date_range[1])
    
    # Apply soul_id search filter
    if view_mode == "All Users" and st.session_state.user_filter_soul_id and st.session_state.user_filter_soul_id.strip():
        soul_id_map = get_user_soul_id_mapping()
        user_map = get_user_name_mapping()
        # Find user IDs matching the soul_id
        search_term = st.session_state.user_filter_soul_id.strip().lower()
        matching_user_ids = [user_id for user_id, soul_id in soul_id_map.items() if soul_id and search_term in str(soul_id).lower()]
        matching_user_names = [user_map.get(uid) for uid in matching_user_ids if user_map.get(uid)]
        if matching_user_names:
            df_filtered = df_filtered[df_filtered["user"].isin(matching_user_names)]
        else:
            df_filtered = pd.DataFrame()  # No matches
            st.warning(f"⚠️ No users found with Soul ID containing: {st.session_state.user_filter_soul_id}")
else:
    # Default: show all data without filters
    pass

st.markdown("---")

# =====================================================================
# MONTHLY SUMMARY - KPI CARDS
# =====================================================================
st.markdown("### 📈 Monthly Summary of Metrics")
kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5, kpi_col6 = st.columns(6)

with kpi_col1:
    total_hours = df_filtered["hours_worked"].sum()
    st.metric("Total Hours Worked", f"{total_hours:.1f} hrs")

with kpi_col2:
    total_tasks = df_filtered["tasks_completed"].sum()
    st.metric("Total Tasks Completed", f"{int(total_tasks)}")

with kpi_col3:
    avg_productivity = df_filtered["productivity_score"].mean()
    st.metric("Avg Productivity Score", f"{avg_productivity:.1f}%")

with kpi_col4:
    # Calculate quality assessment coverage
    assessed_count = len(df_filtered[df_filtered["quality_rating"] != "Not Assessed"])
    total_count = len(df_filtered)
    quality_coverage = (assessed_count / total_count * 100) if total_count > 0 else 0
    st.metric("Quality Coverage", f"{quality_coverage:.1f}%")

with kpi_col5:
    if view_mode == "All Users":
        unique_users = df_filtered["user"].nunique()
        st.metric("Active Users", f"{unique_users}")
    else:
        # Show average quality score (only for assessed days with valid scores)
        assessed_df = df_filtered[df_filtered["quality_rating"] != "Not Assessed"]
        assessed_with_scores = assessed_df[assessed_df["quality_score"].notna()]
        if len(assessed_with_scores) > 0:
            avg_quality_score = assessed_with_scores["quality_score"].mean()
            st.metric("Avg Quality Score", f"{avg_quality_score:.1f}")
        else:
            st.metric("Avg Quality Score", "N/A")

st.markdown("---")

# =====================================================================
# VISUALIZATIONS
# =====================================================================
st.markdown("### 📊 Visualizations")

# =====================================================================
# ROW 1: Total Hours Worked & Total Tasks Completed
# =====================================================================
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("#### Total Hours Worked Over Time")
    # Group by date and sum hours
    hours_by_date = df_filtered.groupby("date")["hours_worked"].sum().reset_index()
    
    if len(hours_by_date) > 0:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=hours_by_date["date"],
            y=hours_by_date["hours_worked"],
            mode='lines+markers',
            name='Hours Worked',
            fill='tozeroy',
            line=dict(color='#1f77b4', width=2),
            marker=dict(size=4)
        ))
        
        fig1.update_layout(
            height=400,
            hovermode='x unified',
            xaxis_title="Date",
            yaxis_title="Hours Worked",
            showlegend=True,
            yaxis=dict(range=[0, max(hours_by_date["hours_worked"].max() * 1.1, 1)])  # Always show from 0
        )
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("📊 No data to display")

with chart_col2:
    st.markdown("#### Total Tasks Completed Over Time")
    # Group by date and sum tasks
    tasks_by_date = df_filtered.groupby("date")["tasks_completed"].sum().reset_index()
    
    if len(tasks_by_date) > 0:
        fig2 = px.line(
            tasks_by_date,
            x="date",
            y="tasks_completed",
            markers=True,
            line_shape='spline'
        )
        
        fig2.update_traces(line_color='#ff7f0e', marker=dict(size=6))
        fig2.update_layout(
            height=400,
            hovermode='x unified',
            xaxis_title="Date",
            yaxis_title="Tasks Completed",
            showlegend=False,
            yaxis=dict(range=[0, max(tasks_by_date["tasks_completed"].max() * 1.1, 1)])  # Always show from 0
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("📊 No data to display")

# =====================================================================
# ROW 2: Productivity Score & Quality Distribution
# =====================================================================
chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    st.markdown("#### Average Productivity Score Over Time")
    # Group by date and calculate mean productivity
    productivity_by_date = df_filtered.groupby("date")["productivity_score"].mean().reset_index()
    
    if len(productivity_by_date) > 0:
        # Fill NaN with 0 for display
        productivity_by_date["productivity_score"] = productivity_by_date["productivity_score"].fillna(0)
        productivity_by_date["moving_avg"] = calculate_moving_average(productivity_by_date, "productivity_score", window=7)
        
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=productivity_by_date["date"],
            y=productivity_by_date["productivity_score"],
            mode='lines+markers',
            name='Daily Score',
            line=dict(color='lightblue', width=1),
            marker=dict(size=4),
            opacity=0.5
        ))
        fig3.add_trace(go.Scatter(
            x=productivity_by_date["date"],
            y=productivity_by_date["moving_avg"],
            mode='lines',
            name='7-Day Moving Avg',
            line=dict(color='#2ca02c', width=3)
        ))
        
        max_score = productivity_by_date["productivity_score"].max()
        fig3.update_layout(
            height=400,
            hovermode='x unified',
            xaxis_title="Date",
            yaxis_title="Productivity Score",
            showlegend=True,
            yaxis=dict(range=[0, max(max_score * 1.1, 10)])  # Always show from 0
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("📊 No data to display")

with chart_col4:
    st.markdown("#### Quality Rating Distribution")
    # Count quality ratings
    quality_counts = df_filtered["quality_rating"].value_counts().reset_index()
    quality_counts.columns = ["quality_rating", "count"]
    
    if len(quality_counts) > 0 and quality_counts["count"].sum() > 0:
        # Order by quality rating
        quality_order = ["Good", "Average", "Bad", "Not Assessed"]
        quality_counts["quality_rating"] = pd.Categorical(
            quality_counts["quality_rating"], 
            categories=quality_order, 
            ordered=True
        )
        quality_counts = quality_counts.sort_values("quality_rating")
        
        colors_map = {
            "Good": "#2ca02c",
            "Average": "#ff7f0e", 
            "Bad": "#d62728",
            "Not Assessed": "#888888"
        }
        
        fig4 = px.bar(
            quality_counts,
            x="quality_rating",
            y="count",
            color="quality_rating",
            color_discrete_map=colors_map
        )
        
        fig4.update_layout(
            height=400,
            hovermode='x unified',
            xaxis_title="Quality Rating",
            yaxis_title="Count",
            showlegend=False
        )
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("📊 No data to display")

# =====================================================================
# ROW 3: Attendance Status & Quality Score Trend
# =====================================================================
chart_col5, chart_col6 = st.columns(2)

with chart_col5:
    st.markdown("#### Attendance Status Over Time")
    # Group by date and attendance status
    attendance_by_date = df_filtered.groupby(["date", "attendance_status"]).size().reset_index(name="count")
    
    if len(attendance_by_date) > 0:
        attendance_pivot = attendance_by_date.pivot(index="date", columns="attendance_status", values="count").fillna(0)
        
        fig5 = go.Figure()
        colors = {'Present': '#2ca02c', 'WFH': '#1f77b4', 'Leave': '#ff7f0e', 'Absent': '#d62728'}
        
        for status in attendance_pivot.columns:
            fig5.add_trace(go.Bar(
                x=attendance_pivot.index,
                y=attendance_pivot[status],
                name=status,
                marker_color=colors.get(status, '#888888')
            ))
        
        fig5.update_layout(
            barmode='stack',
            height=400,
            hovermode='x unified',
            xaxis_title="Date",
            yaxis_title="Count",
            showlegend=True
        )
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info("📊 No data to display")

with chart_col6:
    st.markdown("#### Quality Score Trend (Manually Assessed)")
    # Filter to only assessed days and group by date
    assessed_df = df_filtered[df_filtered["quality_rating"] != "Not Assessed"].copy()
    
    if len(assessed_df) > 0:
        # Filter to only days with valid quality scores
        assessed_with_scores = assessed_df[assessed_df["quality_score"].notna()].copy()
        if len(assessed_with_scores) > 0:
            quality_by_date = assessed_with_scores.groupby("date")["quality_score"].mean().reset_index()
            quality_by_date = quality_by_date.sort_values("date")
            
            if len(quality_by_date) > 0:
                fig6 = go.Figure()
                fig6.add_trace(go.Scatter(
                    x=quality_by_date["date"],
                    y=quality_by_date["quality_score"],
                    mode='lines+markers',
                    name='Quality Score',
                    line=dict(color='#9467bd', width=2),
                    marker=dict(size=6)
                ))
                
                fig6.update_layout(
                    height=400,
                    hovermode='x unified',
                    xaxis_title="Date",
                    yaxis_title="Quality Score",
                    yaxis=dict(range=[0, 10]),
                    showlegend=False
                )
                st.plotly_chart(fig6, use_container_width=True)
            else:
                st.info("📊 No data to display")
        else:
            st.info("📊 No data to display")
    else:
        st.info("📊 No data to display")

# =====================================================================
# ROW 4: Cumulative Tasks vs Hours
# =====================================================================
chart_col7 = st.columns(1)[0]

with chart_col7:
    st.markdown("#### Cumulative Tasks vs Hours Worked")
    # Group by date and calculate cumulative sums
    daily_stats = df_filtered.groupby("date").agg({
        "tasks_completed": "sum",
        "hours_worked": "sum"
    }).reset_index()
    
    if len(daily_stats) > 0:
        # Fill NaN with 0
        daily_stats["tasks_completed"] = daily_stats["tasks_completed"].fillna(0)
        daily_stats["hours_worked"] = daily_stats["hours_worked"].fillna(0)
        daily_stats["cumulative_tasks"] = daily_stats["tasks_completed"].cumsum()
        daily_stats["cumulative_hours"] = daily_stats["hours_worked"].cumsum()
        
        fig7 = go.Figure()
        fig7.add_trace(go.Scatter(
            x=daily_stats["date"],
            y=daily_stats["cumulative_tasks"],
            name="Cumulative Tasks",
            yaxis="y",
            line=dict(color='#1f77b4', width=2)
        ))
        fig7.add_trace(go.Scatter(
            x=daily_stats["date"],
            y=daily_stats["cumulative_hours"],
            name="Cumulative Hours",
            yaxis="y2",
            line=dict(color='#ff7f0e', width=2)
        ))
        
        fig7.update_layout(
            height=400,
            hovermode='x unified',
            xaxis_title="Date",
            yaxis=dict(title="Cumulative Tasks", side="left"),
            yaxis2=dict(title="Cumulative Hours", overlaying="y", side="right"),
            showlegend=True
        )
        st.plotly_chart(fig7, use_container_width=True)
    else:
        st.info("📊 No data to display")

# =====================================================================
# DATA TABLE VIEW
# =====================================================================
with st.expander("📋 View Raw Data Table"):
    st.markdown("### Raw Data")
    display_df = df_filtered[["date", "user", "project", "role", "hours_worked", 
                               "tasks_completed", "quality_rating", "quality_score", "quality_source",
                               "productivity_score", "attendance_status"]].sort_values("date", ascending=False)
    
    # Format quality_score for display
    if "quality_score" in display_df.columns:
        display_df["quality_score"] = display_df["quality_score"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
    
    st.dataframe(display_df, use_container_width=True, height=400)
    
    # Download button
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Data as CSV",
        data=csv,
        file_name="user_productivity_data.csv",
        mime="text/csv"
    )
    
    # Info about quality
    st.info("💡 **Quality Note**: Quality ratings are manually assessed and separate from productivity. 'Not Assessed' means no quality evaluation has been done for that day.")
    
    # Quick quality assessment button
    st.markdown("---")
    st.markdown("### ⭐ Quick Quality Assessment")
    st.markdown("Assess quality for selected rows or go to the Quality Assessment tab in Admin Projects for more options.")
    
    assess_col1, assess_col2 = st.columns([1, 4])
    with assess_col1:
        if st.button("📝 Assess Quality", use_container_width=True):
            st.info("💡 Please navigate to 'Admin Projects' page from the sidebar to assess quality.")

# =====================================================================
# FOOTER
# =====================================================================
st.markdown("---")
st.markdown("*User Productivity & Quality Dashboard | Data powered by Supabase*")