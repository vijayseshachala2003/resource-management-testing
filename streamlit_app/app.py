import streamlit as st
from auth import require_auth
from role_guard import setup_role_access


st.set_page_config(page_title="Resource Management", layout="wide")
setup_role_access(__file__)

if "token" not in st.session_state:
    st.sidebar.markdown("### Navigation")
    st.sidebar.page_link("app.py", label="Login")

require_auth()

st.sidebar.success("Logged in")

st.title("User Dashboard")
st.write("Select a page from the sidebar")
