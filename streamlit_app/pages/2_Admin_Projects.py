import streamlit as st
import requests
import pandas as pd
import time
from datetime import date, datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Admin | Project Manager", layout="wide")
API_BASE_URL = "http://127.0.0.1:8000"

# Specific Roles
ROLE_OPTIONS = ["ANNOTATION", "QC", "LIVE_QC", "RETRO_QC", "PM", "APM", "RPM"]

# --- HELPER FUNCTIONS ---
def authenticated_request(method, endpoint, data=None):
    token = st.session_state.get("token")
    if not token:
        st.warning("🔒 Please login first.")
        st.stop()
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.request(method, f"{API_BASE_URL}{endpoint}", headers=headers, json=data)
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
# TAB 1: CREATE & EDIT PROJECTS (TABLE MODE)
# ==========================================
with tab1:
    # --- TOP: CREATE NEW PROJECT ---
    with st.expander("➕ Create New Project", expanded=False):
        with st.form("create_project_form"):
            c1, c2 = st.columns(2)
            new_name = c1.text_input("Project Name")
            new_code = c2.text_input("Project Code", placeholder="e.g. PRJ-001")
            
            c3, c4, c5 = st.columns(3)
            new_start = c3.date_input("Start Date", value=date.today())
            new_end = c4.date_input("End Date (Optional)", value=None)
            is_active = c5.checkbox("Is Active?", value=True)
            
            if st.form_submit_button("Create Project", type="primary"):
                if new_name and new_code:
                    payload = {
                        "name": new_name, "code": new_code, 
                        "start_date": str(new_start), 
                        "end_date": str(new_end) if new_end else None, 
                        "is_active": is_active
                    }
                    if authenticated_request("POST", "/admin/projects/", data=payload):
                        st.toast(f"✅ Project '{new_name}' created successfully!", icon="🎉")
                        time.sleep(1.5)
                        st.rerun()
                else:
                    st.warning("⚠️ Name and Code are required.")

    # --- MAIN: EDITABLE PROJECT TABLE ---
    st.subheader("📋 All Projects (Edit in Table)")
    st.info("💡 Double-click any cell to edit. Press 'Save Changes' at the bottom when done.")

    projects_data = authenticated_request("GET", "/admin/projects/")
    
    if projects_data:
        df = pd.DataFrame(projects_data)
        
        # Prepare Data for Editor
        edit_df = df[['name', 'code', 'is_active', 'start_date', 'end_date', 'id']].copy()
        edit_df['start_date'] = pd.to_datetime(edit_df['start_date']).dt.date
        edit_df['end_date'] = pd.to_datetime(edit_df['end_date']).dt.date

        # Render Editor
        edited_df = st.data_editor(
            edit_df,
            column_config={
                "id": None, 
                "name": st.column_config.TextColumn("Project Name", required=True),
                "code": st.column_config.TextColumn("Code", required=True),
                "is_active": st.column_config.CheckboxColumn("Active?", default=True),
                "start_date": st.column_config.DateColumn("Start Date", format="YYYY-MM-DD", required=True),
                "end_date": st.column_config.DateColumn("End Date", format="YYYY-MM-DD"),
            },
            use_container_width=True,
            num_rows="fixed",
            key="project_editor"
        )

        # SAVE CHANGES LOGIC
        if st.button("💾 Save Changes", type="primary"):
            changes = st.session_state["project_editor"].get("edited_rows", {})
            
            if not changes:
                st.toast("ℹ️ No changes detected.", icon="🤔")
            else:
                progress_bar = st.progress(0)
                total = len(changes)
                updated_count = 0
                error_count = 0
                
                for i, (row_idx, updates) in enumerate(changes.items()):
                    # Get original ID and Data
                    original_row = edit_df.iloc[row_idx]
                    proj_id = original_row['id']
                    
                    # --- FIX START: Force boolean conversion ---
                    raw_active = updates.get("is_active", original_row['is_active'])
                    safe_active = bool(raw_active) 
                    # --- FIX END ---

                    # Merge Updates
                    payload = {
                        "name": updates.get("name", original_row['name']),
                        "code": updates.get("code", original_row['code']),
                        "is_active": safe_active,  # Use the safe boolean
                        "start_date": str(updates.get("start_date", original_row['start_date'])),
                        "end_date": str(updates.get("end_date", original_row['end_date'])) if (updates.get("end_date") or original_row['end_date']) else None
                    }
                    
                    # Call API
                    if authenticated_request("PUT", f"/admin/projects/{proj_id}", data=payload):
                        updated_count += 1
                    else:
                        error_count += 1
                    
                    progress_bar.progress((i + 1) / total)

                # Show Results
                if error_count > 0:
                    st.error(f"❌ Failed to update {error_count} project(s). Check the errors above.")
                elif updated_count > 0:
                    st.toast(f"✅ Successfully updated {updated_count} project(s)!", icon="🎉")
                    time.sleep(1.5)
                    st.rerun()

    else:
        st.info("No projects found.")


# ==========================================
# TAB 2: MANAGE TEAM MEMBERS
# ==========================================
with tab2:
    # 1. Select Project
    projects_list = authenticated_request("GET", "/admin/projects/") or []
    proj_map_simple = {p['name']: p['id'] for p in projects_list}
    
    col_sel, _ = st.columns([1, 2])
    with col_sel:
        selected_proj_name = st.selectbox("Select Project to Manage", options=list(proj_map_simple.keys()))
    
    if selected_proj_name:
        selected_proj_id = proj_map_simple[selected_proj_name]
        
        col_list, col_add = st.columns([2, 1], gap="large")
        
        # --- LEFT: MEMBER LIST ---
        with col_list:
            st.subheader(f"Team: {selected_proj_name}")
            members_data = authenticated_request("GET", f"/admin/projects/{selected_proj_id}/members")
            
            if members_data:
                for m in members_data:
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                        
                        c1.write(f"**{m['name']}**")
                        c1.caption(m['email'])
                        c2.info(m['work_role'])
                        
                        # EDIT ROLE
                        with c3:
                            with st.popover("✏️"):
                                st.write(f"Edit Role: **{m['name']}**")
                                try:
                                    curr_index = ROLE_OPTIONS.index(m['work_role'])
                                except:
                                    curr_index = 0
                                    
                                new_role = st.selectbox("New Role", ROLE_OPTIONS, index=curr_index, key=f"sel_{m['user_id']}")
                                
                                if st.button("Save", key=f"save_{m['user_id']}"):
                                    if authenticated_request("PUT", f"/admin/projects/{selected_proj_id}/members/{m['user_id']}", data={"work_role": new_role}):
                                        st.toast("✅ Role updated successfully!", icon="✨")
                                        time.sleep(1)
                                        st.rerun()

                        # DELETE MEMBER
                        with c4:
                            if st.button("🗑️", key=f"del_{m['user_id']}"):
                                if authenticated_request("DELETE", f"/admin/projects/{selected_proj_id}/members/{m['user_id']}"):
                                    st.toast("✅ Member removed successfully!", icon="🗑️")
                                    time.sleep(1)
                                    st.rerun()
            else:
                st.info("No members assigned yet.")

        # --- RIGHT: ADD NEW MEMBER ---
        with col_add:
            st.subheader("Add New Member")
            with st.container(border=True):
                all_users = authenticated_request("GET", "/admin/users/?limit=200") or []
                user_map = {u['email']: u['id'] for u in all_users}
                
                sel_user_email = st.selectbox("Select User", options=list(user_map.keys()))
                sel_role = st.selectbox("Assign Role", ROLE_OPTIONS)
                
                if st.button("Assign User", type="primary", use_container_width=True):
                    if sel_user_email:
                        payload = {
                            "user_id": user_map[sel_user_email],
                            "work_role": sel_role,
                            "assigned_from": str(date.today())
                        }
                        if authenticated_request("POST", f"/admin/projects/{selected_proj_id}/members", data=payload):
                            st.toast("✅ User assigned successfully!", icon="🚀")
                            time.sleep(1)
                            st.rerun()