# How to Sync Database Users to Supabase Auth

If a user exists in your PostgreSQL database but can't login, it means they don't have a Supabase Auth account yet. Here are two ways to fix this:

## Option 1: Manual Creation (Easiest - Recommended)

1. Go to your Supabase Dashboard: https://app.supabase.com
2. Select your project
3. Navigate to **Authentication** → **Users**
4. Click **"Add user"** → **"Create new user"**
5. Enter:
   - **Email**: `harsh3@example.com` (or the user's email)
   - **Password**: Set a temporary password
   - **Auto Confirm User**: ✅ Check this box (so they can login immediately)
6. Click **"Create user"**
7. The user can now login with their email and the password you set

## Option 2: Using API Endpoint (Requires Service Role Key)

If you have `SUPABASE_SERVICE_ROLE_KEY` in your backend `.env` file, you can use the API endpoint:

### Step 1: Add Service Role Key to Backend .env

Add this to `resource-management/.env`:
```
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
```

You can find your Service Role Key in Supabase Dashboard → Settings → API → `service_role` key (⚠️ Keep this secret!)

### Step 2: Call the API Endpoint

**Endpoint:** `POST /admin/users/{user_id}/create-supabase-account?password=TempPassword123`

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/admin/users/6748f6b9-16dc-4659-97b5-31f34020ec29/create-supabase-account?password=TempPassword123" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Example using Python:**
```python
import requests

user_id = "6748f6b9-16dc-4659-97b5-31f34020ec29"
password = "TempPassword123"
token = "YOUR_ADMIN_TOKEN"

response = requests.post(
    f"http://localhost:8000/admin/users/{user_id}/create-supabase-account",
    params={"password": password},
    headers={"Authorization": f"Bearer {token}"}
)

print(response.json())
```

## After Creating the Account

Once the user has a Supabase account:
- They can login with **email/password** using the password you set
- They can also use **Google OAuth** if they use the same email
- They should change their password after first login (if you set a temporary one)

## Troubleshooting

**Error: "User already exists in Supabase"**
- The user already has a Supabase account
- They can login directly - no action needed

**Error: "SUPABASE_SERVICE_ROLE_KEY not configured"**
- Use Option 1 (Manual Creation) instead
- Or add the service role key to your `.env` file

**Error: "Invalid credentials" after creating account**
- Make sure you set the password correctly
- Check that email matches exactly (case-sensitive)
- Try resetting password in Supabase dashboard
