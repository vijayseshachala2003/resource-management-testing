# 🔐 Supabase Auth Toggle Guide

This guide explains how to **temporarily disable** and **re-enable** Supabase authentication.

---

## 🚀 Quick Toggle

### To DISABLE Supabase Auth (Current Setting)
Add or update in your `.env` file:
```bash
DISABLE_AUTH=true
```

### To ENABLE Supabase Auth
Add or update in your `.env` file:
```bash
DISABLE_AUTH=false
```

**Important:** After changing the value, restart both:
- ✅ FastAPI backend server
- ✅ Streamlit frontend app

---

## 📋 What Happens in Each Mode

### 🔓 DISABLED Mode (`DISABLE_AUTH=true`)

**Backend:**
- ✅ No authentication required
- ✅ All API requests automatically use `admin@local.dev` user
- ✅ No Supabase connection needed
- ✅ No `SUPABASE_URL` or `SUPABASE_ANON_KEY` required

**Frontend:**
- ✅ Shows "Continue (No Auth Required)" button
- ✅ Auto-login on page load
- ✅ No email/password needed

**Use Case:** Development, testing, local development

---

### 🔒 ENABLED Mode (`DISABLE_AUTH=false`)

**Backend:**
- ✅ Requires valid Supabase JWT token in `Authorization: Bearer <token>` header
- ✅ Validates token with Supabase
- ✅ Auto-creates users in your database if they don't exist
- ✅ Requires `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `.env`

**Frontend:**
- ✅ Shows email/password login form
- ✅ Authenticates with Supabase
- ✅ Stores Supabase access token
- ✅ Requires valid Supabase credentials

**Use Case:** Production, staging, when you need real authentication

---

## 📝 Environment Variables

### Required for DISABLED Mode:
```bash
DISABLE_AUTH=true
# SUPABASE_URL and SUPABASE_ANON_KEY not needed
```

### Required for ENABLED Mode:
```bash
DISABLE_AUTH=false
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
```

---

## 🔄 Switching Between Modes

### Step 1: Update `.env` file
Change `DISABLE_AUTH` value:
- `true` = Disabled (no auth)
- `false` = Enabled (Supabase auth)

### Step 2: Restart Backend
```bash
# Stop your FastAPI server (Ctrl+C)
# Then restart it
uvicorn app.main:app --reload
```

### Step 3: Restart Frontend
```bash
# Stop your Streamlit app (Ctrl+C)
# Then restart it
streamlit run streamlit_app/app.py
```

### Step 4: Clear Browser Session (Optional)
If switching from disabled to enabled, you may want to clear your browser's session storage or refresh the page.

---

## ✅ Verification

### Check if Auth is Disabled:
- Backend: Look for "AUTH BYPASS MODE" in logs or check `app/core/dependencies.py`
- Frontend: Login page shows "Auth is currently disabled" message

### Check if Auth is Enabled:
- Backend: Requires `Authorization: Bearer <token>` header
- Frontend: Login page shows email/password input fields

---

## 🛠️ Files That Handle Auth Toggle

1. **Backend:**
   - `app/core/dependencies.py` - Main auth logic
   - `app/core/supabase_auth.py` - Supabase client initialization

2. **Frontend:**
   - `streamlit_app/auth.py` - Login UI and auth check
   - `streamlit_app/supabase_client.py` - Supabase client initialization

---

## ⚠️ Important Notes

- **Default:** Auth is **DISABLED** by default (`DISABLE_AUTH=true`)
- **Security:** Never use disabled mode in production!
- **Testing:** Disabled mode is perfect for local development and testing
- **Consistency:** Both backend and frontend read from the same `.env` file
- **Auto-provisioning:** When enabled, users are automatically created in your database on first login

---

## 🐛 Troubleshooting

### "Supabase environment variables not set"
- **Solution:** Set `DISABLE_AUTH=true` OR provide `SUPABASE_URL` and `SUPABASE_ANON_KEY`

### "Invalid Supabase token"
- **Solution:** Make sure `DISABLE_AUTH=false` and you're using a valid Supabase token

### Frontend shows login form but backend doesn't require auth
- **Solution:** Make sure both backend and frontend are reading from the same `.env` file and both are restarted

---

## 📚 Example `.env` File

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/dbname

# Auth Toggle (true = disabled, false = enabled)
DISABLE_AUTH=true

# Supabase (only needed when DISABLE_AUTH=false)
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_ANON_KEY=your-anon-key-here
```

