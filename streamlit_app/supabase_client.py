from dotenv import load_dotenv
import os

load_dotenv()

DISABLE_AUTH = os.getenv("DISABLE_AUTH", "true").lower() == "true"

# Only initialize Supabase if auth is enabled
if not DISABLE_AUTH:
    from supabase import create_client
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Supabase environment variables not set")

    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
else:
    supabase = None  # Auth disabled - Supabase not needed
