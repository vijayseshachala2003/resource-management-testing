from pathlib import Path
import os

import requests
import streamlit as st


ALLOWED_USER_PAGES = {
    "3_Home.py": "Home",
    "1_History.py": "History",
    "4_Attendance_Requests.py": "Attendance Requests",
    "2_team_history.py": "Team History",
}

ADMIN_ALLOWED_PAGES = {
    "7_Project_Resource_Allocation.py": "Project Resource Allocation",
    "user_productivity_dashboard.py": "User Productivity",
    "project_productivity_dashboard.py": "Project Productivity",
    "05_Reports_Center.py": "Reports Center",
    "2_Admin_Projects.py": "Admin Projects",
    "3_Admin.py": "Admin Panel",
    "5_Approvals.py": "Approvals",
    "6_Attendance_Approvals.py": "Attendance Approvals",
}


def _refresh_role_from_backend() -> None:
    token = st.session_state.get("token")
    if not token:
        return

    if st.session_state.get("role_synced"):
        return

    api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{api_base_url}/me/", headers=headers, timeout=5)
        if response.status_code >= 400:
            return
        user = response.json()
    except Exception:
        return

    if isinstance(user, dict):
        st.session_state["user"] = user
        st.session_state["user_role"] = user.get("role")
        if user.get("name"):
            st.session_state["user_name"] = user.get("name")

    st.session_state["role_synced"] = True


def _get_user_role() -> str:
    _refresh_role_from_backend()
    role = st.session_state.get("user_role")
    if not role:
        user = st.session_state.get("user")
        if isinstance(user, dict):
            role = user.get("role")
    return str(role).upper() if role else ""


def _hide_default_sidebar_nav() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_user_sidebar_nav() -> None:
    st.sidebar.markdown("### Navigation")
    st.sidebar.page_link("pages/3_Home.py", label="Home")
    st.sidebar.page_link("pages/1_History.py", label="History")
    st.sidebar.page_link("pages/4_Attendance_Requests.py", label="Attendance Requests")
    st.sidebar.page_link("pages/2_team_history.py", label="Team History")


def _render_admin_sidebar_nav() -> None:
    st.sidebar.markdown("### Navigation")
    st.sidebar.page_link("pages/7_Project_Resource_Allocation.py", label="Project Resource Allocation")
    st.sidebar.page_link("pages/user_productivity_dashboard.py", label="User Productivity")
    st.sidebar.page_link("pages/project_productivity_dashboard.py", label="Project Productivity")
    st.sidebar.page_link("pages/05_Reports_Center.py", label="Reports Center")
    st.sidebar.page_link("pages/2_Admin_Projects.py", label="Admin Projects")
    st.sidebar.page_link("pages/3_Admin.py", label="Admin Panel")
    st.sidebar.page_link("pages/5_Approvals.py", label="Approvals")
    st.sidebar.page_link("pages/6_Attendance_Approvals.py", label="Attendance Approvals")


def setup_role_access(current_file: str) -> None:
    role = _get_user_role()
    current_page = Path(current_file).name

    if role in {"ADMIN", "MANAGER"}:
        _hide_default_sidebar_nav()
        _render_admin_sidebar_nav()
        if current_page not in ADMIN_ALLOWED_PAGES and current_page != "app.py":
            st.error("Access restricted. Your role does not have access to this page.")
            st.stop()
        return

    if role != "USER":
        return

    _hide_default_sidebar_nav()
    _render_user_sidebar_nav()

    if current_page not in ALLOWED_USER_PAGES and current_page != "app.py":
        st.error("Access restricted. Your role does not have access to this page.")
        st.stop()

