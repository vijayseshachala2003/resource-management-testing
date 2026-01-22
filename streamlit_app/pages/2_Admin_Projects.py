import streamlit as st
import requests
import pandas as pd
import time
from datetime import date, datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Admin | Project Manager", layout="wide")
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

def authenticated_request(method, endpoint, data=None, uploaded_file=None):
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
                response = requests.request(method, url, headers=headers, files=files)
        else:
            # for json payload
            response = requests.request(method, url, headers=headers, json=data)
        
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

tab1, tab2 = st.tabs(["📂 Manage Projects", "👥 Team Allocations"])

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
                            st.success(f"Inserted: {response["inserted"]}")
                            error = response["errors"]
                            error = "Error: None" if len(error) == 0 else "Errors: " + ','.join(error)
                            st.warning(error)
        else:
            st.warning("Select a file.")

    projects_data = authenticated_request("GET", "/admin/projects/")

    # KPI
    if projects_data:
        total_projects = len(projects_data)
        active_projects = len([p for p in projects_data if p["is_active"]])
        completed_projects = total_projects - active_projects

        k1, k2, k3 = st.columns(3)
        k1.metric("Total Projects", total_projects)
        k2.metric("Active Projects", active_projects)
        k3.metric("Completed Projects", completed_projects)

    st.markdown("---")

    c1, c2 = st.columns([2,1])
    with c1:
        search_text = st.text_input("Search by Code or Name")
    with c2:
        status_filter = st.selectbox("Status Filter", ["ALL","ACTIVE","COMPLETED"])

    filtered_projects = []
    for p in projects_data:
        if search_text and search_text.lower() not in p["name"].lower() and search_text.lower() not in p["code"].lower():
            continue
        if status_filter == "ACTIVE" and not p["is_active"]:
            continue
        if status_filter == "COMPLETED" and p["is_active"]:
            continue
        filtered_projects.append(p)

    if filtered_projects:

        df = pd.DataFrame(filtered_projects)
        df["status"] = df["is_active"].apply(lambda x: "ACTIVE" if x else "COMPLETED")

        members_count = {}
        pm_map = {}

        for p in projects_data:
            members = authenticated_request("GET", f"/admin/projects/{p['id']}/members") or []
            members_count[p["id"]] = len(members)
            pm_list = [m["name"] for m in members if m["work_role"] in ["PM","APM"]]
            pm_map[p["id"]] = ", ".join(pm_list)

        df["allocated_users"] = df["id"].map(members_count)
        df["pm_apm"] = df["id"].map(pm_map)

        edit_df = df[['code','name','status','allocated_users','pm_apm','is_active','start_date','end_date','id']].copy()
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
                "is_active": st.column_config.CheckboxColumn("Active?"),
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
                raw_active = updates.get("is_active", original_row["is_active"])

                # BUSINESS FIX
                if end_val:
                    safe_active = False
                else:
                    safe_active = bool(raw_active)

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
        members_data = authenticated_request("GET", f"/admin/projects/{selected_proj_id}/members")

        if members_data:
            for m in members_data:
                st.write(m["name"], "-", m["work_role"])