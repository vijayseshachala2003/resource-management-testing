import streamlit as st
import os
import requests
from dotenv import load_dotenv
from pathlib import Path

# Try to load .env from streamlit_app directory first, then fallback to project root
streamlit_app_env = Path(__file__).parent / ".env"
project_root_env = Path(__file__).parent.parent / ".env"

# Load from streamlit_app/.env if it exists, otherwise try project root
if streamlit_app_env.exists():
    load_dotenv(dotenv_path=streamlit_app_env)
elif project_root_env.exists():
    load_dotenv(dotenv_path=project_root_env)
else:
    # Fallback to default behavior
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


def _sync_role_from_backend() -> None:
    token = st.session_state.get("token")
    if not token:
        return
    api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{api_base_url}/me/", headers=headers, timeout=5)
        if response.status_code >= 400:
            return
        user = response.json()
    except Exception:
        return

    if isinstance(user, dict):
        st.session_state["user"] = user
        st.session_state["user_role"] = user.get("role", st.session_state.get("user_role"))
        if user.get("name"):
            st.session_state["user_name"] = user.get("name")


def _redirect_after_login():
    role = str(st.session_state.get("user_role", "")).upper()
    if role == "USER":
        st.switch_page("pages/3_Home.py")
    if role in {"ADMIN", "MANAGER"}:
        st.switch_page("pages/7_Project_Resource_Allocation.py")


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
                    _sync_role_from_backend()
                    st.session_state["oauth_handled"] = auth_code
                    _clear_query_params()
                    st.success("Logged in successfully")
                    _redirect_after_login()
            except Exception as e:
                st.error(f"Google OAuth failed: {e}")

        st.subheader("🔵 Continue with Google")
        st.caption("Quick sign-in with your Google account. Works alongside email/password authentication.")
        redirect_to = os.getenv("SUPABASE_REDIRECT_URL", "http://localhost:8501")
        if "google_oauth_url" not in st.session_state:
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
            except Exception as e:
                st.error(f"Google OAuth error: {e}")

        if st.session_state.get("google_oauth_url"):
            st.link_button("Login with Google", st.session_state["google_oauth_url"])
        else:
            st.button("Login with Google", disabled=True)

        st.markdown("---")
        
        # Create tabs for Login and Sign Up
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])
        
        with tab1:
            st.markdown("### Email/Password Login")
            st.caption("💡 **Note:** Both Google OAuth and Email/Password authentication work together. Use whichever method you prefer.")

            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")

            if st.button("Login", key="login_btn"):
                if not email or not password:
                    st.error("Please enter both email and password")
                    return
                
                # Try Supabase first, then fallback to backend database auth
                login_success = False
                error_msg = ""
                
                # Try Supabase authentication
                try:
                    res = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password,
                    })

                    if res.session:
                        _set_user_session(res)
                        st.success("✅ Logged in successfully (Supabase)")
                        login_success = True
                        _redirect_after_login()
                except Exception as e:
                    error_msg = str(e)
                    # Supabase failed, try backend database auth
                    try:
                        import requests
                        from dotenv import load_dotenv
                        
                        load_dotenv()
                        api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
                        
                        response = requests.post(
                            f"{api_base_url}/auth/login",
                            json={"email": email, "password": password},
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            # Set session with backend token
                            st.session_state["token"] = data["access_token"]
                            st.session_state["user"] = {
                                "id": data["user_id"],
                                "email": data["user_email"],
                                "name": data["user_name"],
                                "role": data["user_role"],
                            }
                            st.session_state["user_email"] = data["user_email"]
                            st.session_state["user_id"] = data["user_id"]
                            st.session_state["user_name"] = data["user_name"]
                            st.session_state["user_role"] = data["user_role"]
                            
                            auth_method = data.get("auth_method", "database")
                            st.success(f"✅ Logged in successfully ({auth_method})")
                            login_success = True
                            _redirect_after_login()
                        else:
                            error_data = response.json() if response.content else {}
                            error_msg = error_data.get("detail", "Login failed")
                    except requests.exceptions.RequestException:
                        # Backend not available or network error
                        pass
                    except Exception as backend_error:
                        # Backend auth also failed
                        pass
                
                # If both methods failed, show error
                if not login_success:
                    if "Invalid login credentials" in error_msg or "invalid" in error_msg.lower() or "Invalid email or password" in error_msg:
                        st.error("❌ Invalid email or password. Please check your credentials.")
                        st.info("💡 **Tip:** This account might use Supabase or Database authentication. Try both methods or contact an administrator.")
                    elif "Email not confirmed" in error_msg:
                        st.error("❌ Please verify your email address before logging in. Check your inbox for the confirmation email.")
                    elif "Too many requests" in error_msg:
                        st.error("❌ Too many login attempts. Please wait a few minutes and try again.")
                    else:
                        st.error(f"Login error: {error_msg}")
        
        with tab2:
            st.markdown("### Create New Account")
            st.caption("💡 **Note:** You can also sign up using Google OAuth above, or create an account here with email/password.")

            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input("Password", type="password", key="signup_password")
            signup_confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm_password")
            signup_name = st.text_input("Full Name (Optional)", key="signup_name")

            if st.button("Sign Up", key="signup_btn"):
                if not signup_email or not signup_password:
                    st.error("Please enter both email and password")
                    return
                
                if signup_password != signup_confirm_password:
                    st.error("❌ Passwords do not match. Please try again.")
                    return
                
                if len(signup_password) < 6:
                    st.error("❌ Password must be at least 6 characters long.")
                    return
                    
                try:
                    signup_data = {
                        "email": signup_email,
                        "password": signup_password,
                    }
                    
                    # Add name to metadata if provided
                    if signup_name:
                        signup_data["options"] = {
                            "data": {
                                "name": signup_name,
                                "role": "USER"  # Default role for new users
                            }
                        }
                    
                    res = supabase.auth.sign_up(signup_data)

                    if not res.user:
                        st.error("Sign up failed: No user created")
                        return

                    # Check if email confirmation is required
                    if res.session:
                        # Email confirmation not required - auto login
                        _set_user_session(res)
                        st.success("✅ Account created successfully! Logged in.")
                        _redirect_after_login()
                    else:
                        # Email confirmation required
                        st.success("✅ Account created successfully!")
                        st.info("📧 **Please check your email to verify your account before logging in.**")
                        st.info("Once verified, you can use the 'Login' tab to sign in.")

                except Exception as e:
                    error_msg = str(e)
                    if "User already registered" in error_msg or "already exists" in error_msg.lower():
                        st.error("❌ An account with this email already exists. Please use the 'Login' tab instead.")
                    elif "Password should be at least" in error_msg:
                        st.error(f"❌ {error_msg}")
                    elif "Invalid email" in error_msg:
                        st.error("❌ Please enter a valid email address.")
                    else:
                        st.error(f"Sign up error: {error_msg}")


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