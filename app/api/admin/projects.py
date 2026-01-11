from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from uuid import UUID
from datetime import date
from app.db.session import SessionLocal
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectResponse
from app.schemas.project import ProjectMemberDetail
# --- IMPORTS FOR PROJECT OWNERS (MANAGERS) ---
from app.models.project_owners import ProjectOwner
from app.schemas.project_owners import OwnerAssign, OwnerResponse
from app.models.user import User

# --- IMPORTS FOR PROJECT MEMBERS (WORKERS) ---
from app.models.project_members import ProjectMember
from app.schemas.project_members import MemberAssign, MemberResponse

router = APIRouter(prefix="/admin/projects", tags=["Admin - Projects"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
#              CORE PROJECT APIs
# ==========================================
from app.core.dependencies import get_current_user
# --- GET LIST REQUEST (With Search, Status & Date Interval) ---
@router.get("/", response_model=list[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    # 1. ADD THIS LINE: We need to know WHO is asking to find their role
    current_user: User = Depends(get_current_user), 
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    start_date_from: Optional[date] = None,
    start_date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
):
    # (Validation Logic remains the same)
    if start_date_from and start_date_to and start_date_from > start_date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'start_date_from' cannot be later than 'start_date_to'."
        )

    query = db.query(Project)

    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            or_(
                Project.name.ilike(search_fmt),
                Project.code.ilike(search_fmt)
            )
        )

    if is_active is not None:
        query = query.filter(Project.is_active == is_active)

    if start_date_from:
        query = query.filter(Project.start_date >= start_date_from)

    if start_date_to:
        query = query.filter(Project.start_date <= start_date_to)

    projects = query.offset(skip).limit(limit).all()

    # --- 2. NEW LOGIC: INJECT USER ROLES ---
    # Fetch all active project memberships for this user
    my_memberships = db.query(ProjectMember).filter(
        ProjectMember.user_id == current_user.id,
        ProjectMember.is_active == True
    ).all()
    
    # Create a lookup map: {project_id: "Role Name"}
    role_map = {m.project_id: m.work_role for m in my_memberships}

    # Attach the specific role to each project in the list
    for p in projects:
        # If user is assigned, use their role. If not, default to "Contributor"
        p.current_user_role = role_map.get(p.id, "N/A")

    return projects
# --- GET SINGLE PROJECT REQUEST ---
@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Project not found"
        )
        
    return project

# --- CREATE REQUEST ---
@router.post("/", response_model=ProjectResponse)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    # 1. Check for Duplicate Code
    existing_project = db.query(Project).filter(Project.code == payload.code).first()
    if existing_project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project with code '{payload.code}' already exists."
        )

    # 2. Validate Date Logic
    if payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be earlier than start date."
        )

    # 3. Create Project
    project = Project(
        code=payload.code,
        name=payload.name,
        is_active=payload.is_active,
        start_date=payload.start_date,
        end_date=payload.end_date
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

# --- UPDATE REQUEST ---
@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    payload: ProjectCreate,
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 1. Check for Duplicate Code (ignoring self)
    duplicate_check = db.query(Project).filter(
        Project.code == payload.code,
        Project.id != project_id
    ).first()

    if duplicate_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project with code '{payload.code}' already exists."
        )

    # 2. Validate Date Logic
    if payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be earlier than start date."
        )

    # 3. Update Fields
    project.code = payload.code
    project.name = payload.name
    project.is_active = payload.is_active
    project.start_date = payload.start_date
    project.end_date = payload.end_date

    db.commit()
    db.refresh(project)
    return project

# --- DELETE REQUEST ---
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


# ==========================================
#      PROJECT OWNERS (MANAGERS) APIs
# ==========================================

# --- ASSIGN OWNER (PM/APM) ---
@router.post("/{project_id}/owners", response_model=OwnerResponse)
def assign_owner(
    project_id: UUID, 
    payload: OwnerAssign, 
    db: Session = Depends(get_db)
):
    # 1. Verify Project Exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Verify User Exists
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 3. Check for Duplicates (Can't assign same PM twice)
    existing = db.query(ProjectOwner).filter(
        ProjectOwner.project_id == project_id,
        ProjectOwner.user_id == payload.user_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User is already an owner of this project")

    # 4. Create Assignment
    owner = ProjectOwner(
        project_id=project_id,
        user_id=payload.user_id,
        work_role=payload.work_role
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    
    # 5. Attach name for the response (UI friendly)
    owner.user_name = user.name
    return owner


# --- LIST OWNERS ---
@router.get("/{project_id}/owners", response_model=list[OwnerResponse])
def list_project_owners(
    project_id: UUID, 
    db: Session = Depends(get_db)
):
    owners = db.query(ProjectOwner).filter(
        ProjectOwner.project_id == project_id
    ).all()
    
    results = []
    for o in owners:
        # Attach user name if user exists
        o.user_name = o.user.name if o.user else "Unknown"
        results.append(o)
        
    return results


# --- REMOVE OWNER ---
@router.delete("/{project_id}/owners/{user_id}")
def remove_project_owner(
    project_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db)
):
    owner = db.query(ProjectOwner).filter(
        ProjectOwner.project_id == project_id,
        ProjectOwner.user_id == user_id
    ).first()

    if not owner:
        raise HTTPException(status_code=404, detail="Owner assignment not found")

    db.delete(owner)
    db.commit()

    return {"message": "Owner removed successfully"}


# ==========================================
#      PROJECT MEMBERS (WORKERS) APIs
# ==========================================

# --- ASSIGN MEMBER ---
@router.post("/{project_id}/members", response_model=MemberResponse)
def assign_member(
    project_id: UUID, 
    payload: MemberAssign, 
    db: Session = Depends(get_db)
):
    # 1. Verify Project Exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Verify User Exists
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 3. Check for Duplicate Active Assignment
    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == payload.user_id,
        ProjectMember.is_active == True
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User is already active on this project")

    # 4. Create Assignment
    member = ProjectMember(
        project_id=project_id,
        user_id=payload.user_id,
        work_role=payload.work_role,
        assigned_from=payload.assigned_from,
        assigned_to=payload.assigned_to,
        is_active=True
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    
    # 5. Attach name
    member.user_name = user.name
    return member


# --- LIST MEMBERS ---

@router.get("/{project_id}/members", response_model=list[ProjectMemberDetail])
def list_project_members(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Returns a list of all users assigned to this project, 
    including their Name, Email, Role, and Active Status.
    """
    # Join ProjectMember table with User table to get the names
    results = db.query(ProjectMember, User).join(
        User, ProjectMember.user_id == User.id
    ).filter(
        ProjectMember.project_id == project_id
    ).all()

    members_list = []
    for member, user in results:
        members_list.append(ProjectMemberDetail(
            user_id=user.id,
            name=user.name,
            email=user.email,
            work_role=member.work_role,
            is_active=member.is_active,
            assigned_from=member.assigned_from,
            assigned_to=member.assigned_to
        ))
    
    return members_list