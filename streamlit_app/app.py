import streamlit as st
# from auth import require_auth as old_auth
from supabase_client import require_auth as supabase_auth

st.set_page_config(page_title="Resource Management", layout="wide")

supabase_auth()

st.sidebar.success("Logged in")

st.title("User Dashboard")
st.write("Select a page from the sidebar")
