# Supabase Auth Migration Report

## Current Status

✅ **Already Migrated:**
- `app/core/dependencies.py` - Uses Supabase auth via `get_user_from_token()`
- `app/core/supabase_auth.py` - Supabase client and token validation implemented
- `app/core/security.py` - All JWT code commented out
- `app/api/auth.py` - All JWT endpoints commented out
- `app/middlewares/auth.py` - Commented out
- Frontend (`streamlit_app/auth.py`) - Using Supabase auth

❌ **Still Has Issues:**

---

## Files That Need Changes

### 1. **`app/models/user.py`** ⚠️ CRITICAL
**Line 19:** `password_hash = Column(String, nullable=False)`

**Problem:** 
- Database model still requires `password_hash` field
- User creation endpoints don't set it, which will cause database errors
- With Supabase auth, passwords are managed by Supabase, not your database

**Required Changes:**
- Make `password_hash` nullable: `password_hash = Column(String, nullable=True)`
- OR remove the column entirely if you don't need to store password hashes locally
- **Recommendation:** Make it nullable first, then remove later after confirming everything works

---

### 2. **`app/api/admin/users.py`** ⚠️ CRITICAL
**Line 70-86:** `create_user()` function

**Problem:**
- Line 81: `password_hash=hash_password(payload.password)` is commented out
- But `User` model still requires `password_hash` (not nullable)
- This will cause database constraint violations when creating users

**Required Changes:**
- **Option A:** Set `password_hash` to `None` or empty string: `password_hash=None` or `password_hash=""`
- **Option B:** Remove `password` field from `UserCreate` schema (see #3)
- **Option C:** Create users in Supabase first, then sync to your DB

**Current Code:**
```python
user = User(
    email=payload.email,
    name=payload.name,
    # password_hash=hash_password(payload.password),  # ❌ Commented but model requires it
    role=UserRole(payload.role),
    ...
)
```

**Should be:**
```python
user = User(
    email=payload.email,
    name=payload.name,
    password_hash=None,  # ✅ Or remove if column is removed
    role=UserRole(payload.role),
    ...
)
```

---

### 3. **`app/schemas/user.py`** ⚠️ NEEDS UPDATE
**Lines 12-19:** `UserCreate` schema
**Lines 60-62:** `UserPasswordUpdate` schema

**Problem:**
- `UserCreate` still has `password: str` field (line 15)
- `UserPasswordUpdate` schema exists but password changes should be handled by Supabase
- These schemas don't match the new auth flow

**Required Changes:**

**For `UserCreate`:**
- **Option A:** Remove `password` field entirely (users created via Supabase)
- **Option B:** Make it optional: `password: Optional[str] = None` (if you want to support both flows temporarily)

**For `UserPasswordUpdate`:**
- **Option A:** Remove this schema entirely (password changes via Supabase)
- **Option B:** Keep it but document that it's deprecated

**Current Code:**
```python
class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str  # ❌ Remove this
    role: UserRole
    ...
```

**Should be:**
```python
class UserCreate(BaseModel):
    email: EmailStr
    name: str
    # password: str  # ❌ Removed - handled by Supabase
    role: UserRole
    ...
```

---

### 4. **`app/api/admin/bulk_uploads.py`** ⚠️ CRITICAL
**Line 110:** Active `hash_password()` call

**Problem:**
- Line 4: Import is commented out: `# from app.core.security import hash_password`
- Line 110: Still calls `hash_password()` which doesn't exist → **Will cause runtime error**
- CSV still expects `password` field (line 27)
- Creates users with `password_hash` but function doesn't exist

**Required Changes:**

**Line 4:** Remove commented import (already done, but clean up)

**Line 27:** Remove `"password"` from `USER_REQUIRED_FIELDS`:
```python
USER_REQUIRED_FIELDS = {
    "email",
    "name",
    "role",
    # "password",  # ❌ Remove - handled by Supabase
    "date_of_joining",
    "soul_id",
    "work_role",
}
```

**Line 92:** Update validation to not check password:
```python
# Already handles this: if field != "password"
# But should remove password from required fields entirely
```

**Line 110:** Remove `password_hash` assignment:
```python
insert_list.append(
    User(
        email=email,
        name=row["name"].strip(),
        # password_hash=hash_password(...),  # ❌ Remove this line
        password_hash=None,  # ✅ Or remove if column removed
        role=UserRole(row["role"]),
        ...
    )
)
```

**Line 43:** Remove `DEFAULT_PASS` constant (no longer needed)

**Note:** You'll need to create users in Supabase first, then sync to your DB, OR make password_hash nullable in the model.

---

### 5. **`app/main.py`** ⚠️ MINOR CLEANUP
**Line 6:** `from app.api import auth`
**Line 25:** `# app.include_router(auth.router)`

**Problem:**
- Importing `auth` module but not using it
- Router is commented out (good)

**Required Changes:**
- Remove the import: `# from app.api import auth` or delete the line entirely
- Keep router commented out or remove the line

---

### 6. **`app/schemas/auth.py`** ⚠️ CLEANUP
**All schemas:** `LoginRequest`, `TokenResponse`, `RefreshTokenRequest`

**Problem:**
- These schemas are for JWT-based auth
- Not used anywhere (auth endpoints commented out)
- Can be removed or kept for reference

**Required Changes:**
- **Option A:** Delete the file entirely (cleanest)
- **Option B:** Comment out or keep for reference if you might need them later
- **Recommendation:** Delete it - Supabase handles all auth schemas

---

### 7. **`app/core/security.py`** ⚠️ CLEANUP
**Entire file:** All code commented out

**Problem:**
- File exists but all code is commented
- Taking up space and causing confusion

**Required Changes:**
- **Option A:** Delete the file entirely (recommended)
- **Option B:** Keep it commented for reference
- **Recommendation:** Delete it - Supabase handles all security

---

### 8. **`app/api/auth.py`** ⚠️ CLEANUP
**Entire file:** All code commented out

**Problem:**
- File exists but all endpoints are commented
- Router not included in main.py

**Required Changes:**
- **Option A:** Delete the file entirely (recommended)
- **Option B:** Keep commented for reference
- **Recommendation:** Delete it - Supabase handles auth endpoints

---

### 9. **`app/middlewares/auth.py`** ⚠️ CLEANUP
**Entire file:** All code commented out

**Problem:**
- File exists but middleware is commented out in main.py

**Required Changes:**
- **Option A:** Delete the file entirely (recommended)
- **Option B:** Implement Supabase token validation middleware here
- **Recommendation:** Delete it - auth is handled via `get_current_user` dependency

---

## Database Migration Considerations

### **`password_hash` Column**

**Current State:**
- Column exists and is `NOT NULL`
- No values being set (will cause errors)

**Options:**

1. **Make it nullable** (safest, reversible):
   ```sql
   ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
   ```

2. **Remove it entirely** (cleanest, but requires migration):
   ```sql
   ALTER TABLE users DROP COLUMN password_hash;
   ```

3. **Set default empty string** (quick fix, but not ideal):
   ```python
   password_hash = Column(String, nullable=False, default="")
   ```

**Recommendation:** Start with Option 1 (make nullable), then remove later once everything is confirmed working.

---

## Summary of Required Changes

### Critical (Will Cause Errors):
1. ✅ `app/models/user.py` - Make `password_hash` nullable or remove
2. ✅ `app/api/admin/users.py` - Set `password_hash=None` in user creation
3. ✅ `app/api/admin/bulk_uploads.py` - Remove `hash_password()` call and password field
4. ✅ `app/schemas/user.py` - Remove `password` from `UserCreate` schema

### Cleanup (Recommended):
5. ✅ `app/main.py` - Remove unused `auth` import
6. ✅ `app/schemas/auth.py` - Delete file (or keep commented)
7. ✅ `app/core/security.py` - Delete file (or keep commented)
8. ✅ `app/api/auth.py` - Delete file (or keep commented)
9. ✅ `app/middlewares/auth.py` - Delete file (or keep commented)

### Database:
10. ✅ Run migration to make `password_hash` nullable or remove column

---

## Testing Checklist

After making changes, test:
- [ ] User creation via `/admin/users` POST endpoint
- [ ] Bulk user upload via `/admin/bulk_uploads/users` POST endpoint
- [ ] All endpoints using `get_current_user` dependency
- [ ] Frontend authentication flow
- [ ] User lookup by email (used in `get_current_user`)

---

## Notes

- Your `get_current_user()` in `dependencies.py` looks up users by email from Supabase token
- Make sure users exist in your database with matching emails
- Consider syncing Supabase users to your database automatically
- Password management is now entirely handled by Supabase

