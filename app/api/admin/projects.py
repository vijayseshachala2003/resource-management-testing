from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/admin/projects", tags=["Admin - Projects"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()

@router.post("/", response_model=ProjectResponse)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        code=payload.code,
        name=payload.name,
        is_active=payload.is_active
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
from uuid import UUID
from fastapi import HTTPException

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    payload: ProjectCreate,
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.code = payload.code
    project.name = payload.name
    project.is_active = payload.is_active

    db.commit()
    db.refresh(project)
    return project
@router.delete("/{project_id}")
def deactivate_project(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.is_active = False
    db.commit()

    return {"message": "Project deactivated successfully"}
