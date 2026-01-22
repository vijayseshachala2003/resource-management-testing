import streamlit as st
from auth import require_auth

st.set_page_config(page_title="Resource Management", layout="wide")

require_auth()

st.sidebar.success("Logged in")

st.title("User Dashboard")
st.write("Select a page from the sidebar")
