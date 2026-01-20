import streamlit as st
from api import api_request
import requests
from datetime import datetime


st.set_page_config(page_title="Attendance Requests", layout="wide")

_CSS = """
<style>
  .att-card { padding:16px; border-radius:10px; background:linear-gradient(180deg,#0f1724, #071025); border:1px solid rgba(255,255,255,0.03); margin-bottom:12px }
  .small { font-size:13px; color:#9aa4b2 }
  .badge { padding:6px 10px; border-radius:999px; font-weight:600; font-size:12px }
  .badge-pending{ background:rgba(255,200,60,0.08); color:#ffb703; border:1px solid rgba(255,200,60,0.12) }
  .badge-approved{ background:rgba(0,200,100,0.06); color:#00c853; border:1px solid rgba(0,200,100,0.08) }
  .badge-rejected{ background:rgba(255,80,80,0.06); color:#ff6b6b; border:1px solid rgba(255,80,80,0.08) }
  .muted { color:#9aa4b2 }
  .form-label{ color:#cbd5e1 }
</style>
"""


def require_token():
    token = st.session_state.get("token")
    if not token:
        st.warning("Please login to access Attendance Requests.")
        st.stop()
    return token


def fetch_projects(token):
    try:
        return api_request("GET", "/admin/projects/", token=token)
    except Exception:
        return []


def create_request(token, payload):
    return api_request("POST", "/attendance/requests/", token=token, json=payload)


def list_requests(token, params=None):
    return api_request("GET", "/attendance/requests", token=token, params=params)


def cancel_request(token, req_id):
    # backend delete may return message; api_request will raise on error
    return api_request("DELETE", f"/attendance/requests/{req_id}", token=token)


st.markdown(_CSS, unsafe_allow_html=True)

st.title("Attendance Requests")
st.caption("Create, view and manage your attendance change requests")
st.write("---")

token = st.session_state.get("token")
if not token:
    st.info("You must log in from the app sidebar before using this page.")
    st.stop()


cols = st.columns([1, 2], gap="large")

with cols[0]:
    st.subheader("New Request")

    projects = fetch_projects(token) or []
    proj_map = {p["id"]: p["name"] for p in projects}
    proj_name_to_id = {p["name"]: p["id"] for p in projects}
    proj_names = ["— none —"] + list(proj_name_to_id.keys())

    with st.form("request_form"):
        project = st.selectbox("Project", options=proj_names, index=0, help="Optional: associate request with a project")
        project_id = proj_name_to_id.get(project) if project != "— none —" else None

        req_type = st.selectbox("Type", ["LEAVE", "REGULARIZATION", "SHIFT_CHANGE", "WFH", "OTHER"])

        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start Date")
            start_time = st.time_input("Start Time (optional)")
        with c2:
            end_date = st.date_input("End Date")
            end_time = st.time_input("End Time (optional)")

        reason = st.text_area("Reason", placeholder="Short justification for the request", height=110)
        attachment_url = st.text_input("Attachment URL (optional)", placeholder="Paste a link to supporting document")

        submitted = st.form_submit_button("Submit Request")

        if submitted:
            if start_date > end_date:
                st.error("Start date cannot be after end date")
            else:
                payload = {
                    "project_id": project_id,
                    "request_type": req_type,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "start_time": start_time.isoformat() if start_time else None,
                    "end_time": end_time.isoformat() if end_time else None,
                    "reason": reason or None,
                    "attachment_url": attachment_url or None,
                }
                try:
                    create_request(token, payload)
                    st.success("Request submitted")
                    st.rerun()

                except Exception as e:
                    st.error(f"Failed to submit: {e}")

with cols[1]:
    st.subheader("Your Requests")

    # Filters
    fcol1, fcol2 = st.columns([2, 1])
    with fcol1:
        q = st.text_input("Search", placeholder="Search by project, type, or reason")
    with fcol2:
        status_filter = st.selectbox("Status", ["ALL", "PENDING", "APPROVED", "REJECTED"], index=0)

    try:
        items = list_requests(token) or []
    except Exception as e:
        st.error(f"Unable to fetch requests: {e}")
        st.stop()

    # client-side filtering
    def matches(it):
        if status_filter != "ALL" and (it.get('status') or '').upper() != status_filter:
            return False

        if q:
            qlow = q.lower()
            project_name = proj_map.get(it.get("project_id"), "").lower()

            if qlow in str(it.get('request_type','')).lower():
                return True
            if qlow in project_name:
                return True
            if qlow in str(it.get('reason','')).lower():
                return True
            return False

        return True


    visible = [it for it in items if matches(it)]

    if not visible:
        st.info("No requests found — create a request using the form on the left.")
    else:
        for it in visible:
            status = (it.get('status') or '').upper()
            badge_class = 'badge-pending' if status == 'PENDING' else ('badge-approved' if status == 'APPROVED' else 'badge-rejected')
            submitted_at = it.get('requested_at') or it.get('created_at')
            submitted_display = submitted_at and datetime.fromisoformat(submitted_at).strftime('%b %d, %Y %I:%M %p') or ''

            st.markdown(f"<div class='att-card'>", unsafe_allow_html=True)
            rcol, acol = st.columns([5, 1])
            with rcol:
                st.markdown(f"### {it.get('request_type','Request')} <span class='badge {badge_class}'>{status}</span>", unsafe_allow_html=True)
                st.markdown(
    f"<div class='small'>Project: <b>{proj_map.get(it.get('project_id'), '—')}</b> • Submitted: {submitted_display}</div>",
    unsafe_allow_html=True
)

                st.write(f"**Period:** {it.get('start_date') or '—'} → {it.get('end_date') or '—'}")
                if it.get('reason'):
                    with st.expander("Reason"):
                        st.write(it.get('reason'))
                if it.get('attachment_url'):
                    st.markdown(f"[Attachment]({it.get('attachment_url')})")

            with acol:
                if status == 'PENDING':
                    if st.button("Cancel", key=f"cancel_{it['id']}"):
                        try:
                            cancel_request(token, it['id'])
                            st.success("Canceled")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Cancel failed: {e}")
                else:
                    st.markdown(f"<div class='muted'>{status}</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

    st.write("\n")
    if st.button("Refresh"):
       st.rerun()
