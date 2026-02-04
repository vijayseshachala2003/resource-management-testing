import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone as tz
import pytz
from role_guard import setup_role_access

# --- CONFIGURATION ---
st.set_page_config(page_title="Attendance Request Approvals", layout="wide")
setup_role_access(__file__)
API_BASE_URL = "http://127.0.0.1:8000"

# --- HELPER FUNCTIONS ---
def authenticated_request(method, endpoint, data=None, params=None):
    """Make authenticated API request"""
    token = st.session_state.get("token")
    if not token:
        st.warning("🔒 Please login first.")
        st.stop()
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.request(
            method, 
            f"{API_BASE_URL}{endpoint}", 
            headers=headers, 
            json=data,
            params=params
        )
        if response.status_code >= 400:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
        return response.json()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None


def get_pending_requests(request_type=None):
    """Fetch pending attendance requests that need approval"""
    params = {"status": "PENDING"}
    if request_type and request_type != "All":
        params["request_type"] = request_type
    return authenticated_request("GET", "/admin/attendance-requests/", params=params)


def get_all_requests(status=None, request_type=None):
    """Fetch all attendance requests with optional filters"""
    params = {}
    if status and status != "All":
        params["status"] = status
    if request_type and request_type != "All":
        params["request_type"] = request_type
    return authenticated_request("GET", "/admin/attendance-requests/", params=params)


def get_approval_history():
    """Fetch approval history"""
    return authenticated_request("GET", "/admin/attendance-request-approvals/")


def submit_approval(request_id, decision, comment=""):
    """Submit approval/rejection for a request"""
    user_id = st.session_state.get("user_id")
    
    # Fallback: Get user_id from /me/ endpoint if not in session
    if not user_id:
        me_data = authenticated_request("GET", "/me/")
        if me_data and me_data.get("id"):
            user_id = str(me_data["id"])
            st.session_state["user_id"] = user_id  # Cache it
        else:
            st.error("Could not get user ID. Please log out and log back in.")
            return None
    
    payload = {
        "request_id": request_id,
        "approver_user_id": user_id,
        "decision": decision,
        "comment": comment
    }
    return authenticated_request("POST", "/admin/attendance-request-approvals/", data=payload)


def delete_approval(approval_id):
    """Delete an approval record"""
    return authenticated_request("DELETE", f"/admin/attendance-request-approvals/{approval_id}")


def update_approval(approval_id, decision, comment):
    """Update an approval record"""
    payload = {"decision": decision, "comment": comment}
    return authenticated_request("PUT", f"/admin/attendance-request-approvals/{approval_id}", data=payload)


# --- PAGE HEADER ---
st.title("📋 Attendance Request Approvals")

# --- LOAD FILTERS ---
projects = authenticated_request("GET", "/admin/projects") or []
project_options = {"All Projects": None}
for p in projects:
    project_options[p["name"]] = p["id"]

# --- TODAY'S METRICS ---
# Get today's date in local timezone
local_tz = pytz.timezone("Asia/Kolkata")  # Adjust to your timezone if different
today_local = datetime.now(local_tz).date()

# Fetch recent and filter client-side
all_approvals = authenticated_request("GET", "/admin/attendance-request-approvals/") or []

# Filter approvals/rejections that were decided today (in local timezone)
today_approvals = []
today_rejections = []

for a in all_approvals:
    decision = a.get('decision')
    decided_at_str = a.get('decided_at', '')
    
    if not decided_at_str:
        continue
    
    try:
        # Parse the decided_at timestamp (could be ISO format with or without timezone)
        if 'T' in decided_at_str:
            # Parse ISO format timestamp
            if decided_at_str.endswith('Z'):
                # UTC timezone
                dt = datetime.fromisoformat(decided_at_str.replace('Z', '+00:00'))
            elif '+' in decided_at_str or decided_at_str.count('-') > 2:
                # Has timezone info
                dt = datetime.fromisoformat(decided_at_str)
            else:
                # No timezone, assume UTC
                dt = datetime.fromisoformat(decided_at_str)
                dt = dt.replace(tzinfo=tz.utc)
            
            # Convert to local timezone and get date
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz.utc)
            dt_local = dt.astimezone(local_tz)
            decided_date = dt_local.date()
            
            # Compare with today's date
            if decided_date == today_local:
                if decision == "APPROVED":
                    today_approvals.append(a)
                elif decision == "REJECTED":
                    today_rejections.append(a)
        else:
            # Just a date string, compare directly
            decided_date = datetime.fromisoformat(decided_at_str.split()[0]).date()
            if decided_date == today_local:
                if decision == "APPROVED":
                    today_approvals.append(a)
                elif decision == "REJECTED":
                    today_rejections.append(a)
    except Exception as e:
        # Skip invalid date formats
        continue

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Approvals Today", len(today_approvals))
col_m2.metric("Rejections Today", len(today_rejections))

st.markdown("---")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📥 Pending Requests", "📜 Approval History", "⚙️ Manage Approvals"])

# =====================
# TAB 1: PENDING REQUESTS
# =====================
with tab1:
    st.subheader("Pending Attendance Requests")
    
    # Filters Row
    f_col1, f_col2, f_col3, f_col4 = st.columns([1.5, 1.5, 1, 1])
    with f_col1:
        selected_project_name = st.selectbox("Filter Project", list(project_options.keys()), key="pending_project_filter")
        selected_project_id = project_options[selected_project_name]
    
    with f_col2:
        filter_type = st.selectbox(
            "Filter Type", 
            ["All", "SICK_LEAVE", "WFH", "REGULARIZATION", "SHIFT_CHANGE", "OTHER"],
            key="pending_type_filter"
        )
    
    with f_col3:
        date_from = st.date_input("From", value=None, key="pending_date_from")
    
    with f_col4:
        date_to = st.date_input("To", value=None, key="pending_date_to")

    # Fetch all pending
    pending = authenticated_request("GET", "/admin/attendance-requests/", params={"status": "PENDING"}) or []
    
    # Client-side filtering
    if filter_type != "All":
        pending = [r for r in pending if r.get('request_type') == filter_type]
    if selected_project_id:
        pending = [r for r in pending if r.get('project_id') == str(selected_project_id)]
    if date_from:
        pending = [r for r in pending if r.get('start_date') >= str(date_from)]
    if date_to:
        pending = [r for r in pending if r.get('end_date') <= str(date_to)]
    
    if not pending:
        st.success("🎉 All caught up! No pending requests to approve.")
    else:
        st.info(f"**{len(pending)}** requests waiting for your review")
        
        for req in pending:
            with st.container(border=True):
                # Layout with user info
                col_user, col_info, col_dates, col_actions = st.columns([2, 2, 2, 1.5])
                
                with col_user:
                    user_name = req.get('user_name', 'Unknown')
                    user_id = req.get('user_id') or 'N/A'
                    st.markdown(f"### 👤 {user_name}")
                    st.caption(f"User ID: `{str(user_id)[:8]}...`")
                    if req.get('user_email'):
                        st.caption(f"📧 {req['user_email']}")
                
                with col_info:
                    request_type = req.get('request_type', 'SICK_LEAVE')
                    type_emoji = {
                        'SICK_LEAVE': '🏖️',
                        'WFH': '🏠',
                        'REGULARIZATION': '📝',
                        'SHIFT_CHANGE': '🔄',
                        'OTHER': '📋'
                    }.get(request_type, '📋')
                    
                    st.markdown(f"**{type_emoji} {request_type}**")
                    st.caption(f"Request ID: `{req.get('id', 'N/A')[:8]}...`")
                    
                    if req.get('reason'):
                        st.write(f"**Reason:** {req['reason']}")
                
                with col_dates:
                    st.metric("Start Date", req.get('start_date', 'N/A'))
                    st.metric("End Date", req.get('end_date', 'N/A'))
                
                with col_actions:
                    st.write("")  # Spacer
                    request_id = req.get('id')
                    
                    # Approve Button
                    if st.button("✅ Approve", key=f"approve_{request_id}", use_container_width=True, type="primary"):
                        result = submit_approval(request_id, "APPROVED", "Approved")
                        if result:
                            st.toast("✅ Request approved!", icon="👍")
                            st.rerun()
                    
                    # Reject with reason
                    with st.popover("❌ Reject", use_container_width=True):
                        reason = st.text_input("Rejection reason", key=f"reason_{request_id}")
                        if st.button("Confirm Reject", key=f"conf_reject_{request_id}", type="primary"):
                            result = submit_approval(request_id, "REJECTED", reason or "Rejected")
                            if result:
                                st.toast("❌ Request rejected", icon="👎")
                                st.rerun()


# =====================
# TAB 2: APPROVAL HISTORY
# =====================
with tab2:
    st.subheader("Approval History")
    
    # Filters
    h_col1, h_col2, h_col3, h_col4 = st.columns([1.5, 1.5, 1, 1])
    with h_col1:
        filter_decision = st.selectbox("Status", ["All", "APPROVED", "REJECTED"], key="history_decision_filter")
    with h_col2:
        filter_req_type = st.selectbox(
            "Request Type", 
            ["All", "SICK_LEAVE", "WFH", "REGULARIZATION", "SHIFT_CHANGE", "OTHER"],
            key="history_type_filter"
        )
    with h_col3:
        h_date_from = st.date_input("From", value=None, key="history_date_from")
    with h_col4:
        h_date_to = st.date_input("To", value=None, key="history_date_to")
    
    # Fetch all history (use limit if available)
    history = authenticated_request("GET", "/admin/attendance-request-approvals/", params={"limit": 100}) or []
    
    # Client-side filtering
    if filter_decision != "All":
        history = [h for h in history if h.get('decision') == filter_decision]
    if h_date_from:
        history = [h for h in history if h.get('decided_at', '') >= str(h_date_from)]
    if h_date_to:
        # Simple string compare for dates in ISO timestamps
        history = [h for h in history if h.get('decided_at', '') <= str(h_date_to) + " 23:59:59"]
    all_requests = get_all_requests()
    
    # Fetch all users to create approver lookup
    all_users = authenticated_request("GET", "/admin/users/", params={"limit": 1000}) or []
    approver_lookup = {}
    for user in all_users:
        user_id = user.get('id')
        if user_id:
            approver_lookup[str(user_id)] = user.get('name', 'Unknown')
    
    if not history:
        st.info("No approval history found.")
    else:
        # Create lookup for request info
        request_lookup = {}
        if all_requests:
            for req in all_requests:
                request_lookup[req.get('id')] = {
                    'user_name': req.get('user_name', 'Unknown'),
                    'user_id': req.get('user_id'),
                    'request_type': req.get('request_type'),
                    'reason': req.get('reason'),
                    'start_date': req.get('start_date', 'N/A'),
                    'end_date': req.get('end_date', 'N/A')
                }
        
        # Enrich history with request info
        enriched_history = []
        for h in history:
            req_id = h.get('request_id')
            req_info = request_lookup.get(req_id, {})
            
            # Filter by request type
            if filter_req_type != "All" and req_info.get('request_type') != filter_req_type:
                continue
            
            # Get approver name
            approver_user_id = h.get('approver_user_id')
            approver_name = 'Unknown'
            if approver_user_id:
                approver_name = approver_lookup.get(str(approver_user_id), 'Unknown')
            
            enriched_history.append({
                'decision': h.get('decision'),
                'user_name': req_info.get('user_name', 'Unknown'),
                'user_id': str(req_info.get('user_id', 'N/A'))[:8] + '...',
                'request_type': req_info.get('request_type', 'N/A'),
                'start_date': req_info.get('start_date', 'N/A'),
                'end_date': req_info.get('end_date', 'N/A'),
                'approver_name': approver_name,
                'comment': h.get('comment'),
                'decided_at': h.get('decided_at', '')[:19],  # Truncate timestamp
                'approval_id': str(h.get('id', ''))[:8] + '...',
            })
        
        # Filter by decision
        if filter_decision != "All":
            enriched_history = [h for h in enriched_history if h.get('decision') == filter_decision]
        
        if enriched_history:
            df = pd.DataFrame(enriched_history)
            df.columns = ['Decision', 'Requester Name', 'User ID', 'Request Type', 'From Date', 'To Date', 'Approved By', 'Comment', 'Decided At', 'Approval ID']
            
            # Add status color
            def color_decision(val):
                if val == 'APPROVED':
                    return 'background-color: #d4edda; color: #155724'
                elif val == 'REJECTED':
                    return 'background-color: #f8d7da; color: #721c24'
                return ''
            
            st.dataframe(
                df.style.map(color_decision, subset=['Decision']),
                use_container_width=True,
                hide_index=True
            )
            
            st.caption(f"Showing {len(df)} records")
        else:
            st.info("No records match the filters.")


# =====================
# TAB 3: MANAGE APPROVALS (CRUD)
# =====================
with tab3:
    st.subheader("Manage Approval Records")
    
    crud_action = st.radio("Action", ["Update Approval", "Delete Approval"], horizontal=True)
    
    st.markdown("---")
    
    if crud_action == "Update Approval":
        st.write("**Update an existing approval record**")
        
        with st.form("update_form"):
            approval_id = st.text_input("Approval ID (UUID)")
            new_decision = st.selectbox("New Decision", ["APPROVED", "REJECTED"])
            new_comment = st.text_area("New Comment")
            
            submitted = st.form_submit_button("Update Approval", type="primary")
            
            if submitted:
                if approval_id:
                    result = update_approval(approval_id, new_decision, new_comment)
                    if result:
                        st.success("✅ Approval updated successfully!")
                        st.json(result)
                else:
                    st.warning("Please enter an Approval ID")
    
    elif crud_action == "Delete Approval":
        st.write("**Delete an approval record**")
        st.warning("⚠️ This action cannot be undone!")
        
        with st.form("delete_form"):
            approval_id = st.text_input("Approval ID to delete (UUID)")
            confirm = st.checkbox("I confirm I want to delete this record")
            
            submitted = st.form_submit_button("Delete Approval", type="primary")
            
            if submitted:
                if approval_id and confirm:
                    result = delete_approval(approval_id)
                    if result:
                        st.success("✅ Approval deleted successfully!")
                else:
                    st.warning("Please enter an Approval ID and confirm deletion")


# # --- SIDEBAR INFO ---
# with st.sidebar:
#     st.markdown("### ℹ️ About This Page")
#     st.markdown("""
#     **Attendance Request Approvals** allows managers to:
    
#     - 📥 View and approve pending requests
#     - 📜 See approval history with filters
#     - ⚙️ Manage (update/delete) approvals
    
#     ---
    
#     **Filters Available:**
#     - Request Type (LEAVE, WFH, etc.)
#     - Decision (APPROVED, REJECTED)
#     """)
