import streamlit as st
from api import api_request
from datetime import datetime
import pytz

st.set_page_config(page_title="Attendance Requests", layout="wide")

# ---------------- CSS ----------------
_CSS = """
<style>
.att-card { padding:16px; border-radius:10px; background:#0f1724; border:1px solid rgba(255,255,255,0.05); margin-bottom:12px }
.small { font-size:13px; color:#9aa4b2 }
.badge { padding:6px 10px; border-radius:999px; font-weight:600; font-size:12px }
.badge-pending{ background:#332b00; color:#ffb703 }
.badge-approved{ background:#00331a; color:#00c853 }
.badge-rejected{ background:#330000; color:#ff6b6b }
.muted { color:#9aa4b2 }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

# ---------------- Helpers ----------------

def format_time_local(ts):
    if not ts:
        return ""
    dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
    local = dt.astimezone(pytz.timezone("Asia/Kolkata"))
    return local.strftime("%d %b %Y %I:%M %p")

def fetch_projects(token):
    return api_request("GET","/admin/projects/",token=token)

def create_request(token,payload):
    return api_request("POST","/attendance/requests/",token=token,json=payload)

def update_request(token,req_id,payload):
    return api_request("PUT",f"/attendance/requests/{req_id}",token=token,json=payload)

def list_requests(token):
    return api_request("GET","/attendance/requests",token=token)

def cancel_request(token,req_id):
    return api_request("DELETE",f"/attendance/requests/{req_id}",token=token)

# ---------------- Auth ----------------

token = st.session_state.get("token")
if not token:
    st.warning("Please login first")
    st.stop()

# ---------------- UI ----------------

st.title("Attendance Requests")
st.caption("Create, view and manage your attendance requests")
st.write("---")

cols = st.columns([1,2],gap="large")

# ==========================================================
# LEFT SIDE : CREATE REQUEST
# ==========================================================

with cols[0]:

    st.subheader("New Request")

    projects = fetch_projects(token) or []
    proj_name_to_id = {p["name"]:p["id"] for p in projects}
    proj_id_to_name = {p["id"]:p["name"] for p in projects}

    proj_names = ["— none —"] + list(proj_name_to_id.keys())

    with st.form("request_form"):

        project = st.selectbox("Project",proj_names)
        project_id = proj_name_to_id.get(project) if project!="— none —" else None

        req_type = st.selectbox("Type",["LEAVE","REGULARIZATION","SHIFT_CHANGE","WFH","OTHER"])

        c1,c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start Date")
            start_time = st.time_input("Start Time (optional)")
        with c2:
            end_date = st.date_input("End Date")
            end_time = st.time_input("End Time (optional)")

        reason = st.text_area("Reason")
        attachment_url = st.text_input("Attachment URL (optional)")

        submit = st.form_submit_button("Submit Request")

        if submit:
            payload = {
                "project_id": project_id,
                "request_type": req_type,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None,
                "reason": reason or None,
                "attachment_url": attachment_url or None
            }
            create_request(token,payload)
            st.success("Request submitted successfully")
            st.rerun()

# ==========================================================
# RIGHT SIDE : LIST REQUESTS
# ==========================================================

with cols[1]:

    st.subheader("Your Requests")

    status_filter = st.selectbox("Status Filter",["ALL","PENDING","APPROVED","REJECTED"])

    items = list_requests(token) or []

    def matches(it):
        if status_filter!="ALL" and (it.get("status") or "").upper()!=status_filter:
            return False
        return True

    visible = [i for i in items if matches(i)]

    if not visible:
        st.info("No requests found.")
    else:
        for it in visible:

            status = (it.get("status") or "").upper()

            if status=="PENDING":
                badge_class = "badge-pending"
            elif status=="APPROVED":
                badge_class = "badge-approved"
            elif status=="REJECTED":
                badge_class = "badge-rejected"
            else:
                badge_class = "badge-pending"

            submitted_at = it.get("requested_at") or it.get("created_at")
            submitted_display = format_time_local(submitted_at)

            st.markdown("<div class='att-card'>",unsafe_allow_html=True)

            rcol,acol = st.columns([5,1])

            with rcol:

                st.markdown(
                    f"### {it.get('request_type','Request')} "
                    f"<span class='badge {badge_class}'>{status}</span>",
                    unsafe_allow_html=True
                )

                st.markdown(
                    f"<div class='small'>Project: <b>{proj_id_to_name.get(it.get('project_id'),'—')}</b> "
                    f"• Submitted: {submitted_display}</div>",
                    unsafe_allow_html=True
                )

                st.write(f"**Period:** {it.get('start_date') or '—'} → {it.get('end_date') or '—'}")

                if it.get("reason"):
                    with st.expander("Reason"):
                        st.write(it.get("reason"))

            with acol:

                if status=="PENDING":
                    if st.button("Cancel",key=f"cancel_{it['id']}"):
                        cancel_request(token,it["id"])
                        st.success("Canceled")
                        st.rerun()
                else:
                    st.markdown(f"<div class='muted'>{status}</div>",unsafe_allow_html=True)

            st.markdown("</div>",unsafe_allow_html=True)

    if st.button("Refresh"):
        st.rerun()

