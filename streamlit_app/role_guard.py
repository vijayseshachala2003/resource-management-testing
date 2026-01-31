from pathlib import Path
import os

import requests
import streamlit as st


ALLOWED_USER_PAGES = {
    "3_Home.py": "Home",
    "1_History.py": "History",
    "4_Attendance_Requests.py": "Leave/WFH Requests",
    "2_Team_Stats.py": "Team Stats",
}

ADMIN_ALLOWED_PAGES = {
    "7_Project_Resource_Allocation.py": "Project Resource Allocation",
    "user_productivity_dashboard.py": "User Productivity",
    "project_productivity_dashboard.py": "Project Productivity",
    "05_Reports_Center.py": "Reports Center",
    "2_Admin_Projects.py": "Admin Projects",
    "5_Approvals.py": "Timesheet Approvals",
    "6_Attendance_Approvals.py": "Attendance Approvals",
}


def _refresh_role_from_backend() -> None:
    token = st.session_state.get("token")
    if not token:
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
        backend_role = user.get("role")
        existing_role = st.session_state.get("user_role")

        if backend_role:
            backend_role_upper = str(backend_role).upper()
            existing_role_upper = str(existing_role).upper() if existing_role else ""

            if backend_role_upper in {"ADMIN", "MANAGER"}:
                st.session_state["user_role"] = backend_role
            elif existing_role_upper in {"ADMIN", "MANAGER"}:
                # Keep elevated role if backend still reports USER
                pass
            else:
                st.session_state["user_role"] = backend_role

        if user.get("name"):
            st.session_state["user_name"] = user.get("name")



def _get_user_role() -> str:
    _refresh_role_from_backend()
    role = st.session_state.get("user_role")
    if not role:
        user = st.session_state.get("user")
        if isinstance(user, dict):
            role = user.get("role")
    return str(role).upper() if role else ""


def get_user_role() -> str:
    """
    Public function to get user role - used by navigation system
    """
    return _get_user_role()


def _hide_default_sidebar_nav() -> None:
    """
    NOTE: This function is deprecated when using st.navigation.
    st.navigation automatically creates its own navigation sidebar.
    We don't need to hide anything - st.navigation handles it.
    """
    # Do nothing - st.navigation creates its own navigation
    pass


def hide_sidebar_nav_immediately() -> None:
    """
    NOTE: Deprecated when using st.navigation.
    st.navigation automatically creates its own navigation sidebar.
    No need to hide anything.
    """
    # Do nothing - st.navigation handles navigation automatically
    pass


def _render_user_sidebar_nav() -> None:
    # Navigation is handled automatically by st.navigation() in app.py
    # No need to manually render navigation links
    pass


def _render_admin_sidebar_nav() -> None:
    # Navigation is handled automatically by st.navigation() in app.py
    # No need to manually render navigation links
    pass


def setup_role_access(current_file: str) -> None:
    # Note: Authentication is already checked in app.py before pages run
    # No need to call require_auth() here - it causes duplicate widget key errors
    
    # Hide default sidebar navigation IMMEDIATELY, before any role checks
    # This ensures the default nav is hidden even if role check has latency
    hide_sidebar_nav_immediately()
    
    role = _get_user_role()
    current_page = Path(current_file).name

    if role in {"ADMIN", "MANAGER"}:
        _render_admin_sidebar_nav()
        if current_page not in ADMIN_ALLOWED_PAGES and current_page != "app.py":
            st.error("Access restricted. Your role does not have access to this page.")
            st.stop()
        return

    if role != "USER":
        # For users without a recognized role, still hide default nav
        return

    _render_user_sidebar_nav()

    if current_page not in ALLOWED_USER_PAGES and current_page != "app.py":
        st.error("Access restricted. Your role does not have access to this page.")
        st.stop()

