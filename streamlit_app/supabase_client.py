from supabase import create_client
import os

supabase = create_client(
    os.environ["https://duzweubcrgigcdzxihxk.supabase.co"],
    os.environ["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR1endldWJjcmdpZ2NkenhpaHhrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjgxNTQ5MjcsImV4cCI6MjA4MzczMDkyN30.7scgNfKtvVYEyaQ5mpPpEcZcKO9Bux2WWtD9E85jC5Y"]
)
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
                "password": password
            })

            st.session_state["token"] = res.session.access_token
            st.session_state["user"] = res.user
            st.success("Logged in")
            st.rerun()

        except Exception as e:
            st.error(str(e))
