from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middlewares.auth import auth_middleware
from app.api.admin import users, projects
from app.api.admin import shifts
from app.api import auth
from app.api.admin import projects_daily
from dotenv import load_dotenv
load_dotenv()


app = FastAPI(title="Resource Management System")

app.middleware("http")(auth_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(projects.router)
app.include_router(auth.router)
app.include_router(projects_daily.router)

from app.api.time import history
app.include_router(history.router)
from app.api import me
app.include_router(me.router)

app.include_router(shifts.router)

from app.api.admin import user_daily

app.include_router(user_daily.router)


from app.api.admin import dashboard as admin_dashboard

app.include_router(admin_dashboard.router)
from app.api.dashboard import user_history

app.include_router(user_history.router)

from app.api.attendance import requests
app.include_router(requests.router)

from app.api import attendance_daily
app.include_router(attendance_daily.router)

from app.api.admin.bulk_uploads import router as bulk_uploads_router
app.include_router(bulk_uploads_router)
