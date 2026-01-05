from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middlewares.auth import auth_middleware
from app.api.admin import users, projects
from app.api import auth

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
