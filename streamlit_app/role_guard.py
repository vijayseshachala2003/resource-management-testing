from pathlib import Path
import os

import requests
import streamlit as st
from auth import require_auth


ALLOWED_USER_PAGES = {
    "3_Home.py": "Home",
    "1_History.py": "History",
    "4_Attendance_Requests.py": "Attendance Requests",
    "2_Team_Stats.py": "Team Stats",
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
    """Hide Streamlit's default sidebar navigation immediately using CSS and JS"""
    # Always inject the CSS/JS on every call to ensure it works even after reruns
    st.markdown(
        """
        <style>
        /* Hide Streamlit's default sidebar navigation - multiple selectors for reliability */
        [data-testid="stSidebarNav"] { 
            display: none !important; 
            visibility: hidden !important;
            opacity: 0 !important;
            height: 0 !important;
            overflow: hidden !important;
            width: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        [data-testid="stSidebarNav"] ul,
        [data-testid="stSidebarNav"] li,
        [data-testid="stSidebarNav"] a {
            display: none !important;
        }
        nav[data-testid="stSidebarNav"] {
            display: none !important;
        }
        /* Hide any navigation elements in sidebar */
        section[data-testid="stSidebar"] > div:first-child > div:first-child nav,
        section[data-testid="stSidebar"] nav {
            display: none !important;
        }
        /* Target the nav container directly */
        div[data-testid="stSidebarNav"] {
            display: none !important;
        }
        /* Additional fallback - hide any nav in sidebar */
        section[data-testid="stSidebar"] nav,
        section[data-testid="stSidebar"] > nav {
            display: none !important;
        }
        </style>
        <script>
        // JavaScript fallback to hide navigation if CSS doesn't work fast enough
        (function() {
            function hideNav() {
                const selectors = [
                    '[data-testid="stSidebarNav"]',
                    'section[data-testid="stSidebar"] nav',
                    'section[data-testid="stSidebar"] > div:first-child nav'
                ];
                selectors.forEach(selector => {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(el => {
                        if (el) {
                            el.style.display = 'none';
                            el.style.visibility = 'hidden';
                            el.style.opacity = '0';
                            el.style.height = '0';
                            el.style.width = '0';
                            el.style.margin = '0';
                            el.style.padding = '0';
                        }
                    });
                });
            }
            // Run immediately
            hideNav();
            // Run after DOM is ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', hideNav);
            } else {
                hideNav();
            }
            // Run after short delays to catch late-rendered elements
            setTimeout(hideNav, 0);
            setTimeout(hideNav, 50);
            setTimeout(hideNav, 100);
            setTimeout(hideNav, 300);
            setTimeout(hideNav, 500);
            // Use MutationObserver to catch dynamically added elements
            if (typeof MutationObserver !== 'undefined') {
                const observer = new MutationObserver(function(mutations) {
                    hideNav();
                });
                if (document.body) {
                    observer.observe(document.body, { 
                        childList: true, 
                        subtree: true,
                        attributes: true,
                        attributeFilter: ['data-testid']
                    });
                }
            }
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


def hide_sidebar_nav_immediately() -> None:
    """Call this function at the very top of each page, before any other Streamlit calls"""
    # Always call to ensure sidebar is hidden on every rerun
    _hide_default_sidebar_nav()


def _render_user_sidebar_nav() -> None:
    st.sidebar.markdown("### Navigation")
    st.sidebar.page_link("pages/3_Home.py", label="Home")
    st.sidebar.page_link("pages/1_History.py", label="History")
    st.sidebar.page_link("pages/4_Attendance_Requests.py", label="Attendance Requests")
    st.sidebar.page_link("pages/2_Team_Stats.py", label="Team Stats")


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
    # Check authentication first - redirect to login if not authenticated
    require_auth()
    
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

