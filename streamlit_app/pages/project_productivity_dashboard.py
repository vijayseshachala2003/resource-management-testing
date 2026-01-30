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
from role_guard import setup_role_access

load_dotenv()

# =====================================================================
# PAGE CONFIG
# =====================================================================
st.set_page_config(page_title="Project Productivity & Quality Dashboard", layout="wide")
setup_role_access(__file__)

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
        response = requests.request(
            method=method,
            url=f"{API_BASE_URL}{endpoint}",
            headers=headers,
            params=params
        )
        if response.status_code >= 400:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
        return response.json()
    except Exception as e:
        st.error(f"Request failed: {str(e)}")
        return None

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_user_name_mapping() -> Dict[str, str]:
    """Fetch all users and create UUID -> name mapping"""
    users = authenticated_request("GET", "/admin/users/", params={"limit": 1000})
    if not users:
        return {}
    return {str(user["id"]): user["name"] for user in users}

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_project_name_mapping() -> Dict[str, str]:
    """Fetch all projects and create UUID -> name mapping"""
    projects = authenticated_request("GET", "/admin/projects/", params={"limit": 1000})
    if not projects:
        return {}
    return {str(project["id"]): project["name"] for project in projects}

@st.cache_data(ttl=60, show_spinner="Loading productivity data...")  # Cache for 1 minute - data changes frequently
def fetch_project_productivity_data(start_date: Optional[date] = None, end_date: Optional[date] = None,
                                     project_id: Optional[str] = None, fetch_all: bool = True) -> pd.DataFrame:
    """
    Fetch real project productivity data from API.
    Combines ProjectDailyMetrics and UserDailyMetrics for comprehensive view.
    """
    # Get name mappings
    user_map = get_user_name_mapping()
    project_map = get_project_name_mapping()
    
    # Fetch user daily metrics (aggregated by project)
    params = {}
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
    
    user_metrics = authenticated_request("GET", "/admin/metrics/user_daily/", params=params)
    if not user_metrics:
        return pd.DataFrame()
    
    # Convert to DataFrame
    df = pd.DataFrame(user_metrics)
    
    # Add user and project names
    df["user"] = df["user_id"].astype(str).map(user_map)
    df["project"] = df["project_id"].astype(str).map(project_map)
    df["role"] = df["work_role"]
    
    # Rename columns
    df = df.rename(columns={
        "metric_date": "date",
        "hours_worked": "hours_worked",
        "tasks_completed": "tasks_completed",
        "productivity_score": "productivity_score"
    })
    
    # Calculate active_users per project per date
    df["date_obj"] = pd.to_datetime(df["date"]).dt.date
    active_users_df = df.groupby(["project_id", "date_obj"])["user_id"].nunique().reset_index()
    active_users_df.columns = ["project_id", "date_obj", "active_users"]
    
    # Merge active users count
    df = df.merge(active_users_df, on=["project_id", "date_obj"], how="left")
    df["active_users"] = df["active_users"].fillna(0).astype(int)
    
    # Fetch quality ratings from API
    quality_params = {}
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
    df["quality_rating"] = df.apply(
        lambda row: quality_map.get(
            (str(row["user_id"]), str(row["project_id"]), row["date_obj"]),
            "Not Assessed"  # Default if not found - quality must be manually assessed
        ), axis=1
    )
    
    # Map quality scores
    df["quality_score"] = df.apply(
        lambda row: quality_score_map.get(
            (str(row["user_id"]), str(row["project_id"]), row["date_obj"]),
            None
        ), axis=1
    )
    
    # Map quality source
    df["quality_source"] = df.apply(
        lambda row: quality_source_map.get(
            (str(row["user_id"]), str(row["project_id"]), row["date_obj"]),
            None
        ), axis=1
    )
    
    # Select and reorder columns
    result_df = df[[
        "date", "project", "user", "role", "hours_worked",
        "tasks_completed", "quality_rating", "quality_score", "quality_source",
        "productivity_score", "active_users"
    ]].copy()
    
    # Fill missing values
    result_df["hours_worked"] = result_df["hours_worked"].fillna(0)
    result_df["tasks_completed"] = result_df["tasks_completed"].fillna(0)
    result_df["productivity_score"] = result_df["productivity_score"].fillna(0)
    result_df["quality_rating"] = result_df["quality_rating"].fillna("Not Assessed")
    # quality_score can remain None for unassessed days
    
    return result_df

def generate_mock_project_data():
    """
    MOCK DATA GENERATOR - Replace with Supabase API call
    
    Expected Supabase table: 'project_productivity'
    Columns needed:
    - date (DATE): Date of the record
    - project (TEXT): Project name
    - user (TEXT): User name
    - role (TEXT): User role
    - hours_worked (NUMERIC): Total hours worked
    - tasks_completed (INTEGER): Number of tasks completed
    - productivity_score (NUMERIC): Productivity score (0-100)
    - active_users (INTEGER): Number of active users
    
    API Call Example:
    response = supabase.table("project_productivity").select("*").execute()
    return pd.DataFrame(response.data)
    """
    projects = ["Project Alpha", "Project Beta", "Project Gamma"]
    users = ["Alice Johnson", "Bob Smith", "Charlie Davis", "Diana Miller", "Eve Wilson"]
    roles = ["Manager", "Developer", "Designer", "QA", "Developer"]
    
    data = []
    base_date = datetime.now() - timedelta(days=60)
    
    for i in range(60):
        current_date = base_date + timedelta(days=i)
        for project in projects:
            num_users = np.random.randint(2, 5)
            selected_users = np.random.choice(users, num_users, replace=False)
            
            for user in selected_users:
                user_idx = users.index(user)
                data.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "project": project,
                    "user": user,
                    "role": roles[user_idx],
                    "hours_worked": np.random.uniform(4, 10),
                    "tasks_completed": np.random.randint(2, 10),
                    "productivity_score": np.random.uniform(65, 90),
                    "active_users": num_users
                })
    
    return pd.DataFrame(data)

# =====================================================================
# UTILITY FUNCTIONS
# =====================================================================

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
st.title("📁 Project Productivity & Quality Dashboard")
st.markdown("Comprehensive analytics for project performance tracking")
st.markdown("---")

# =====================================================================
# LOAD AND PREPARE DATA
# =====================================================================
# Fetch real data from API (will be filtered by date range below)
with st.spinner("Loading data from API..."):
    # Fetch all available data first, then filter by UI selections
    df = fetch_project_productivity_data()
    
    if df.empty:
        st.warning("⚠️ No data available. Please ensure metrics are calculated.")
        st.stop()
    
    df["date"] = pd.to_datetime(df["date"])

# =====================================================================
# VIEW MODE SELECTOR (All Projects vs Specific Project)
# =====================================================================
col1, col2 = st.columns([1, 3])
with col1:
    view_mode = st.selectbox("View Mode", ["All Projects", "Specific Project"])

with col2:
    if view_mode == "Specific Project":
        selected_project = st.selectbox("Select Project", sorted(df["project"].unique()))
        df_filtered = df[df["project"] == selected_project].copy()
    else:
        selected_project = None
        df_filtered = df.copy()

# =====================================================================
# FILTERS (Date Range, Role, Project)
# =====================================================================
st.markdown("### 🔍 Filters")

# Initialize filter state
if "project_filters_applied" not in st.session_state:
    st.session_state.project_filters_applied = False
if "project_filter_date_range" not in st.session_state:
    st.session_state.project_filter_date_range = None
if "project_filter_roles" not in st.session_state:
    st.session_state.project_filter_roles = []
if "project_filter_projects" not in st.session_state:
    st.session_state.project_filter_projects = []

filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    date_range = st.date_input(
        "Date Range",
        value=st.session_state.project_filter_date_range if st.session_state.project_filter_date_range else (min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="project_date_range"
    )

with filter_col2:
    all_roles = sorted(df["role"].unique())
    filter_roles = st.multiselect(
        "Filter by Role",
        options=all_roles,
        default=st.session_state.project_filter_roles if st.session_state.project_filter_roles else all_roles,
        key="project_filter_roles_input"
    )

with filter_col3:
    if view_mode == "All Projects":
        all_projects = sorted(df["project"].unique())
        filter_projects = st.multiselect(
            "Filter by Project",
            options=all_projects,
            default=st.session_state.project_filter_projects if st.session_state.project_filter_projects else all_projects,
            key="project_filter_projects_input"
        )
    else:
        filter_projects = []


# Apply Filters Button
apply_col1, apply_col2 = st.columns([4, 1])
with apply_col2:
    apply_filters = st.button("🔍 Apply Filters", type="primary", use_container_width=True, key="apply_project_filters")

if apply_filters:
    st.session_state.project_filters_applied = True
    st.session_state.project_filter_date_range = date_range
    st.session_state.project_filter_roles = filter_roles
    st.session_state.project_filter_projects = filter_projects
    st.rerun()

# Apply filters only if button was pressed
if st.session_state.project_filters_applied:
    # Apply role filter
    if st.session_state.project_filter_roles:
        df_filtered = df_filtered[df_filtered["role"].isin(st.session_state.project_filter_roles)]
    
    # Apply project filter
    if view_mode == "All Projects" and st.session_state.project_filter_projects:
        df_filtered = df_filtered[df_filtered["project"].isin(st.session_state.project_filter_projects)]
    
    # Apply date filter
    if st.session_state.project_filter_date_range and len(st.session_state.project_filter_date_range) == 2:
        df_filtered = filter_data_by_date(df_filtered, st.session_state.project_filter_date_range[0], st.session_state.project_filter_date_range[1])
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
    st.metric("Avg Productivity", f"{avg_productivity:.1f}%")

with kpi_col4:
    avg_active_users = df_filtered.groupby("date")["active_users"].mean().mean()
    st.metric("Avg Active Users", f"{avg_active_users:.1f}")

with kpi_col5:
    if view_mode == "All Projects":
        num_projects = df_filtered["project"].nunique()
        st.metric("Active Projects", f"{num_projects}")

st.markdown("---")

# =====================================================================
# VISUALIZATIONS
# =====================================================================
st.markdown("### 📊 Visualizations")

# =====================================================================
# ROW 1: Total Hours Worked (Stacked Area) & Tasks Completed (Multi-Line)
# =====================================================================
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("#### Total Hours Worked Over Time")
    # Group by date and project
    hours_by_project = df_filtered.groupby(["date", "project"])["hours_worked"].sum().reset_index()
    
    fig1 = px.area(
        hours_by_project,
        x="date",
        y="hours_worked",
        color="project",
        line_group="project"
    )
    
    fig1.update_layout(
        height=400,
        hovermode='x unified',
        xaxis_title="Date",
        yaxis_title="Hours Worked",
        showlegend=True
    )
    st.plotly_chart(fig1, use_container_width=True)

with chart_col2:
    st.markdown("#### Total Tasks Completed Over Time")
    # Group by date and project
    tasks_by_project = df_filtered.groupby(["date", "project"])["tasks_completed"].sum().reset_index()
    
    fig2 = px.line(
        tasks_by_project,
        x="date",
        y="tasks_completed",
        color="project",
        markers=True
    )
    
    fig2.update_layout(
        height=400,
        hovermode='x unified',
        xaxis_title="Date",
        yaxis_title="Tasks Completed",
        showlegend=True
    )
    st.plotly_chart(fig2, use_container_width=True)

# =====================================================================
# ROW 2: Average Productivity & Active Users Count
# =====================================================================
chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    st.markdown("#### Average Productivity Over Time")
    # Group by date and calculate mean productivity
    if view_mode == "All Projects":
        productivity_by_date = df_filtered.groupby(["date", "project"])["productivity_score"].mean().reset_index()
        fig3 = px.line(
            productivity_by_date,
            x="date",
            y="productivity_score",
            color="project",
            markers=True
        )
    else:
        productivity_by_date = df_filtered.groupby("date")["productivity_score"].mean().reset_index()
        fig3 = px.line(
            productivity_by_date,
            x="date",
            y="productivity_score",
            markers=True
        )
        fig3.update_traces(line_color='#2ca02c')
    
    fig3.update_layout(
        height=400,
        hovermode='x unified',
        xaxis_title="Date",
        yaxis_title="Avg Productivity Score",
        showlegend=True
    )
    st.plotly_chart(fig3, use_container_width=True)

with chart_col4:
    st.markdown("#### Active Users Count Over Time")
    # Group by date and calculate mean active users
    active_users_by_date = df_filtered.groupby("date")["active_users"].mean().reset_index()
    
    fig4 = px.bar(
        active_users_by_date,
        x="date",
        y="active_users"
    )
    
    fig4.update_traces(marker_color='#9467bd')
    fig4.update_layout(
        height=400,
        hovermode='x unified',
        xaxis_title="Date",
        yaxis_title="Active Users",
        showlegend=False
    )
    st.plotly_chart(fig4, use_container_width=True)


# =====================================================================
# ROW 4: Cumulative Tasks vs Hours & Role-Based Task Completion
# =====================================================================
chart_col7 = st.columns(1)[0]

with chart_col7:
    st.markdown("#### Cumulative Tasks vs Hours Worked")
    # Calculate cumulative metrics
    cumulative_stats = df_filtered.groupby("date").agg({
        "tasks_completed": "sum",
        "hours_worked": "sum"
    }).reset_index().sort_values("date")
    
    cumulative_stats["cumulative_tasks"] = cumulative_stats["tasks_completed"].cumsum()
    cumulative_stats["cumulative_hours"] = cumulative_stats["hours_worked"].cumsum()
    
    fig7 = go.Figure()
    
    # Area for cumulative hours
    fig7.add_trace(go.Scatter(
        x=cumulative_stats["date"],
        y=cumulative_stats["cumulative_hours"],
        name="Cumulative Hours",
        fill='tozeroy',
        line=dict(color='rgba(31, 119, 180, 0.5)'),
        yaxis="y2"
    ))
    
    # Line for cumulative tasks
    fig7.add_trace(go.Scatter(
        x=cumulative_stats["date"],
        y=cumulative_stats["cumulative_tasks"],
        name="Cumulative Tasks",
        mode='lines',
        line=dict(color='#ff7f0e', width=3),
        yaxis="y"
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

# =====================================================================
# VISUALIZATION: Monthly Summary Heatmap
# =====================================================================
st.markdown("#### Monthly Summary - Heatmap")

# Create month-project heatmap for tasks completed
df_filtered["month"] = df_filtered["date"].dt.to_period("M").astype(str)
heatmap_data = df_filtered.groupby(["month", "project"])["tasks_completed"].sum().reset_index()
heatmap_pivot = heatmap_data.pivot(index="project", columns="month", values="tasks_completed").fillna(0)

fig9 = go.Figure(data=go.Heatmap(
    z=heatmap_pivot.values,
    x=heatmap_pivot.columns,
    y=heatmap_pivot.index,
    colorscale='Blues',
    text=heatmap_pivot.values,
    texttemplate='%{text:.0f}',
    textfont={"size": 10},
    colorbar=dict(title="Tasks")
))

fig9.update_layout(
    height=300,
    xaxis_title="Month",
    yaxis_title="Project",
    xaxis=dict(side="bottom")
)
st.plotly_chart(fig9, use_container_width=True)

# =====================================================================
# DATA TABLE VIEW
# =====================================================================
with st.expander("📋 View Raw Data Table"):
    st.markdown("### Raw Data")
    display_df = df_filtered[["date", "project", "user", "role", "hours_worked", 
                               "tasks_completed", "productivity_score",
                               "active_users"]].sort_values("date", ascending=False)
    
    st.dataframe(display_df, use_container_width=True, height=400)
    
    # Download button
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Data as CSV",
        data=csv,
        file_name="project_productivity_data.csv",
        mime="text/csv"
    )
    

# =====================================================================
# FOOTER
# =====================================================================
st.markdown("---")
st.markdown("*Project Productivity Dashboard | Data powered by Supabase*")