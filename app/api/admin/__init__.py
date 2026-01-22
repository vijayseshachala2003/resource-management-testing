from fastapi import APIRouter

from app.api.admin import project_resource_allocation

router = APIRouter()

router.include_router(project_resource_allocation.router)
