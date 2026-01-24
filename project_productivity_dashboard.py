import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
import numpy as np

# =====================================================================
# PAGE CONFIG
# =====================================================================
st.set_page_config(page_title="Project Productivity & Quality Dashboard", layout="wide")

# =====================================================================
# API/DATABASE CONNECTION SETUP
# =====================================================================
# TODO: Replace mock function with actual Supabase API call
# 
# Example Supabase setup:
# from supabase import create_client, Client
# SUPABASE_URL = "your-supabase-url"
# SUPABASE_KEY = "your-supabase-key"
# supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
#
# Then replace generate_mock_project_data() with:
# def fetch_project_data():
#     response = supabase.table("project_productivity").select("*").execute()
#     return pd.DataFrame(response.data)
# =====================================================================

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
    - quality_rating (TEXT): Quality rating (Good/Average/Bad)
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
                    "quality_rating": np.random.choice(["Good", "Average", "Bad"], p=[0.5, 0.35, 0.15]),
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
# SESSION STATE INITIALIZATION
# =====================================================================
if "project_data" not in st.session_state:
    st.session_state.project_data = generate_mock_project_data()

# =====================================================================
# HEADER
# =====================================================================
st.title("📁 Project Productivity & Quality Dashboard")
st.markdown("Comprehensive analytics for project performance tracking")
st.markdown("---")

# =====================================================================
# LOAD AND PREPARE DATA
# =====================================================================
# In production, replace this with: df = fetch_project_data()
df = st.session_state.project_data.copy()
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
# FILTERS (Date Range, Role, Project, Quality)
# =====================================================================
st.markdown("### 🔍 Filters")
filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

with filter_col1:
    min_date = df_filtered["date"].min().date()
    max_date = df_filtered["date"].max().date()
    date_range = st.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="project_date_range"
    )

with filter_col2:
    filter_roles = st.multiselect(
        "Filter by Role",
        options=sorted(df_filtered["role"].unique()),
        default=sorted(df_filtered["role"].unique())
    )
    df_filtered = df_filtered[df_filtered["role"].isin(filter_roles)]

with filter_col3:
    if view_mode == "All Projects":
        filter_projects = st.multiselect(
            "Filter by Project",
            options=sorted(df_filtered["project"].unique()),
            default=sorted(df_filtered["project"].unique())
        )
        df_filtered = df_filtered[df_filtered["project"].isin(filter_projects)]

with filter_col4:
    filter_quality = st.multiselect(
        "Filter by Quality",
        options=["Good", "Average", "Bad"],
        default=["Good", "Average", "Bad"]
    )
    df_filtered = df_filtered[df_filtered["quality_rating"].isin(filter_quality)]

# Apply date filter
if len(date_range) == 2:
    df_filtered = filter_data_by_date(df_filtered, date_range[0], date_range[1])

st.markdown("---")

# =====================================================================
# MONTHLY SUMMARY - KPI CARDS
# =====================================================================
st.markdown("### 📈 Monthly Summary of Metrics")
kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)

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
    else:
        good_quality_pct = (df_filtered["quality_rating"] == "Good").sum() / len(df_filtered) * 100 if len(df_filtered) > 0 else 0
        st.metric("Good Quality %", f"{good_quality_pct:.1f}%")

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
# ROW 3: Quality Breakdown & Daily Performance Stats
# =====================================================================
chart_col5, chart_col6 = st.columns(2)

with chart_col5:
    st.markdown("#### Quality Breakdown (Good/Avg/Bad)")
    # Group by project and quality rating
    quality_by_project = df_filtered.groupby(["project", "quality_rating"]).size().reset_index(name="count")
    
    fig5 = px.bar(
        quality_by_project,
        x="project",
        y="count",
        color="quality_rating",
        barmode="stack",
        color_discrete_map={'Good': '#2ca02c', 'Average': '#ff7f0e', 'Bad': '#d62728'}
    )
    
    fig5.update_layout(
        height=400,
        xaxis_title="Project",
        yaxis_title="Count",
        showlegend=True
    )
    st.plotly_chart(fig5, use_container_width=True)

with chart_col6:
    st.markdown("#### Daily Performance Stats")
    # Normalize metrics to 0-100 scale for comparison
    daily_stats = df_filtered.groupby("date").agg({
        "hours_worked": "sum",
        "tasks_completed": "sum",
        "productivity_score": "mean"
    }).reset_index()
    
    # Normalize for visualization (scale to 0-100)
    max_hours = daily_stats["hours_worked"].max()
    max_tasks = daily_stats["tasks_completed"].max()
    
    daily_stats["hours_normalized"] = (daily_stats["hours_worked"] / max_hours * 100) if max_hours > 0 else 0
    daily_stats["tasks_normalized"] = (daily_stats["tasks_completed"] / max_tasks * 100) if max_tasks > 0 else 0
    
    fig6 = go.Figure()
    fig6.add_trace(go.Scatter(
        x=daily_stats["date"],
        y=daily_stats["hours_normalized"],
        name="Hours (normalized)",
        mode='lines+markers',
        line=dict(color='#1f77b4')
    ))
    fig6.add_trace(go.Scatter(
        x=daily_stats["date"],
        y=daily_stats["tasks_normalized"],
        name="Tasks (normalized)",
        mode='lines+markers',
        line=dict(color='#ff7f0e')
    ))
    fig6.add_trace(go.Scatter(
        x=daily_stats["date"],
        y=daily_stats["productivity_score"],
        name="Productivity Score",
        mode='lines+markers',
        line=dict(color='#2ca02c')
    ))
    
    fig6.update_layout(
        height=400,
        hovermode='x unified',
        xaxis_title="Date",
        yaxis_title="Normalized Value (0-100)",
        showlegend=True
    )
    st.plotly_chart(fig6, use_container_width=True)

# =====================================================================
# ROW 4: Cumulative Tasks vs Hours & Role-Based Task Completion
# =====================================================================
chart_col7, chart_col8 = st.columns(2)

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

with chart_col8:
    st.markdown("#### Role-Based Task Completion")
    # Group by role and project
    role_task_completion = df_filtered.groupby(["role", "project"])["tasks_completed"].sum().reset_index()
    
    fig8 = px.bar(
        role_task_completion,
        x="role",
        y="tasks_completed",
        color="project",
        barmode="group"
    )
    
    fig8.update_layout(
        height=400,
        xaxis_title="Role",
        yaxis_title="Tasks Completed",
        showlegend=True
    )
    st.plotly_chart(fig8, use_container_width=True)

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
                               "tasks_completed", "quality_rating", "productivity_score", 
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
st.markdown("*Project Productivity & Quality Dashboard | Data powered by Supabase*")
