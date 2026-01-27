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
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "false").lower() == "true"


def _set_user_session(res):
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


def _get_query_param(name: str):
    try:
        value = st.query_params.get(name)
        if isinstance(value, list):
            return value[0] if value else None
        return value
    except Exception:
        return st.experimental_get_query_params().get(name, [None])[0]


def _clear_query_params():
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()

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

        # Handle OAuth callback (redirect back with ?code=)
        auth_code = _get_query_param("code")
        if auth_code and st.session_state.get("oauth_handled") != auth_code:
            try:
                try:
                    res = supabase.auth.exchange_code_for_session({"auth_code": auth_code})
                except TypeError:
                    res = supabase.auth.exchange_code_for_session(auth_code)

                if res and res.session:
                    _set_user_session(res)
                    st.session_state["oauth_handled"] = auth_code
                    _clear_query_params()
                    st.success("Logged in successfully")
                    st.rerun()
            except Exception as e:
                st.error(f"Google OAuth failed: {e}")

        st.subheader("Continue with Google")
        redirect_to = os.getenv("SUPABASE_REDIRECT_URL", "http://localhost:8501")
        if st.button("Continue with Google"):
            try:
                result = supabase.auth.sign_in_with_oauth({
                    "provider": "google",
                    "options": {"redirect_to": redirect_to},
                })
                url = None
                if isinstance(result, dict):
                    url = result.get("url") or (result.get("data") or {}).get("url")
                else:
                    url = getattr(result, "url", None)
                    if not url and hasattr(result, "data"):
                        url = getattr(result.data, "url", None)

                if url:
                    st.session_state["google_oauth_url"] = url
                else:
                    st.error("Could not start Google OAuth. No redirect URL returned.")
            except Exception as e:
                st.error(f"Google OAuth error: {e}")

        if st.session_state.get("google_oauth_url"):
            st.link_button(
                "Open Google Sign-In",
                st.session_state["google_oauth_url"],
            )

        st.markdown("---")

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

                _set_user_session(res)

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