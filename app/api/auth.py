from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])


# -------------------------
# LOGOUT
# -------------------------
@router.post("/logout")
def logout():
    """
    Logout endpoint (stateless - client deletes tokens).
    Actual logout is handled client-side by clearing Supabase session.
    """
    return {"message": "Logged out successfully"}
