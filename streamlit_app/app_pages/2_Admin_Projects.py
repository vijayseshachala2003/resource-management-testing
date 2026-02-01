import streamlit as st
import requests
import pandas as pd
import time
from datetime import date, datetime, timedelta
from role_guard import get_user_role

# --- CONFIGURATION ---
st.set_page_config(page_title="Admin | Project Manager", layout="wide")

# Basic role check
role = get_user_role()
if not role or role not in ["ADMIN", "MANAGER"]:
    st.error("Access denied. Admin or Manager role required.")
    st.stop()
API_BASE_URL = "http://127.0.0.1:8000"

ROLE_OPTIONS = ["ANNOTATION", "QC", "LIVE_QC", "RETRO_QC", "PM", "APM", "RPM"]

# --- HELPER FUNCTIONS ---
# def authenticated_request(method, endpoint, data=None):
#     token = st.session_state.get("token")
#     if not token:
#         st.warning("🔒 Please login first.")
#         st.stop()
#
#     headers = {"Authorization": f"Bearer {token}"}
#     try:
#         response = requests.request(method, f"{API_BASE_URL}{endpoint}", headers=headers, json=data)
#         if response.status_code >= 400:
#             st.error(f"❌ Error {response.status_code}: {response.text}")
#             return None
#         return response.json()
#     except Exception as e:
#         st.error(f"❌ Connection Error: {e}")
#         return None

def authenticated_request(method, endpoint, data=None, uploaded_file=None, params=None):
    token = st.session_state.get("token")
    
    if not token:
        st.warning("🔒 Please login first.")
        st.stop()

    headers = {"Authorization": f"Bearer {token}"}
    
    # enforce ONE payload type
    if data is not None and uploaded_file is not None:
        st.error("❌ Cannot send JSON and file in the same request.")
        return None
     
    url = f"{API_BASE_URL}{endpoint}"

    try:
        response = None
        # for file upload
        if uploaded_file is not None:
            files = {
                "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
            }
            with st.spinner("Uploading file..."):
                response = requests.request(method, url, headers=headers, files=files, params=params)
        else:
            # for json payload (POST/PUT) or params (GET)
            if method.upper() == "GET" and params:
                response = requests.request(method, url, headers=headers, params=params)
            else:
                response = requests.request(method, url, headers=headers, json=data, params=params)
        
        if response.status_code >= 400:
            st.error(f"❌ Error {response.status_code}: {response.text}")
            return None
        return response.json()

    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None
    

# --- TITLE ---
st.title("🛠️ Project Management Center")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📂 Manage Projects", "👥 Team Allocations", "⭐ Quality Assessment"])

# ==========================================
# TAB 1
# ==========================================
with tab1:

    with st.expander("➕ Create New Project", expanded=False):
        with st.form("create_project_form"):
            c1, c2 = st.columns(2)
            new_name = c1.text_input("Project Name")
            new_code = c2.text_input("Project Code")

            c3, c4, c5 = st.columns(3)
            new_start = c3.date_input("Start Date", value=date.today())
            new_end = c4.date_input("End Date (Optional)", value=None)
            is_active = c5.checkbox("Is Active?", value=True)
            
            if st.form_submit_button("Create Project", type="primary"):
                payload = {
                    "name": new_name.strip(),
                    "code": new_code.strip(),
                    "start_date": str(new_start),
                    "end_date": str(new_end) if new_end else None,
                    "is_active": is_active
                }
                authenticated_request("POST", "/admin/projects/", data=payload)
                st.toast("Project created")
                st.rerun()
    
    # --- BOTTOM: UPLOAD BULK PROJECTS
    with st.expander("Upload Bulk Project (in .csv)", expanded=False):
        uploaded_file = st.file_uploader(
            "Upload a CSV file",
            type=["csv"],
            accept_multiple_files=False
        )

        if uploaded_file:
            if uploaded_file.type != "text/csv" and uploaded_file.type != "application/vnd.ms-excel":
                st.error("Invalid file type. Please upload a .csv file")
            else:
                if uploaded_file.size == 0:
                    st.error("Empty file.")
                else:
                    st.success("File attached.")
                    if st.button("Upload"):
                        response = authenticated_request("POST", "/admin/bulk_uploads/projects", uploaded_file=uploaded_file)
                        
                        if not response:
                            st.error("Error uploading file")
                        else:
                            st.success(f"Inserted: {response['inserted']}")
                            error = response["errors"]
                            error = "Error: None" if len(error) == 0 else "Errors: " + ','.join(error)
                            st.warning(error)
        else:
            st.warning("Select a file.")

    projects_data = authenticated_request("GET", "/admin/projects/")

    # KPI
    if projects_data:
        total_projects = len(projects_data)
        # Active: is_active=True AND no end_date
        active_projects = len([p for p in projects_data if p["is_active"] and not p.get("end_date")])
        # Paused: is_active=False AND no end_date
        paused_projects = len([p for p in projects_data if not p["is_active"] and not p.get("end_date")])
        # Completed: has end_date (regardless of is_active)
        completed_projects = len([p for p in projects_data if p.get("end_date")])

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Projects", total_projects)
        k2.metric("Active Projects", active_projects)
        k3.metric("Paused Projects", paused_projects)
        k4.metric("Completed Projects", completed_projects)

    st.markdown("---")

    c1, c2 = st.columns([2,1])
    with c1:
        search_text = st.text_input("Search by Code or Name")
    with c2:
        status_filter = st.selectbox("Status Filter", ["ALL", "ACTIVE", "PAUSED", "COMPLETED"])

    filtered_projects = []
    for p in projects_data:
        if search_text and search_text.lower() not in p["name"].lower() and search_text.lower() not in p["code"].lower():
            continue
        # Active: is_active=True AND no end_date
        if status_filter == "ACTIVE" and (not p["is_active"] or p.get("end_date")):
            continue
        # Paused: is_active=False AND no end_date
        if status_filter == "PAUSED" and (p["is_active"] or p.get("end_date")):
            continue
        # Completed: has end_date (regardless of is_active)
        if status_filter == "COMPLETED" and not p.get("end_date"):
            continue
        filtered_projects.append(p)

    if filtered_projects:

        df = pd.DataFrame(filtered_projects)
        df["status"] = df.apply(
            lambda row: "COMPLETED"
            if row.get("end_date")
            else ("ACTIVE" if row.get("is_active") else "PAUSED"),
            axis=1,
        )

        members_count = {}
        pm_map = {}

        for p in projects_data:
            members = authenticated_request("GET", f"/admin/projects/{p['id']}/members") or []
            members_count[p["id"]] = len(members)
            pm_list = [m["name"] for m in members if m["work_role"] in ["PM","APM"]]
            pm_map[p["id"]] = ", ".join(pm_list)

        df["allocated_users"] = df["id"].map(members_count)
        df["pm_apm"] = df["id"].map(pm_map)

        edit_df = df[['code','name','status','allocated_users','pm_apm','start_date','end_date','id']].copy()
        edit_df['start_date'] = pd.to_datetime(edit_df['start_date']).dt.date
        edit_df['end_date'] = pd.to_datetime(edit_df['end_date']).dt.date

        edited_df = st.data_editor(
            edit_df,
            column_config={
                "id": None,
                "code": st.column_config.TextColumn("Code"),
                "name": st.column_config.TextColumn("Name"),
                "status": st.column_config.TextColumn("Status"),
                "allocated_users": st.column_config.NumberColumn("Allocated Users"),
                "pm_apm": st.column_config.TextColumn("PM / APM"),
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["ACTIVE", "PAUSED", "COMPLETED"],
                ),
                "start_date": st.column_config.DateColumn("Start Date"),
                "end_date": st.column_config.DateColumn("End Date")
            },
            use_container_width=True,
            key="project_editor"
        )


        if st.button("💾 Save Changes", type="primary"):
            changes = st.session_state["project_editor"].get("edited_rows", {})

            for row_idx, updates in changes.items():
                original_row = edit_df.iloc[row_idx]
                proj_id = original_row["id"]

                end_val = updates.get("end_date", original_row["end_date"])
                status_val = updates.get("status", original_row["status"])

                if status_val == "COMPLETED" and not end_val:
                    end_val = date.today()
                if status_val in ["ACTIVE", "PAUSED"]:
                    end_val = None

                safe_active = status_val == "ACTIVE"

                payload = {
                    "name": updates.get("name", original_row["name"]).strip(),
                    "code": updates.get("code", original_row["code"]).strip(),
                    "is_active": safe_active,
                    "start_date": str(updates.get("start_date", original_row["start_date"])),
                    "end_date": str(end_val) if end_val else None
                }

                authenticated_request("PUT", f"/admin/projects/{proj_id}", data=payload)

            st.toast("Projects updated")
            time.sleep(1)
            st.rerun()

    else:
        st.info("No projects found.")

# ==========================================
# TAB 2
# ==========================================
with tab2:
    projects_list = authenticated_request("GET", "/admin/projects/") or []
    proj_map_simple = {p['name']: p['id'] for p in projects_list}

    selected_proj_name = st.selectbox("Select Project", options=list(proj_map_simple.keys()))

    if selected_proj_name:
        selected_proj_id = proj_map_simple[selected_proj_name]
        
        # Add Member Section
        with st.expander("➕ Add Member to Project", expanded=False):
            with st.form("add_member_form"):
                # Get all users with limit parameter
                all_users = authenticated_request("GET", "/admin/users/", params={"limit": 1000}) or []
                # Filter active users only
                active_users = [u for u in all_users if u.get("is_active", True)]
                
                if not active_users:
                    st.warning("No active users found. Please create users first.")
                else:
                    # Get existing member IDs to exclude them from selection
                    existing_members = authenticated_request("GET", f"/admin/projects/{selected_proj_id}/members") or []
                    existing_user_ids = {str(m.get("user_id")) for m in existing_members if m.get("is_active", True)}
                    
                    # Filter out already assigned active users
                    available_users = [u for u in active_users if str(u.get("id")) not in existing_user_ids]
                    
                    if not available_users:
                        st.info("All active users are already assigned to this project.")
                    else:
                        # Create user selection options (name - email format)
                        user_options = {f"{u['name']} ({u['email']})": u['id'] for u in available_users}
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            selected_user_display = st.selectbox(
                                "Select User",
                                options=list(user_options.keys()),
                                key="add_member_user"
                            )
                            selected_user_id = user_options[selected_user_display]
                        
                        with col2:
                            selected_work_role = st.selectbox(
                                "Work Role",
                                options=ROLE_OPTIONS,
                                key="add_member_role"
                            )
                        
                        col3, col4 = st.columns(2)
                        with col3:
                            assigned_from = st.date_input(
                                "Assigned From",
                                value=date.today(),
                                key="add_member_from"
                            )
                        with col4:
                            assigned_to = st.date_input(
                                "Assigned To (Optional)",
                                value=None,
                                key="add_member_to"
                            )
                        
                        if st.form_submit_button("➕ Add Member", type="primary"):
                            payload = {
                                "user_id": str(selected_user_id),
                                "work_role": selected_work_role,
                                "assigned_from": str(assigned_from),
                                "assigned_to": str(assigned_to) if assigned_to else None
                            }
                            
                            response = authenticated_request("POST", f"/admin/projects/{selected_proj_id}/members", data=payload)
                            
                            if response:
                                st.success(f"✅ Member added successfully!")
                                st.toast("Member added")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ Failed to add member. Check if user is already assigned to this project.")
        
        st.markdown("---")
        
        # Display existing members
        st.subheader("👥 Current Team Members")
        members_data = authenticated_request("GET", f"/admin/projects/{selected_proj_id}/members") or []

        if members_data:
            # Create a dataframe for better display
            members_df_data = []
            for m in members_data:
                members_df_data.append({
                    "Name": m.get("name", "-"),
                    "Email": m.get("email", "-"),
                    "Work Role": m.get("work_role", "-"),
                    "Assigned From": m.get("assigned_from", "-"),
                    "Assigned To": m.get("assigned_to", "-") if m.get("assigned_to") else "Ongoing",
                    "Status": "Active" if m.get("is_active", True) else "Inactive",
                    "User ID": m.get("user_id")
                })
            
            df_members = pd.DataFrame(members_df_data)
            
            # Display as dataframe with remove buttons
            st.markdown("### 📋 Members Table")
            display_df = df_members[["Name", "Email", "Work Role", "Assigned From", "Assigned To", "Status"]].copy()
            st.dataframe(display_df, use_container_width=True)
            
            # Edit member role section
            st.markdown("### ✏️ Edit Member Role")
            edit_col1, edit_col2, edit_col3 = st.columns([2, 2, 1])
            with edit_col1:
                edit_user_display = st.selectbox(
                    "Select member to edit",
                    options=[f"{row['Name']} ({row['Email']})" for _, row in df_members.iterrows()],
                    key="edit_member_select"
                )
            with edit_col2:
                # Get current role for selected member
                selected_edit_name = edit_user_display.split(" (")[0] if edit_user_display else None
                current_role = None
                if selected_edit_name:
                    selected_edit_row = df_members[df_members["Name"] == selected_edit_name]
                    if not selected_edit_row.empty:
                        current_role = selected_edit_row.iloc[0]["Work Role"]
                
                # Set default index for selectbox
                default_index = 0
                if current_role and current_role in ROLE_OPTIONS:
                    default_index = ROLE_OPTIONS.index(current_role)
                
                new_role = st.selectbox(
                    "New Work Role",
                    options=ROLE_OPTIONS,
                    index=default_index,
                    key="edit_member_role"
                )
            with edit_col3:
                st.write("")  # Spacing
                st.write("")  # Spacing
                if st.button("💾 Update Role", type="primary", key="edit_member_btn", use_container_width=True):
                    if selected_edit_name:
                        try:
                            selected_edit_row = df_members[df_members["Name"] == selected_edit_name].iloc[0]
                            user_id_to_edit = selected_edit_row["User ID"]
                            
                            # Check if role actually changed
                            if current_role == new_role:
                                st.info(f"ℹ️ {selected_edit_row['Name']} already has role '{new_role}'. No changes made.")
                            else:
                                payload = {
                                    "work_role": new_role
                                }
                                
                                response = authenticated_request("PUT", f"/admin/projects/{selected_proj_id}/members/{user_id_to_edit}", data=payload)
                                if response is not None:
                                    st.success(f"✅ {selected_edit_row['Name']}'s role updated from '{current_role}' to '{new_role}'")
                                    st.toast("Role updated")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to update role. Please try again.")
                        except Exception as e:
                            st.error(f"❌ Error updating role: {str(e)}")
            
            # Remove member section
            st.markdown("### 🗑️ Remove Member")
            remove_col1, remove_col2 = st.columns([3, 1])
            with remove_col1:
                remove_user_display = st.selectbox(
                    "Select member to remove",
                    options=[f"{row['Name']} ({row['Email']})" for _, row in df_members.iterrows()],
                    key="remove_member_select"
                )
            with remove_col2:
                st.write("")  # Spacing
                st.write("")  # Spacing
                if st.button("🗑️ Remove", type="primary", key="remove_member_btn"):
                    # Find the selected user ID
                    selected_name = remove_user_display.split(" (")[0]
                    selected_row = df_members[df_members["Name"] == selected_name].iloc[0]
                    user_id_to_remove = selected_row["User ID"]
                    
                    response = authenticated_request("DELETE", f"/admin/projects/{selected_proj_id}/members/{user_id_to_remove}")
                    if response is not None:
                        st.success(f"✅ {selected_row['Name']} removed from project")
                        st.toast("Member removed")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Failed to remove member")
            
        else:
            st.info("No members assigned to this project yet. Use the 'Add Member' form above to assign team members.")

# ==========================================
# TAB 3: QUALITY ASSESSMENT
# ==========================================
with tab3:
    # Helper functions for quality assessment
    @st.cache_data(ttl=300)
    def get_user_name_mapping_qa() -> dict:
        """Fetch all users and create UUID -> name mapping"""
        users = authenticated_request("GET", "/admin/users/", params={"limit": 1000}) or []
        if not users:
            return {}
        return {str(user["id"]): user["name"] for user in users}
    
    @st.cache_data(ttl=300)
    def get_user_email_mapping_qa() -> dict:
        """Fetch all users and create UUID -> email mapping"""
        users = authenticated_request("GET", "/admin/users/", params={"limit": 1000}) or []
        if not users:
            return {}
        return {str(user["id"]): user.get("email", "") for user in users}
    
    @st.cache_data(ttl=300)
    def get_project_name_mapping_qa() -> dict:
        """Fetch all projects and create UUID -> name mapping"""
        projects = authenticated_request("GET", "/admin/projects/") or []
        if not projects:
            return {}
        return {str(project["id"]): project["name"] for project in projects}
    
    st.markdown("### ⭐ Quality Assessment")
    st.markdown("Manually assess quality ratings for users on specific dates")
    st.markdown("---")
    
    # Mode selector
    mode = st.radio(
        "Assessment Mode",
        ["Individual Assessment", "Bulk Upload"],
        horizontal=True,
        key="quality_mode_pmc"
    )
    
    st.markdown("---")
    
    if mode == "Individual Assessment":
        st.markdown("#### 📝 Individual Quality Assessment")
        
        # Get mappings
        user_map = get_user_name_mapping_qa()
        user_email_map = get_user_email_mapping_qa()
        project_map = get_project_name_mapping_qa()
        
        if not user_map or not project_map:
            st.error("⚠️ Unable to load users or projects. Please check your connection.")
        else:
            # Create user options with email display: "Name (email)"
            user_options_display = {}
            for user_id, user_name in user_map.items():
                email = user_email_map.get(user_id, "")
                if email:
                    display_name = f"{user_name} ({email})"
                else:
                    display_name = user_name
                user_options_display[display_name] = user_id
            
            # Create reverse mapping for project
            project_id_to_name = {v: k for k, v in project_map.items()}
            
            # Form fields
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # User selection with email
                user_display_list = sorted(user_options_display.keys())
                selected_user_display = st.selectbox("Select User", user_display_list, key="qa_user_pmc")
                selected_user_id = user_options_display.get(selected_user_display)
            
            with col2:
                # Project selection
                project_options = sorted(project_map.values())
                selected_project_name = st.selectbox("Select Project", project_options, key="qa_project_pmc")
                selected_project_id = project_id_to_name.get(selected_project_name)
            
            with col3:
                # Date selection
                selected_date = st.date_input("Assessment Date", value=date.today(), key="qa_date_pmc")
            
            # Quality rating
            col4, col5 = st.columns(2)
            
            with col4:
                rating = st.selectbox(
                    "Quality Rating",
                    ["GOOD", "AVERAGE", "BAD"],
                    help="GOOD: High quality work\nAVERAGE: Acceptable quality\nBAD: Poor quality requiring improvement",
                    key="qa_rating_pmc"
                )
            
            with col5:
                quality_score = st.number_input(
                    "Quality Score (0-10)",
                    min_value=0.0,
                    max_value=10.0,
                    value=7.0,
                    step=0.1,
                    help="Numeric score from 0 (poor) to 10 (excellent). Optional but recommended.",
                    key="qa_score_pmc"
                )
            
            # Accuracy and Critical Rate
            col6, col7 = st.columns(2)
            
            with col6:
                accuracy = st.number_input(
                    "Accuracy (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=None,
                    step=0.1,
                    help="Percentage of work completed correctly (0-100%). Optional.",
                    key="qa_accuracy_pmc"
                )
            
            with col7:
                critical_rate = st.number_input(
                    "Critical Rate (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=None,
                    step=0.1,
                    help="Percentage of critical tasks handled successfully (0-100%). Optional.",
                    key="qa_critical_rate_pmc"
                )
            
            # Notes
            notes = st.text_area(
                "Assessment Notes (Optional)",
                placeholder="Add any additional comments about the quality assessment...",
                height=100,
                key="qa_notes_pmc"
            )
            
            # Submit button
            if st.button("💾 Save Quality Assessment", type="primary", use_container_width=True, key="qa_save_pmc"):
                if not selected_user_id or not selected_project_id:
                    st.error("Please select both user and project.")
                else:
                    with st.spinner("Submitting quality assessment..."):
                        payload = {
                            "user_id": selected_user_id,
                            "project_id": selected_project_id,
                            "metric_date": str(selected_date),
                            "rating": rating,
                            "quality_score": float(quality_score) if quality_score else None,
                            "accuracy": float(accuracy) if accuracy is not None else None,
                            "critical_rate": float(critical_rate) if critical_rate is not None else None,
                            "notes": notes if notes.strip() else None
                        }
                        
                        result = authenticated_request("POST", "/admin/metrics/user_daily/quality", data=payload)
                        
                        if result:
                            st.success(f"✅ Quality assessment saved successfully!")
                            st.balloons()
                            # Clear cache to refresh data
                            get_user_name_mapping_qa.clear()
                            get_user_email_mapping_qa.clear()
                            get_project_name_mapping_qa.clear()
                            # Force rerun to refresh the table
                            time.sleep(0.5)
                            st.rerun()
            
            # Existing assessments view
            st.markdown("---")
            st.markdown("#### 📋 Recent Quality Assessments")
            
            # Fetch existing assessments
            if selected_user_id and selected_project_id:
                params = {
                    "user_id": selected_user_id,
                    "project_id": selected_project_id,
                    "start_date": str(selected_date - timedelta(days=30)),
                    "end_date": str(selected_date + timedelta(days=1))
                }
                
                quality_data = authenticated_request("GET", "/admin/metrics/user_daily/quality-ratings", params=params) or []
                
                if quality_data:
                    df_quality = pd.DataFrame(quality_data)
                    df_quality["metric_date"] = pd.to_datetime(df_quality["metric_date"]).dt.date
                    
                    # Format for display
                    df_quality["quality_rating"] = df_quality["quality_rating"].apply(
                        lambda x: {"GOOD": "✅ Good", "AVERAGE": "⚠️ Average", "BAD": "❌ Bad"}.get(x, x) if x else "Not Assessed"
                    )
                    
                    if "quality_score" in df_quality.columns:
                        df_quality["quality_score"] = df_quality["quality_score"].apply(
                            lambda x: f"{x:.1f}" if x is not None else "N/A"
                        )
                    
                    if "accuracy" in df_quality.columns:
                        df_quality["accuracy"] = df_quality["accuracy"].apply(
                            lambda x: f"{x:.1f}%" if x is not None else "N/A"
                        )
                    
                    if "critical_rate" in df_quality.columns:
                        df_quality["critical_rate"] = df_quality["critical_rate"].apply(
                            lambda x: f"{x:.1f}%" if x is not None else "N/A"
                        )
                    
                    display_cols = ["metric_date", "quality_rating", "quality_score", "accuracy", "critical_rate", "source", "notes"]
                    display_cols = [col for col in display_cols if col in df_quality.columns]
                    
                    st.dataframe(
                        df_quality[display_cols].sort_values("metric_date", ascending=False),
                        use_container_width=True,
                        height=300
                    )
                else:
                    st.info("No quality assessments found for this user/project combination in the last 30 days.")
    
    else:
        # Bulk Upload
        st.markdown("#### 📤 Bulk Quality Assessment Upload")
        
        st.markdown("""
        **CSV Format Required:**
        - `user_email`: User's email address
        - `project_code`: Project code
        - `metric_date`: Date in YYYY-MM-DD format
        - `rating`: Quality rating (GOOD, AVERAGE, or BAD)
        - `quality_score` (optional): Numeric score 0-10
        - `accuracy` (optional): Accuracy percentage 0-100
        - `critical_rate` (optional): Critical rate percentage 0-100
        - `work_role` (optional): Work role (will be fetched from project_members if not provided)
        - `notes` (optional): Assessment notes
        
        **Example CSV:**
        ```csv
        user_email,project_code,metric_date,rating,quality_score,accuracy,critical_rate,notes
        user@example.com,PROJ001,2024-01-15,GOOD,8.5,95.0,88.5,Excellent work quality
        user2@example.com,PROJ002,2024-01-15,AVERAGE,6.0,75.0,70.0,Acceptable quality
        ```
        """)
        
        uploaded_file = st.file_uploader(
            "Upload CSV File",
            type=["csv"],
            help="Upload a CSV file with quality assessments",
            key="qa_upload_pmc"
        )
        
        if uploaded_file:
            # Preview CSV
            try:
                df_preview = pd.read_csv(uploaded_file)
                st.markdown("##### 📄 CSV Preview")
                st.dataframe(df_preview.head(10), use_container_width=True)
                
                if st.button("📤 Upload Quality Assessments", type="primary", use_container_width=True, key="qa_upload_btn_pmc"):
                    # Reset file pointer
                    uploaded_file.seek(0)
                    
                    with st.spinner("Uploading quality assessments..."):
                        response = authenticated_request("POST", "/admin/bulk_uploads/quality", uploaded_file=uploaded_file)
                        
                        if response:
                            st.success(f"✅ Successfully uploaded {response.get('inserted', 0)} quality assessments!")
                            
                            if response.get("errors"):
                                st.warning(f"⚠️ {len(response['errors'])} errors encountered:")
                                with st.expander("View Errors"):
                                    for error in response["errors"]:
                                        st.text(error)
                            
                            st.balloons()
                            get_user_name_mapping_qa.clear()
                            get_user_email_mapping_qa.clear()
                            get_project_name_mapping_qa.clear()
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("❌ Upload failed. Please check the file format and try again.")
            
            except Exception as e:
                st.error(f"❌ Error reading CSV file: {str(e)}")
        
        # Download template
        st.markdown("---")
        st.markdown("#### 📥 Download CSV Template")
        
        template_data = {
            "user_email": ["user@example.com"],
            "project_code": ["PROJ001"],
            "metric_date": ["2024-01-15"],
            "rating": ["GOOD"],
            "quality_score": [8.5],
            "accuracy": [95.0],
            "critical_rate": [88.5],
            "work_role": [""],
            "notes": ["Example quality assessment"]
        }
        template_df = pd.DataFrame(template_data)
        csv_template = template_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Download CSV Template",
            data=csv_template,
            file_name="quality_assessment_template.csv",
            mime="text/csv",
            key="qa_template_pmc"
        )