import streamlit as st
from supabase_client import supabase

def login_ui():
    st.title("Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })

            if not res.session:
                st.error("Login failed")
                return

            # Store Supabase token
            st.session_state["token"] = res.session.access_token
            st.session_state["user"] = {
                "id": res.user.id,
                "email": res.user.email,
                "name": res.user.user_metadata.get("name"),
                "role": res.user.user_metadata.get("role", "USER"),
            }

            st.session_state["user_email"] = res.user.email

            st.success("Logged in successfully")
            st.rerun()

        except Exception as e:
            st.error(str(e))


def require_auth():
    """
    Call this at the top of every protected page.
    """
    if "token" not in st.session_state:
        login_ui()
        st.stop()