import streamlit as st
import os
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
streamlit_app_env = Path(__file__).parent / ".env"
project_root_env = Path(__file__).parent.parent / ".env"

if streamlit_app_env.exists():
    load_dotenv(dotenv_path=streamlit_app_env)
elif project_root_env.exists():
    load_dotenv(dotenv_path=project_root_env)
else:
    load_dotenv()

DISABLE_AUTH = os.getenv("DISABLE_AUTH", "false").lower() == "true"


def _hide_sidebar():
    """Hide the sidebar using CSS."""
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] { display: none; }
            [data-testid="stSidebarNav"] { display: none; }
            section[data-testid="stSidebar"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True
    )


def _sync_role_from_backend(token: str):
    """Sync user role from backend after OAuth login."""
    api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{api_base_url}/me/", headers=headers, timeout=5)
        if response.status_code == 200:
            user_data = response.json()
            st.session_state["user"] = user_data
            st.session_state["user_email"] = user_data.get("email", st.session_state.get("user_email"))
            st.session_state["user_id"] = user_data.get("id", st.session_state.get("user_id"))
            st.session_state["user_name"] = user_data.get("name", st.session_state.get("user_name"))
            st.session_state["user_role"] = user_data.get("role", "USER")
            return True
        elif response.status_code == 403:
            st.session_state["_auth_error"] = "Access denied. Your email is not registered in the system."
            return False
        else:
            return False
    except Exception:
        return False


def show_profile_section():
    """Display profile icon in top right with dropdown."""
    if "token" not in st.session_state:
        return

    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            width: 240px !important;
            min-width: 240px !important;
        }
        section[data-testid="stSidebar"] > div {
            padding-top: 0.5rem;
        }
        section[data-testid="stSidebar"] button {
            padding: 0.25rem 0.5rem;
            font-size: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    user_name = st.session_state.get("user_name", "User") or "User"
    user_email = st.session_state.get("user_email", "")
    user_role = st.session_state.get("user_role", "USER")
    avatar_url = st.session_state.get("user_avatar")
    first_letter = (user_name[0] if user_name else "U").upper()
    
    if avatar_url:
        avatar_small = f'<img src="{avatar_url}" style="width:36px;height:36px;border-radius:50%;object-fit:cover;">'
        avatar_large = f'<img src="{avatar_url}" style="width:70px;height:70px;border-radius:50%;object-fit:cover;margin:0 auto 10px;">'
    else:
        avatar_small = f'<div style="width:36px;height:36px;border-radius:50%;background:#4285f4;color:white;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:16px;">{first_letter}</div>'
        avatar_large = f'<div style="width:70px;height:70px;border-radius:50%;background:linear-gradient(135deg,#4285f4,#34a853);color:white;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:28px;margin:0 auto 10px;">{first_letter}</div>'
    
    st.markdown(
        f"""
        <style>
        .profile-wrapper {{ position: fixed; top: 10px; right: 60px; z-index: 1000000; }}
        .profile-btn {{ width: 36px; height: 36px; border-radius: 50%; border: none; padding: 0; cursor: pointer; background: transparent; }}
        .profile-btn:hover {{ box-shadow: 0 1px 3px rgba(0,0,0,0.3); }}
        .profile-dropdown {{ display: none; position: absolute; top: 45px; right: 0; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); min-width: 280px; padding: 20px; z-index: 1000001; }}
        .profile-wrapper:hover .profile-dropdown {{ display: block; }}
        .profile-dropdown-name {{ font-size: 16px; font-weight: 600; color: #202124; margin-bottom: 4px; text-align: center; }}
        .profile-dropdown-email {{ font-size: 13px; color: #5f6368; margin-bottom: 8px; text-align: center; }}
        .profile-dropdown-role {{ display: inline-block; background: #e8f0fe; color: #1967d2; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500; }}
        </style>
        <div class="profile-wrapper">
            <button class="profile-btn">{avatar_small}</button>
            <div class="profile-dropdown">
                <div style="text-align:center;">{avatar_large}</div>
                <div class="profile-dropdown-name">{user_name}</div>
                <div class="profile-dropdown-email">{user_email}</div>
                <div style="text-align:center;"><span class="profile-dropdown-role">{user_role}</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    with st.sidebar:
        if st.button("🚪 Sign out", key="logout_btn", use_container_width=True):
            logout()
        st.markdown("---")


def logout():
    """Log out the user."""
    st.session_state.clear()
    st.rerun()


def login_ui():
    """Show login page with Google OAuth."""
    _hide_sidebar()

    st.markdown(
        """
        <style>
        .login-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 6px;
            color: #f8fafc;
        }
        .login-subtitle {
            font-size: 14px;
            color: #cbd5e1;
            margin-bottom: 18px;
        }
        .login-meta {
            font-size: 12px;
            color: #94a3b8;
            margin-top: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="login-title">Sign in</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">Use your Google account to continue.</div>', unsafe_allow_html=True)

    # Show auth errors if any
    if st.session_state.get("_auth_error"):
        st.error(st.session_state["_auth_error"])
        st.info("Please contact an administrator to get access.")
        del st.session_state["_auth_error"]

    # Check for error in URL
    error = st.query_params.get("error")
    if error:
        error_desc = st.query_params.get("error_description", "Unknown error")
        st.warning(error_desc)
        st.query_params.clear()

    if DISABLE_AUTH:
        st.info("Auth is disabled. Continue to the app.")
        if st.button("Continue", use_container_width=True, type="primary"):
            st.session_state["token"] = "bypass_token"
            st.session_state["user_email"] = "admin@local.dev"
            st.session_state["user_id"] = "local-admin"
            st.session_state["user_name"] = "Local Admin"
            st.session_state["user_role"] = "ADMIN"
            st.rerun()
        return

    from supabase_client import supabase

    # Handle OAuth callback with code
    code = st.query_params.get("code")
    if code:
        try:
            res = supabase.auth.exchange_code_for_session({"auth_code": code})

            if res and res.session:
                token = res.session.access_token

                # Store basic info from Supabase
                st.session_state["token"] = token
                st.session_state["user_email"] = res.user.email
                st.session_state["user_id"] = res.user.id
                st.session_state["user_name"] = res.user.user_metadata.get("name", "")
                st.session_state["user_avatar"] = res.user.user_metadata.get("avatar_url") or res.user.user_metadata.get("picture")

                # Sync role from backend
                if _sync_role_from_backend(token):
                    st.query_params.clear()
                    st.rerun()
                else:
                    # User not authorized - clear everything
                    st.session_state.clear()
                    st.query_params.clear()
                    st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")
            st.info("Please try clicking the login button again.")
            st.query_params.clear()
        return

    redirect_to = os.getenv("SUPABASE_REDIRECT_URL", "http://localhost:8501")

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
            # Store URL in session state for the button to use
            st.session_state["_oauth_url"] = url
        else:
            st.error("Could not generate login URL")
    except Exception as e:
        st.error(f"OAuth error: {e}")

    # Show login button that redirects in same tab
    if st.button("Continue with Google", use_container_width=True, type="primary"):
        if "_oauth_url" in st.session_state:
            # Use meta refresh to redirect in same window
            st.markdown(
                f'<meta http-equiv="refresh" content="0;url={st.session_state["_oauth_url"]}">',
                unsafe_allow_html=True
            )

    st.markdown('<div class="login-meta">Need access? Contact your administrator.</div>', unsafe_allow_html=True)


def require_auth():
    """Check authentication. Call at top of every page."""
    if DISABLE_AUTH:
        if "token" not in st.session_state:
            st.session_state["token"] = "bypass_token"
            st.session_state["user_email"] = "admin@local.dev"
            st.session_state["user_id"] = "local-admin"
            st.session_state["user_name"] = "Local Admin"
            st.session_state["user_role"] = "ADMIN"
    else:
        if "token" not in st.session_state:
            login_ui()
            st.stop()
