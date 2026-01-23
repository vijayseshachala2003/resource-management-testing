import os
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()

DISABLE_AUTH = os.getenv("DISABLE_AUTH", "true").lower() == "true"

# Only initialize Supabase if auth is enabled
if not DISABLE_AUTH:
    from supabase import create_client, Client
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_ANON_KEY not set")

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
else:
    supabase = None


def get_user_from_token(token: str):
    """
    Get user from Supabase token.
    Only works when DISABLE_AUTH=false
    """
    if DISABLE_AUTH:
        raise RuntimeError("Supabase auth is disabled. Set DISABLE_AUTH=false to enable.")
    
    if not supabase:
        raise RuntimeError("Supabase client not initialized")
    
    try:
        response = supabase.auth.get_user(token)

        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Supabase token",
            )

        return response.user

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supabase token",
        )
