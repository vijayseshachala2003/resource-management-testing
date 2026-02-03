"""
Navigation module for role-based page routing using st.navigation
"""
import streamlit as st
from pathlib import Path
import sys
import os

# Add app_pages to path
app_pages_dir = Path(__file__).parent / "app_pages"
sys.path.insert(0, str(app_pages_dir.parent))

# Page definitions with metadata - mapping file names to page configs
PAGE_CONFIGS = {
    "3_Home": {
        "file": "app_pages/3_Home.py",
        "label": "Home",
        "icon": "🏠",
        "roles": ["USER"],
    },
    "1_History": {
        "file": "app_pages/1_History.py",
        "label": "History",
        "icon": "📜",
        "roles": ["USER"],
    },
    "4_Attendance_Requests": {
        "file": "app_pages/4_Attendance_Requests.py",
        "label": "Leave/WFH Requests",
        "icon": "📅",
        "roles": ["USER"],
    },
    "2_Team_Stats": {
        "file": "app_pages/2_Team_Stats.py",
        "label": "Team Stats",
        "icon": "👥",
        "roles": ["USER"],
    },
    "7_Project_Resource_Allocation": {
        "file": "app_pages/7_Project_Resource_Allocation.py",
        "label": "Project Resource Allocation",
        "icon": "📁",
        "roles": ["ADMIN", "MANAGER"],
    },
    "user_productivity_dashboard": {
        "file": "app_pages/user_productivity_dashboard.py",
        "label": "User Productivity",
        "icon": "👤",
        "roles": ["ADMIN", "MANAGER"],
    },
    "project_productivity_dashboard": {
        "file": "app_pages/project_productivity_dashboard.py",
        "label": "Project Productivity",
        "icon": "📈",
        "roles": ["ADMIN", "MANAGER"],
    },
    "05_Reports_Center": {
        "file": "app_pages/05_Reports_Center.py",
        "label": "Reports Center",
        "icon": "📋",
        "roles": ["ADMIN", "MANAGER"],
    },
    "2_Admin_Projects": {
        "file": "app_pages/2_Admin_Projects.py",
        "label": "Admin Projects",
        "icon": "🔧",
        "roles": ["ADMIN", "MANAGER"],
    },
    "5_Approvals": {
        "file": "app_pages/5_Approvals.py",
        "label": "Timesheet Approvals",
        "icon": "🧾",
        "roles": ["ADMIN", "MANAGER"],
    },
    "6_Attendance_Approvals": {
        "file": "app_pages/6_Attendance_Approvals.py",
        "label": "Attendance Approvals",
        "icon": "📝",
        "roles": ["ADMIN", "MANAGER"],
    },
}


def get_pages_for_role(role: str) -> list:
    """
    Get list of Page objects for the given role using st.navigation format
    """
    role = role.upper() if role else ""
    
    pages = []
    for page_id, page_config in PAGE_CONFIGS.items():
        if role in page_config["roles"]:
            # Create Page object for st.navigation
            page = st.Page(
                page_config["file"],
                title=page_config["label"],
                icon=page_config["icon"],
            )
            pages.append(page)
    
    return pages


def setup_navigation(role: str):
    """
    Setup role-based navigation and return the navigation object
    """
    pages = get_pages_for_role(role)
    
    if not pages:
        # No pages available, show error
        st.error("No pages available for your role. Please contact an administrator.")
        st.stop()
        return None
    
    # Create navigation
    pg = st.navigation(pages)
    return pg
