import streamlit as st
import requests
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Approvals Inbox", layout="centered")
API_BASE_URL = "http://127.0.0.1:8000"

# --- HELPER FUNCTIONS ---
def authenticated_request(method, endpoint, data=None):
    token = st.session_state.get("token")
    if not token:
        st.warning("🔒 Please login first.")
        st.stop()

    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.request(method, f"{API_BASE_URL}{endpoint}", headers=headers, json=data)
        # response = requests.request(method, f"{API_BASE_URL}{endpoint}", json=data)
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
        if action == "approve":
            st.toast(f"✅ Approved log #{history_id}", icon="👍")
        else:
            st.toast(f"❌ Rejected log #{history_id}", icon="👎")
        
        time.sleep(1)
        st.rerun()

# --- TITLE ---
st.title("Inbox: Pending Approvals")
st.markdown("Verify and approve team timesheets.")
st.markdown("---")

# --- FETCH DATA ---
# We use the Dashboard API to get the list of pending items
pending_items = authenticated_request("GET", "/admin/dashboard/pending-approvals")

if not pending_items:
    st.success("🎉 All caught up! No pending approvals.")
    st.balloons()
else:
    st.write(f"**{len(pending_items)} Pending Items**")
    
    for item in pending_items:
        with st.container(border=True):
            # Layout: Details on Left | Actions on Right
            c_details, c_actions = st.columns([3, 1])
            
            with c_details:
                # Header: Name & Project
                st.markdown(f"### 👤 {item['user_name']}")
                st.caption(f"📂 **{item['project_name']}** | Role: `{item['work_role']}`")
                
                # Stats Grid
                col1, col2, col3 = st.columns(3)
                col1.metric("Date", item['sheet_date'])
                
                # Format Duration nicely
                dur_val = f"{item['duration_minutes']} min"
                col2.metric("Duration", dur_val)
                
                col3.metric("Tasks", item['tasks_completed'])
                
            with c_actions:
                st.write("") # Spacer
                st.write("") 
                
                # Approve Button
                if st.button("✅ Approve", key=f"app_{item['history_id']}", use_container_width=True, type="primary"):
                    submit_decision(item['history_id'], "approve", "Approved via Inbox")
                
                # Reject Button (with popover for optional comment)
                with st.popover("❌ Reject"):
                    st.write("Confirm Rejection")
                    reason = st.text_input("Reason (Optional)", key=f"reason_{item['history_id']}")
                    if st.button("Confirm Reject", key=f"conf_rej_{item['history_id']}", type="primary"):
                        submit_decision(item['history_id'], "reject", reason)
