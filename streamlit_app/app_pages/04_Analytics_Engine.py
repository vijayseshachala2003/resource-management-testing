import streamlit as st
import requests
import pandas as pd
from datetime import date
from role_guard import get_user_role

# --- CONFIG ---
API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Analytics Engine", layout="wide")

# Basic role check
role = get_user_role()
if not role or role not in ["USER", "ADMIN", "MANAGER"]:
    st.error("Access denied. Please log in.")
    st.stop()
st.title("🧠 Analytics & Intelligence Engine")

# --- 1. AUTH CHECK ---
token = st.session_state.get("token")
if not token:
    st.warning("🔒 Please login first.")
    st.stop()

headers = {"Authorization": f"Bearer {token}"}

# --- 2. SELECT PROJECT ---
try:
    response = requests.get(f"{API_URL}/admin/projects/", headers=headers)
    if response.status_code == 200:
        projects = response.json()
        project_options = {p["name"]: p["id"] for p in projects}
        
        if not project_options:
            st.warning("No projects found.")
            st.stop()
    else:
        st.error("Failed to load projects.")
        st.stop()
except Exception as e:
    st.error(f"Connection Error: {e}")
    st.stop()

# Layout: Control Panel
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    selected_project_name = st.selectbox("Select Project", list(project_options.keys()))
    project_id = project_options[selected_project_name]

with col2:
    selected_date = st.date_input("Analysis Date", date.today())

with col3:
    st.write("##") # Spacer
    run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

st.divider()

# --- 3. RUN CALCULATION ---
if run_btn:
    with st.spinner("Crunching numbers... calculating averages... grading users..."):
        try:
            # Call the Analytics API
            calc_url = f"{API_URL}/analytics/calculate-daily"
            params = {
                "project_id": project_id,
                "calculation_date": str(selected_date)
            }
            
            res = requests.post(calc_url, params=params, headers=headers)
            
            if res.status_code == 200:
                data = res.json()
                
                # A. Show Summary Metrics
                st.success("Analysis Complete!")
                m1, m2, m3 = st.columns(3)
                m1.metric("Project Average (Tasks)", data.get("project_avg_tasks", 0))
                m2.metric("Processed Users", data.get("processed_users", 0))
                m3.metric("Bad Threshold (<70%)", data.get("bad_threshold", 0))
                
                # B. Show Detailed Table
                if "details" in data and data["details"]:
                    st.subheader("📋 Daily Scorecard")
                    df = pd.DataFrame(data["details"])
                    
                    # --- COLUMN REORDERING & FORMATTING ---
                    # We want: [Index] | User Name | Rating | Score | Tasks
                    
                    target_cols = []
                    rating_col_name = "rating" # Default if renaming fails
                    
                    if "user_name" in df.columns:
                        # Select only the columns we want in the specific order
                        df = df[["user_name", "rating", "score", "tasks"]]
                        
                        # Rename for cleaner display
                        df = df.rename(columns={
                            "user_name": "User Name",
                            "rating": "Rating",
                            "score": "Score",
                            "tasks": "Tasks Completed"
                        })
                        rating_col_name = "Rating"
                    else:
                        # Fallback if backend doesn't send name yet
                        st.warning("Backend not returning names. Showing IDs instead.")
                        df = df[["user_id", "rating", "score", "tasks"]]

                    # Highlight 'BAD' rows
                    def highlight_bad(val):
                        # Use specific colors requested
                        color = "#ef3434" if val == 'BAD' else "#55ce55" if val == 'GOOD' else ''
                        return f'background-color: {color}'
                    
                    st.dataframe(
                        df.style.map(highlight_bad, subset=[rating_col_name]), 
                        use_container_width=True
                    )
                else:
                    st.warning("Calculation finished, but no user details were returned.")
                
                # --- 4. PREPARE DOWNLOAD BUTTON ---
                # We fetch this immediately so the button is ready to click
                csv_url = f"{API_URL}/reports/project-daily-csv/{project_id}/{selected_date}"
                file_res = requests.get(csv_url, headers=headers)
                
                if file_res.status_code == 200:
                    st.write("##") # Spacer
                    st.download_button(
                        label="📥 Download Official CSV Report",
                        data=file_res.content,
                        file_name=f"Daily_Report_{selected_project_name}_{selected_date}.csv",
                        mime="text/csv",
                        type="primary"
                    )
                else:
                    st.error("Report generated, but CSV download failed.")
                    
            elif res.status_code == 404:
                st.error("No APPROVED work logs found for this date. Go to 'Approvals' page first!")
            else:
                st.error(f"Error {res.status_code}: {res.text}")
                
        except Exception as e:
            st.error(f"System Error: {e}")