# JWT to Supabase OAuth Migration Checklist

This document lists all the JWT-based authentication components that need to be removed/scrapped before implementing Supabase OAuth.

## Files to Remove/Modify

### 1. **Core Security Module** (`app/core/security.py`)
**Status:** ❌ REMOVE ENTIRE FILE (or heavily modify)

**Contains:**
- `SECRET_KEY` - JWT secret key (no longer needed)
- `ALGORITHM` - JWT algorithm (no longer needed)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - JWT expiration (no longer needed)
- `REFRESH_TOKEN_EXPIRE_DAYS` - JWT refresh token expiration (no longer needed)
- `pwd_context` - Passlib CryptContext for password hashing
- `hash_password()` - Password hashing function (Supabase handles this)
- `verify_password()` - Password verification function (Supabase handles this)
- `create_access_token()` - JWT token creation (Supabase handles this)
- `create_refresh_token()` - JWT refresh token creation (Supabase handles this)
- `decode_access_token()` - JWT token decoding (Supabase handles this)
- `decode_token()` - JWT token decoding helper (Supabase handles this)

**Action:** Delete this file entirely or keep only utility functions that don't relate to auth.

---

### 2. **Auth API Endpoints** (`app/api/auth.py`)
**Status:** ❌ REMOVE/MODIFY SIGNIFICANTLY

**Current endpoints to remove:**
- `POST /auth/login` - Email/password login (Supabase handles OAuth)
- `POST /auth/refresh` - JWT refresh token endpoint (Supabase handles this)
- `POST /auth/logout` - Logout endpoint (may keep but modify for Supabase)

**Dependencies to remove:**
- `verify_password` import
- `create_access_token` import
- `create_refresh_token` import
- `decode_token` import
- `LoginRequest` schema (email/password login)
- `TokenResponse` schema (JWT tokens)
- `RefreshTokenRequest` schema (JWT refresh tokens)

**Action:** Replace with Supabase OAuth callback handlers or remove entirely if using Supabase client-side auth.

---

### 3. **Auth Middleware** (`app/middlewares/auth.py`)
**Status:** ⚠️ MODIFY COMPLETELY

**Current state:**
- Currently a placeholder that doesn't validate JWT
- Needs to be replaced with Supabase token validation

**Action:** Rewrite to validate Supabase access tokens instead of JWT.

---

### 4. **Dependencies Module** (`app/core/dependencies.py`)
**Status:** ⚠️ MODIFY SIGNIFICANTLY

**Components to remove:**
- `OAuth2PasswordBearer` from fastapi.security (JWT-specific)
- `oauth2_scheme` instance
- `get_current_user()` function - Uses JWT token decoding
- `decode_access_token` import
- `SECRET_KEY` and `ALGORITHM` imports

**Action:** Replace `get_current_user()` with Supabase user extraction from Supabase tokens.

---

### 5. **Auth Schemas** (`app/schemas/auth.py`)
**Status:** ❌ REMOVE/MODIFY

**Schemas to remove:**
- `LoginRequest` - Email/password login (not needed for OAuth)
- `TokenResponse` - JWT token response (Supabase has its own format)
- `RefreshTokenRequest` - JWT refresh token (Supabase handles this)

**Action:** Replace with Supabase-specific schemas or remove if using Supabase client SDK.

---

### 6. **User Model** (`app/models/user.py`)
**Status:** ⚠️ MODIFY

**Field to consider removing:**
- `password_hash` column - If Supabase handles user management, this may not be needed

**Action:** Decide if you want to keep user data in your DB or rely entirely on Supabase Auth. If keeping, you may want to remove `password_hash` and sync with Supabase user IDs.

---

### 7. **User Management Endpoints** (`app/api/admin/users.py`)
**Status:** ⚠️ MODIFY

**Remove:**
- `hash_password` import (line 171)
- Password hashing when creating users (if Supabase manages users)

**Action:** Modify user creation to work with Supabase user management or remove password-related fields.

---

### 8. **User Profile Endpoints** (`app/api/me.py`)
**Status:** ⚠️ MODIFY

**Remove:**
- `verify_password` import
- `hash_password` import
- `change_password()` endpoint - Password changes handled by Supabase

**Modify:**
- `get_me()` - Update to get user from Supabase instead of JWT token

**Action:** Remove password change endpoint, update user retrieval to use Supabase.

---

### 9. **Bulk Uploads** (`app/api/admin/bulk_uploads.py`)
**Status:** ⚠️ CHECK AND MODIFY

**Remove:**
- `hash_password` import (if used for user creation)

**Action:** Review and remove password hashing if creating users via bulk upload.

---

### 10. **Streamlit Auth** (`streamlit_app/auth.py`)
**Status:** ⚠️ MODIFY COMPLETELY

**Current implementation:**
- Uses `/auth/login` endpoint with email/password
- Stores JWT token in session state

**Action:** Replace with Supabase OAuth flow in Streamlit. Use Supabase Python client for authentication.

---

### 11. **Main Application** (`app/main.py`)
**Status:** ⚠️ MODIFY

**Current:**
- Includes `auth.router` (line 25)
- Uses `auth_middleware` (line 14)

**Action:** 
- Update auth router inclusion (may remove or modify)
- Update middleware to use Supabase token validation

---

## Dependencies to Remove from `requirements.txt`

After migration, you can remove:
- `python-jose` - JWT library (Supabase handles tokens)
- `passlib[bcrypt]` - Password hashing (Supabase handles this)

**Keep:**
- `fastapi` - Still needed
- `sqlalchemy` - Still needed for DB
- `psycopg2-binary` - Still needed for PostgreSQL
- `python-dotenv` - Still needed for env vars
- `pydantic` - Still needed for schemas

**Add:**
- `supabase` - Supabase Python client library

---

## Files Using `get_current_user` Dependency

These files use `get_current_user` and will need updates:
1. `app/api/attendance/requests.py`
2. `app/api/admin/attendance_requests.py`
3. `app/api/time/history.py`
4. `app/api/admin/projects.py`
5. `app/api/admin/dashboard.py`
6. `app/api/dashboard/user_history.py`
7. `app/api/me.py`

**Action:** Update `get_current_user` in `app/core/dependencies.py` to extract user from Supabase token, then all these files will automatically work with the new auth.

---

## Summary

### Complete Removal:
- ✅ `app/core/security.py` - Entire JWT/password hashing logic
- ✅ JWT-related schemas in `app/schemas/auth.py`
- ✅ Login/refresh endpoints in `app/api/auth.py`

### Major Modifications:
- ⚠️ `app/core/dependencies.py` - Replace JWT validation with Supabase
- ⚠️ `app/middlewares/auth.py` - Replace with Supabase token validation
- ⚠️ `app/api/me.py` - Remove password change, update user retrieval
- ⚠️ `app/api/admin/users.py` - Remove password hashing
- ⚠️ `streamlit_app/auth.py` - Replace with Supabase OAuth

### Database Considerations:
- Consider removing `password_hash` column from `users` table
- Consider syncing user IDs with Supabase Auth user IDs
- Decide if you want to keep user data in your DB or rely entirely on Supabase

---

## Next Steps After Removal

1. Install Supabase client: `pip install supabase`
2. Set up Supabase environment variables
3. Create new Supabase auth middleware
4. Update `get_current_user` to use Supabase tokens
5. Update Streamlit app to use Supabase OAuth
6. Test all protected endpoints

