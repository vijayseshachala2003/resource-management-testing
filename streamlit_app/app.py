import streamlit as st
from auth import require_auth
from role_guard import get_user_role
from navigation import setup_navigation

st.set_page_config(page_title="Resource Management", layout="wide")

# Check authentication
if "token" not in st.session_state:
    st.sidebar.markdown("### 🔐 Login Required")
    require_auth()
    st.rerun()

require_auth()

# Get user role
role = get_user_role()

# Show loading skeleton if role not yet determined
if not role:
    with st.sidebar:
        st.info("🔄 Loading navigation...")
    st.info("🔄 Loading your dashboard...")
    st.stop()

# Setup role-based navigation
pg = setup_navigation(role)

if pg:
    # Run the selected page
    pg.run()
