import streamlit as st
import requests
import time
import pandas as pd
from datetime import date, datetime
from role_guard import get_user_role

# --- CONFIGURATION ---
st.set_page_config(page_title="Timesheet Approvals", layout="wide")

# Basic role check
role = get_user_role()
if not role or role not in ["ADMIN", "MANAGER"]:
    st.error("Access denied. Admin or Manager role required.")
    st.stop()
API_BASE_URL = "http://127.0.0.1:8000"

# --- HELPER FUNCTIONS ---
def authenticated_request(method, endpoint, data=None, params=None):
    token = st.session_state.get("token")
    if not token:
        st.warning("🔒 Please login first.")
        st.stop()

    headers = {"Authorization": f"Bearer {token}"}
    try:
        if method.upper() == "GET" and params:
            response = requests.request(method, f"{API_BASE_URL}{endpoint}", headers=headers, params=params)
        else:
            response = requests.request(method, f"{API_BASE_URL}{endpoint}", headers=headers, json=data)
        if response.status_code >= 400:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
        return response.json()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def submit_decision(history_id, action, notes=""):
    # 1. Determine Status string required by backend
    status_val = "APPROVED" if action == "approve" else "REJECTED"
    
    # 2. Prepare Payload matching ApprovalRequest schema
    payload = {
        "status": status_val,
        "approval_comment": notes
    }
    
    # 3. Call the API Endpoint defined in app/api/time/history.py
    resp = authenticated_request("PUT", f"/time/history/{history_id}/approve", data=payload)
    
    # 4. Handle Success
    if resp:
        return True
    return False

def bulk_approve(history_ids, action, notes=""):
    """Approve or reject multiple items at once"""
    success_count = 0
    failed_count = 0
    
    for history_id in history_ids:
        if submit_decision(history_id, action, notes):
            success_count += 1
        else:
            failed_count += 1
    
    return success_count, failed_count

# --- TITLE ---
st.title("📋 Timesheet Approvals")
st.markdown("Verify and approve team timesheets. Only project managers and admins can see approvals for their projects.")
st.markdown("---")

# --- FETCH DATA ---
pending_items = authenticated_request("GET", "/admin/dashboard/pending-approvals") or []

# --- FILTERS ---
st.subheader("🔍 Filters")
filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

with filter_col1:
    # Project filter
    projects = authenticated_request("GET", "/admin/projects/") or []
    project_options = ["All Projects"] + [p["name"] for p in projects]
    selected_project = st.selectbox("Project", options=project_options, key="filter_project")

with filter_col2:
    # Work Role filter
    if pending_items:
        all_roles = sorted(list(set([item.get("work_role", "") for item in pending_items if item.get("work_role")])))
        role_options = ["All Roles"] + all_roles
    else:
        role_options = ["All Roles"]
    selected_role = st.selectbox("Work Role", options=role_options, key="filter_role")

with filter_col3:
    # Date from filter
    date_from = st.date_input("Date From", value=None, key="filter_date_from")

with filter_col4:
    # Date to filter
    date_to = st.date_input("Date To", value=None, key="filter_date_to")

# Apply filters
filtered_items = pending_items.copy()

if selected_project and selected_project != "All Projects":
    filtered_items = [item for item in filtered_items if item.get("project_name") == selected_project]

if selected_role and selected_role != "All Roles":
    filtered_items = [item for item in filtered_items if item.get("work_role") == selected_role]

if date_from:
    date_from_str = str(date_from)
    filtered_items = [item for item in filtered_items if item.get("sheet_date") >= date_from_str]

if date_to:
    date_to_str = str(date_to)
    filtered_items = [item for item in filtered_items if item.get("sheet_date") <= date_to_str]

st.markdown("---")

# --- BULK ACTIONS ---
if filtered_items:
    st.subheader(f"📊 Results: {len(filtered_items)} Pending Item(s)")
    
    # Initialize session state for selected items
    if "selected_approvals" not in st.session_state:
        st.session_state.selected_approvals = set()
    
    # Bulk action section
    bulk_col1, bulk_col2, bulk_col3 = st.columns([2, 1, 1])
    
    with bulk_col1:
        st.markdown("**Bulk Actions:**")
        all_selected = len(st.session_state.selected_approvals) == len(filtered_items) and len(filtered_items) > 0
        select_all = st.checkbox("Select All", value=all_selected, key="select_all_approvals")
        if select_all and not all_selected:
            st.session_state.selected_approvals = {item["history_id"] for item in filtered_items}
            st.rerun()
        elif not select_all and all_selected:
            st.session_state.selected_approvals = set()
            st.rerun()
    
    with bulk_col2:
        selected_count = len(st.session_state.selected_approvals)
        if selected_count > 0:
            if st.button(f"✅ Bulk Approve ({selected_count})", type="primary", use_container_width=True, key="bulk_approve_btn"):
                history_ids = list(st.session_state.selected_approvals)
                success, failed = bulk_approve(history_ids, "approve", "Bulk approved via Inbox")
                if success > 0:
                    st.success(f"✅ Successfully approved {success} item(s)")
                if failed > 0:
                    st.error(f"❌ Failed to approve {failed} item(s)")
                st.session_state.selected_approvals = set()
                time.sleep(1)
                st.rerun()
    
    with bulk_col3:
        if selected_count > 0:
            with st.popover(f"❌ Bulk Reject ({selected_count})", use_container_width=True):
                reject_reason = st.text_input("Rejection Reason (Optional)", key="bulk_reject_reason")
                if st.button("Confirm Bulk Reject", type="primary", key="bulk_reject_confirm"):
                    history_ids = list(st.session_state.selected_approvals)
                    success, failed = bulk_approve(history_ids, "reject", reject_reason)
                    if success > 0:
                        st.success(f"✅ Successfully rejected {success} item(s)")
                    if failed > 0:
                        st.error(f"❌ Failed to reject {failed} item(s)")
                    st.session_state.selected_approvals = set()
                    time.sleep(1)
                    st.rerun()
    
    st.markdown("---")
    
    # --- TABLE VIEW ---
    # Prepare data for table
    table_data = []
    for item in filtered_items:
        history_id = item.get("history_id")
        is_selected = history_id in st.session_state.selected_approvals
        
        # Format duration
        duration = item.get("duration_minutes", 0)
        duration_str = f"{duration:.1f} min" if duration else "0 min"
        
        # Format clock in/out times
        clock_in = item.get("clock_in")
        clock_out = item.get("clock_out")
        
        # Handle datetime objects or strings
        if clock_in:
            if isinstance(clock_in, datetime):
                clock_in_str = clock_in.strftime("%I:%M %p")
            elif isinstance(clock_in, str):
                try:
                    dt = datetime.fromisoformat(clock_in.replace("Z", "+00:00"))
                    clock_in_str = dt.strftime("%I:%M %p")
                except:
                    clock_in_str = str(clock_in)
            else:
                clock_in_str = str(clock_in)
        else:
            clock_in_str = "-"
        
        if clock_out:
            if isinstance(clock_out, datetime):
                clock_out_str = clock_out.strftime("%I:%M %p")
            elif isinstance(clock_out, str):
                try:
                    dt = datetime.fromisoformat(clock_out.replace("Z", "+00:00"))
                    clock_out_str = dt.strftime("%I:%M %p")
                except:
                    clock_out_str = str(clock_out)
            else:
                clock_out_str = str(clock_out)
        else:
            clock_out_str = "-"
        
        table_data.append({
            "Select": is_selected,
            "User": item.get("user_name", "-"),
            "Project": item.get("project_name", "-"),
            "Work Role": item.get("work_role", "-"),
            "Date": item.get("sheet_date", "-"),
            "Clock In": clock_in_str,
            "Clock Out": clock_out_str,
            "Duration": duration_str,
            "Tasks": item.get("tasks_completed", 0),
            "History ID": history_id
        })
    
    # Create DataFrame
    df = pd.DataFrame(table_data)
    
    # Display table with checkboxes
    st.subheader("📋 Approval List")
    
    # Create a custom display with checkboxes
    for idx, row in df.iterrows():
        history_id = row["History ID"]
        current_selected = history_id in st.session_state.selected_approvals
        
        with st.container(border=True):
            col_check, col_info, col_actions = st.columns([0.5, 4, 1.5])
            
            with col_check:
                checkbox_key = f"checkbox_{history_id}"
                is_checked = st.checkbox("", value=current_selected, key=checkbox_key, label_visibility="collapsed")
                
                # Update selection state if changed
                if is_checked != current_selected:
                    if is_checked:
                        st.session_state.selected_approvals.add(history_id)
                    else:
                        st.session_state.selected_approvals.discard(history_id)
                    # Note: We don't rerun here to avoid too many reruns, but the state is updated
            
            with col_info:
                # Display all information in a clean grid
                info_col1, info_col2, info_col3, info_col4 = st.columns(4)
                
                with info_col1:
                    st.markdown(f"**👤 {row['User']}**")
                    st.caption(f"📂 {row['Project']}")
                
                with info_col2:
                    st.markdown(f"**Role:** {row['Work Role']}")
                    st.markdown(f"**Date:** {row['Date']}")
                
                with info_col3:
                    st.markdown(f"**⏰ Clock In:** {row['Clock In']}")
                    st.markdown(f"**⏰ Clock Out:** {row['Clock Out']}")
                
                with info_col4:
                    st.markdown(f"**⏱️ Duration:** {row['Duration']}")
                    st.markdown(f"**✅ Tasks:** {row['Tasks']}")
            
            with col_actions:
                st.write("")  # Spacer
                action_col1, action_col2 = st.columns(2)
                
                with action_col1:
                    if st.button("✅ Approve", key=f"app_{history_id}", use_container_width=True, type="primary"):
                        if submit_decision(history_id, "approve", "Approved via Inbox"):
                            st.success("✅ Approved")
                            st.toast(f"✅ Approved log #{history_id}", icon="👍")
                            time.sleep(1)
                            st.rerun()
                
                with action_col2:
                    with st.popover("❌ Reject", use_container_width=True):
                        st.write("Confirm Rejection")
                        reason = st.text_input("Reason (Optional)", key=f"reason_{history_id}")
                        if st.button("Confirm Reject", key=f"conf_rej_{history_id}", type="primary"):
                            if submit_decision(history_id, "reject", reason):
                                st.success("❌ Rejected")
                                st.toast(f"❌ Rejected log #{history_id}", icon="👎")
                                time.sleep(1)
                                st.rerun()
            
            st.markdown("---")
    
    # Alternative: Show as dataframe (read-only view)
    st.subheader("📊 Data Table View")
    display_df = df[["User", "Project", "Work Role", "Date", "Clock In", "Clock Out", "Duration", "Tasks"]].copy()
    st.dataframe(display_df, use_container_width=True, height=400)

else:
    if not pending_items:
        st.success("🎉 All caught up! No pending approvals.")
        st.balloons()
    else:
        st.info(f"ℹ️ No items match the selected filters. Total pending: {len(pending_items)}")
