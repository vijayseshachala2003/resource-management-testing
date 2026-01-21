🧠 Resource Management System
A full-stack Resource Management System designed to manage users, projects, attendance, productivity metrics, and dashboards with Supabase OAuth authentication, FastAPI backend, and Streamlit frontend.

🚀 Tech Stack
Backend
FastAPI – REST APIs
SQLAlchemy – ORM
PostgreSQL (Supabase) – Database
Supabase Auth – OAuth-based authentication
Pydantic – Data validation

Frontend
Streamlit – User & Admin dashboards

🔐 Authentication (Supabase OAuth)
Authentication is fully handled by Supabase
No passwords are stored in the backend database
Backend validates users using Supabase access tokens
On first login, users are auto-registered into the local users table

File Structure

resource-management/
│
├── app/                         # FastAPI Backend
│   ├── api/
│   │   ├── admin/               # Admin APIs
│   │   ├── metrics/             # User metrics & history
│   │   ├── time/                # Clock-in / Clock-out (future)
│   │   └── me.py                # Logged-in user APIs
│   │
│   ├── core/
│   │   ├── supabase_auth.py     # Supabase token verification
│   │   └── dependencies.py      # Auth & role dependencies
│   │
│   ├── models/                  # SQLAlchemy models
│   ├── schemas/                 # Pydantic schemas
│   ├── db/                      # DB setup
│   └── main.py                  # App entrypoint
│
├── streamlit_app/               # Streamlit Frontend
│   ├── app.py                   # Main entry
│   ├── auth.py                  # Supabase login
│   ├── api.py                   # API helper
│   ├── supabase_client.py       # Supabase client
│   └── pages/                   # Dashboard pages
│
├── .env                         # Environment variables
└── README.md

🗄️ Core Database Tables


🔑 Environment Variables


▶️ Running the Project
First install all the requirements then
1️⃣ Backend (FastAPI)
```
cd resource-management
python -m uvicorn app.main:app --reload
```

2️⃣ Frontend (Streamlit)
```
cd streamlit_app
streamlit run app.py
```

👥 User Flow
User signs in via Supabase OAuth
Backend verifies token
If user does not exist:
Auto-created in users table with defaults

User accesses:
Dashboard
Attendance history
Productivity metrics

🛠️ Admin Features
User CRUD
Project CRUD
Bulk uploads (CSV)
Attendance approvals
Role-based access control

🔒 Role-Based Access
Role	Permissions
ADMIN	Full access
USER	Self dashboard & history


