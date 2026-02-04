from dotenv import load_dotenv
import os
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

DISABLE_AUTH = os.getenv("DISABLE_AUTH", "false").lower() == "true"

# Only initialize Supabase if auth is enabled
if not DISABLE_AUTH:
    from supabase import create_client
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError(
            f"Supabase environment variables not set. "
            f"SUPABASE_URL={'set' if SUPABASE_URL else 'missing'}, "
            f"SUPABASE_ANON_KEY={'set' if SUPABASE_ANON_KEY else 'missing'}. "
            f"Checked: {streamlit_app_env} and {project_root_env}"
        )

    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
else:
    supabase = None  # Auth disabled - Supabase not needed
