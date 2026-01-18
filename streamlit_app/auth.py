import streamlit as st
from api import api_request

def login_ui():
    st.title("Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            data = api_request(
                "POST",
                # "/auth/login",
                json={"email": email, "password": password},
            )
            st.session_state["token"] = data["access_token"]
            st.session_state["user_id"] = data.get("user_id")
            st.session_state["user_name"] = data.get("user_name")
            st.session_state["user_email"] = data.get("user_email")
            st.session_state["user_role"] = data.get("user_role")
            st.success("Logged in successfully")
            st.rerun()
        except Exception as e:
            st.error(str(e))


def require_auth():
    if "token" not in st.session_state:
        login_ui()
        st.stop()
