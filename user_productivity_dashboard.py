import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
import numpy as np

# =====================================================================
# PAGE CONFIG
# =====================================================================
st.set_page_config(page_title="User Productivity & Quality Dashboard", layout="wide")

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
# Then replace generate_mock_user_data() with:
# def fetch_user_data():
#     response = supabase.table("user_productivity").select("*").execute()
#     return pd.DataFrame(response.data)
# =====================================================================

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
    - quality_rating (TEXT): Quality rating (Good/Average/Bad)
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
                "quality_rating": np.random.choice(["Good", "Average", "Bad"], p=[0.5, 0.35, 0.15]),
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
# SESSION STATE INITIALIZATION
# =====================================================================
if "user_data" not in st.session_state:
    st.session_state.user_data = generate_mock_user_data()

# =====================================================================
# HEADER
# =====================================================================
st.title("👤 User Productivity & Quality Dashboard")
st.markdown("Comprehensive analytics for individual user performance tracking")
st.markdown("---")

# =====================================================================
# LOAD AND PREPARE DATA
# =====================================================================
# In production, replace this with: df = fetch_user_data()
df = st.session_state.user_data.copy()
df["date"] = pd.to_datetime(df["date"])

# =====================================================================
# VIEW MODE SELECTOR (All Users vs Specific User)
# =====================================================================
col1, col2 = st.columns([1, 3])
with col1:
    view_mode = st.selectbox("View Mode", ["All Users", "Specific User"])

with col2:
    if view_mode == "Specific User":
        selected_user = st.selectbox("Select User", sorted(df["user"].unique()))
        df_filtered = df[df["user"] == selected_user].copy()
    else:
        selected_user = None
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
        key="user_date_range"
    )

with filter_col2:
    if view_mode == "All Users":
        filter_roles = st.multiselect(
            "Filter by Role",
            options=sorted(df_filtered["role"].unique()),
            default=sorted(df_filtered["role"].unique())
        )
        df_filtered = df_filtered[df_filtered["role"].isin(filter_roles)]

with filter_col3:
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
    st.metric("Avg Productivity Score", f"{avg_productivity:.1f}%")

with kpi_col4:
    good_quality_pct = (df_filtered["quality_rating"] == "Good").sum() / len(df_filtered) * 100 if len(df_filtered) > 0 else 0
    st.metric("Good Quality %", f"{good_quality_pct:.1f}%")

with kpi_col5:
    if view_mode == "All Users":
        unique_users = df_filtered["user"].nunique()
        st.metric("Active Users", f"{unique_users}")
    else:
        avg_hours_per_day = df_filtered["hours_worked"].mean()
        st.metric("Avg Hours/Day", f"{avg_hours_per_day:.1f} hrs")

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
    
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=hours_by_date["date"],
        y=hours_by_date["hours_worked"],
        mode='lines',
        name='Hours Worked',
        fill='tozeroy',
        line=dict(color='#1f77b4', width=2)
    ))
    
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
    # Group by date and sum tasks
    tasks_by_date = df_filtered.groupby("date")["tasks_completed"].sum().reset_index()
    
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
        showlegend=False
    )
    st.plotly_chart(fig2, use_container_width=True)

# =====================================================================
# ROW 2: Productivity Score & Quality Distribution
# =====================================================================
chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    st.markdown("#### Average Productivity Score Over Time")
    # Group by date and calculate mean productivity
    productivity_by_date = df_filtered.groupby("date")["productivity_score"].mean().reset_index()
    productivity_by_date["moving_avg"] = calculate_moving_average(productivity_by_date, "productivity_score", window=7)
    
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=productivity_by_date["date"],
        y=productivity_by_date["productivity_score"],
        mode='lines',
        name='Daily Score',
        line=dict(color='lightblue', width=1),
        opacity=0.5
    ))
    fig3.add_trace(go.Scatter(
        x=productivity_by_date["date"],
        y=productivity_by_date["moving_avg"],
        mode='lines',
        name='7-Day Moving Avg',
        line=dict(color='#2ca02c', width=3)
    ))
    
    fig3.update_layout(
        height=400,
        hovermode='x unified',
        xaxis_title="Date",
        yaxis_title="Productivity Score",
        showlegend=True
    )
    st.plotly_chart(fig3, use_container_width=True)

with chart_col4:
    st.markdown("#### Quality Distribution (Good/Avg/Bad)")
    quality_counts = df_filtered["quality_rating"].value_counts().reset_index()
    quality_counts.columns = ["quality_rating", "count"]
    
    fig4 = go.Figure(data=[go.Pie(
        labels=quality_counts["quality_rating"],
        values=quality_counts["count"],
        hole=0.4,
        marker=dict(colors=['#2ca02c', '#ff7f0e', '#d62728'])
    )])
    
    fig4.update_layout(
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig4, use_container_width=True)

# =====================================================================
# ROW 3: Attendance Status & Productivity vs Quality
# =====================================================================
chart_col5, chart_col6 = st.columns(2)

with chart_col5:
    st.markdown("#### Attendance Status Over Time")
    # Group by date and attendance status
    attendance_by_date = df_filtered.groupby(["date", "attendance_status"]).size().reset_index(name="count")
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

with chart_col6:
    st.markdown("#### Productivity vs Quality")
    # Use daily aggregated data
    scatter_data = df_filtered.groupby(["user", "quality_rating", "role"]).agg({
        "productivity_score": "mean",
        "tasks_completed": "sum"
    }).reset_index()
    
    fig6 = px.scatter(
        scatter_data,
        x="quality_rating",
        y="productivity_score",
        size="tasks_completed",
        color="role" if view_mode == "All Users" else "user",
        hover_data=["user", "tasks_completed"],
        size_max=30
    )
    
    fig6.update_layout(
        height=400,
        xaxis_title="Quality Rating",
        yaxis_title="Avg Productivity Score"
    )
    st.plotly_chart(fig6, use_container_width=True)

# =====================================================================
# ROW 4: Cumulative Tasks vs Hours & Task Completion vs Quality
# =====================================================================
chart_col7, chart_col8 = st.columns(2)

with chart_col7:
    st.markdown("#### Cumulative Tasks vs Hours Worked")
    # Group by date and calculate cumulative sums
    daily_stats = df_filtered.groupby("date").agg({
        "tasks_completed": "sum",
        "hours_worked": "sum"
    }).reset_index()
    
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

with chart_col8:
    st.markdown("#### Task Completion vs Quality Rating")
    
    fig8 = px.box(
        df_filtered,
        x="quality_rating",
        y="tasks_completed",
        color="quality_rating",
        points="outliers",
        color_discrete_map={'Good': '#2ca02c', 'Average': '#ff7f0e', 'Bad': '#d62728'}
    )
    
    fig8.update_layout(
        height=400,
        xaxis_title="Quality Rating",
        yaxis_title="Tasks Completed",
        showlegend=False
    )
    st.plotly_chart(fig8, use_container_width=True)

# =====================================================================
# DATA TABLE VIEW
# =====================================================================
with st.expander("📋 View Raw Data Table"):
    st.markdown("### Raw Data")
    display_df = df_filtered[["date", "user", "project", "role", "hours_worked", 
                               "tasks_completed", "quality_rating", "productivity_score", 
                               "attendance_status"]].sort_values("date", ascending=False)
    
    st.dataframe(display_df, use_container_width=True, height=400)
    
    # Download button
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Data as CSV",
        data=csv,
        file_name="user_productivity_data.csv",
        mime="text/csv"
    )

# =====================================================================
# FOOTER
# =====================================================================
st.markdown("---")
st.markdown("*User Productivity & Quality Dashboard | Data powered by Supabase*")
