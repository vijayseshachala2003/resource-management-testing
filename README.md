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
```
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
```
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

## Front end code for Approval management
- Run the script independently by running the following
```
cd attendance_preview 
streamlit run attendance_preview.py ```
```
What can Approval management features
Perfect! I've completed the attendance management system following the workflows you provided. Here's what's been implemented:

## 🎯 Complete Feature Set:

### **User Features:**
1. **Attendance Tab:**
   - Clock in/out with WFH/Onsite mode
   - Live duration tracking
   - View attendance logs with status filters (All/Pending/Approved/Rejected)
   - See shift timings and week-offs

2. **Leave Tab:**
   - Apply for Full Day or Half Day leaves
   - Date range selection (2 paid days, rest unpaid)
   - Upload proof (optional)
   - Complete leave history with filters
   - Leave balance summary

### **Admin Features:**
1. **Project Approvals Tab (Attendance):**
   - View all attendance logs with comprehensive filters (Project, User, Status, Date)
   - **Individual approval**: Select and approve/reject single entries with notes
   - **Bulk approval**: Approve/reject all pending entries at once
   - View complete attendance history

2. **Leave Approvals Tab:**
   - Filter by Project, User, Status, and Leave Type
   - Approve/reject leave requests with optional admin reason
   - View all leave requests with complete details

3. **Settings Tab:**
   - Set default shift timings (start/end time)
   - Configure week-offs (multi-select days)
   - Save and apply globally

All features follow the Keka-style workflow with proper status tracking, filtering, and approval mechanisms! 🚀
