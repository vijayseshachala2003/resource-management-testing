import streamlit as st
from auth import require_auth, show_profile_section
from role_guard import get_user_role
from navigation import setup_navigation

st.set_page_config(page_title="Resource Management", layout="wide")

# Check authentication (will restore from cookie if available)
require_auth()

# If still no token after require_auth, stop here (login_ui already called and stopped)
if "token" not in st.session_state:
    st.stop()

# User is authenticated - show profile section in top right
show_profile_section()

# Get user role
role = get_user_role()

# Show loading skeleton if role not yet determined
if not role:
    st.info("🔄 Loading your dashboard...")
    st.stop()

# Setup role-based navigation
pg = setup_navigation(role)

if pg:
    # Run the selected page
    pg.run()
