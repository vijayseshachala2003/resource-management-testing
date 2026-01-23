import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# AUTH TOGGLE CONFIGURATION
# ============================================
# To DISABLE Supabase Auth: Set DISABLE_AUTH=true in .env
# To ENABLE Supabase Auth:  Set DISABLE_AUTH=false in .env
# Must match backend setting in app/core/dependencies.py
# ============================================
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "true").lower() == "true"

def login_ui():
    st.title("Login")
    
    if DISABLE_AUTH:
        # AUTH BYPASS MODE - No actual login required
        st.info("🔓 Auth is currently disabled - Click below to continue")
        
        if st.button("Continue (No Auth Required)"):
            # Set dummy token and user info for compatibility
            st.session_state["token"] = "bypass_token"
            st.session_state["user"] = {
                "id": "local-admin",
                "email": "admin@local.dev",
                "name": "Local Admin",
                "role": "ADMIN",
            }
            st.session_state["user_email"] = "admin@local.dev"
            st.session_state["user_id"] = "local-admin"
            st.session_state["user_name"] = "Local Admin"
            st.session_state["user_role"] = "ADMIN"
            
            st.success("Logged in successfully (Bypass Mode)")
            st.rerun()
    else:
        # SUPABASE AUTH MODE - Normal login flow
        from supabase_client import supabase
        
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
                st.session_state["user_id"] = res.user.id
                st.session_state["user_name"] = res.user.user_metadata.get("name", res.user.email)
                st.session_state["user_role"] = res.user.user_metadata.get("role", "USER")

                st.success("Logged in successfully")
                st.rerun()

            except Exception as e:
                st.error(str(e))


def require_auth():
    """
    Call this at the top of every protected page.
    """
    if DISABLE_AUTH:
        # Auto-login in bypass mode
        if "token" not in st.session_state:
            st.session_state["token"] = "bypass_token"
            st.session_state["user"] = {
                "id": "local-admin",
                "email": "admin@local.dev",
                "name": "Local Admin",
                "role": "ADMIN",
            }
            st.session_state["user_email"] = "admin@local.dev"
            st.session_state["user_id"] = "local-admin"
            st.session_state["user_name"] = "Local Admin"
            st.session_state["user_role"] = "ADMIN"
    else:
        # Normal auth check
        if "token" not in st.session_state:
            login_ui()
            st.stop()