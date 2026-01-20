# app/api/admin/bulk_uploads.py
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.project import Project
from app.models.user import User, UserRole
import csv
import io

router = APIRouter(prefix="/admin/bulk_uploads", tags=["Admin - BulkUploads"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# For now kept the format for writing a CSV
# email, name, role, password, date_of_joining, soul_id, work_role
# passwork field should only contain 12345, if password field is empty then default pass 12345 will be inserted
USER_REQUIRED_FIELDS = {
        "email",
        "name",
        "role",
        "date_of_joining",
        "soul_id",
        "work_role",
    }

# For now kept the format for writing the project CSV
# code, name, is_active, start_date, end_date
PROJECT_REQUIRED_FIELDS = {
    "code",
    "name",
    "is_active",
    "start_date",
    "end_date"
}


@router.post("/list/users")
async def list_users(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    query = db.query(User)

    if active_only and active_only is True:
        query = query.filter(User.is_active == True)
    
    users = query.all()
    results = []

    for user in users:
        results.append({
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "is_active": user.is_active,
            "doj": user.doj,
            "rpm_user_id": user.rpm_user_id,
            "soul_id": user.soul_id,
            "work_role": user.work_role
        })

    return {
        "count": len(results),
        "items": results
    }

@router.post("/users")
async def bulk_upload_users(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a valid .csv file")

    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    # Validate headers
    if not USER_REQUIRED_FIELDS.issubset(reader.fieldnames):
        missing = USER_REQUIRED_FIELDS - set(reader.fieldnames)
        raise HTTPException(
            status_code=400,
            detail=f"Missing columns: {', '.join(missing)}"
        )

    # Extract emails
    emails_from_file = {
        row["email"].strip().lower()
        for row in rows
        if row.get("email")
    }

    # Fetch existing emails from the DB to check for the conflicting emails
    emails_from_db = {
        email for (email,) in
        db.query(User.email)
          .filter(User.email.in_(emails_from_file))
          .all()
    }

    insert_list = []
    error_list = []

    for line_no, row in enumerate(rows, start=2):
        # Normalize
        email = row["email"].strip().lower()

        # Empty field check
        for field in USER_REQUIRED_FIELDS:
            value = row.get(field)
            if not value or not value.strip():
                error_list.append(
                    f"Line {line_no}: '{field}' is missing"
                )
                break
            elif field == "password" and row[field].strip() != "" and row[field].strip() != DEFAULT_PASS:
                error_list.append(
                    f"Line {line_no}: '{field}' should have only value of 12345"
                )
                break
        else:
            # Duplicate email check
            if email in emails_from_db:
                error_list.append(
                    f"Line {line_no}: email '{email}' already exists"
                )
                continue

            # Create User
            insert_list.append(
                User(
                    email=email,
                    name=row["name"].strip(),
                    role=UserRole(row["role"]),
                    soul_id=row["soul_id"].strip(),
                    work_role=row["work_role"].strip(),
                    doj=row["date_of_joining"].strip(),
                    default_shift_id=None,
                )
            )

    if insert_list:
        db.bulk_save_objects(insert_list)
        db.commit()

    return {
        "inserted": len(insert_list),
        "errors": error_list,
    }

@router.post("/projects")
async def bulk_upload_projects(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a valid .csv file")

    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    # Validate headers
    if not PROJECT_REQUIRED_FIELDS.issubset(reader.fieldnames):
        missing = PROJECT_REQUIRED_FIELDS - set(reader.fieldnames)
        raise HTTPException(
            status_code=400,
            detail=f"Missing columns: {', '.join(missing)}"
        )

    # Extract codes
    codes_from_file = {
        row["code"].strip().lower()
        for row in rows
        if row.get("code")
    }

    # Fetch existing emails from the DB to check for the conflicting codes
    codes_from_db = {
        code for (code,) in
        db.query(Project.code)
          .filter(Project.code.in_(codes_from_file))
          .all()
    }
    
    insert_list = []
    error_list = []

    for line_no, row in enumerate(rows, start=2):
        # Normalize
        code = row["code"].strip().lower()

        # Empty field check
        for field in PROJECT_REQUIRED_FIELDS:
            if field != "end_date" and field != "is_active" and (not row.get(field) or not row[field].strip()):
                error_list.append(
                    f"Line {line_no}: '{field}' is missing"
                )
                break
            if field == "end_date" and row["end_date"] and row["end_date"] > row["start_date"]:
                error_list.append(
                    f"Line {line_no}: 'end_date' can't be greater than 'start_date'"
                )
                break
        else:
            # Duplicate check
            if code in codes_from_db:
                error_list.append(
                    f"Line {line_no}: email '{code}' already exists"
                )
                continue

            # Create User
            insert_list.append(
                Project(
                    code=code,
                    name=row["name"].strip(),
                    is_active=True if row["is_active"].strip() == 'TRUE' else False,
                    start_date=row["start_date"].strip(),
                    end_date=None if row["end_date"].strip() == "" else row["end_date"].strip(),
                )
            )

    if insert_list:
        db.bulk_save_objects(insert_list)
        db.commit()

    return {
        "inserted": len(insert_list),
        "errors": error_list,
    }
