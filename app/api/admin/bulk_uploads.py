# app/api/admin/bulk_uploads.py
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.dependencies import get_current_user
from app.models.project import Project
from app.models.user import User, UserRole
from app.models.user_quality import UserQuality, QualityRating
from app.models.project_members import ProjectMember
import csv
import io
from datetime import datetime, timedelta

router = APIRouter(prefix="/admin/bulk_uploads", tags=["Admin - BulkUploads"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# For now kept the format for writing a CSV
# email, name, role, date_of_joining, soul_id, work_role
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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a valid .csv file")

    content = file.file.read().decode("utf-8-sig")  # utf-8-sig automatically strips BOM if present
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")
   
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV headers / column names are missing")

    # Validate headers
    if not (USER_REQUIRED_FIELDS == set(reader.fieldnames)):
        missing = USER_REQUIRED_FIELDS - set(reader.fieldnames)
        extra = set(reader.fieldnames) - USER_REQUIRED_FIELDS
         
        detail = {
            "missing": 0 if not missing else f"count: {len(missing)}; {', '.join(missing)}",
            "extra": 0 if not extra else f"count: {len(extra)}; {', '.join(extra)}"
        }

        raise HTTPException(
            status_code=400,
            detail=detail
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
        # Check the size of the row: should have exactly 6 entries
        if not (6 == len(row)):
            error_list.append(
                f"Line {line_no}: 'row' should have exactly 6 values"
            )
            continue

        # Normalize
        email = row["email"].strip().lower()
        
        # Empty field check
        for field in USER_REQUIRED_FIELDS:
            value = row.get(field)
            if not value or not value.strip():
                error_list.append(
                    f"Line {line_no}: '{field}' is missing or 'row' has less than 6 values"
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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a valid .csv file")

    content = file.file.read().decode("utf-8-sig")  # utf-8-sig automatically strips BOM if present
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV headers / column names are missing")

    if not (PROJECT_REQUIRED_FIELDS == set(reader.fieldnames)):
        missing = PROJECT_REQUIRED_FIELDS - set(reader.fieldnames)
        extra = set(reader.fieldnames) - PROJECT_REQUIRED_FIELDS
         
        detail = {
            "missing": 0 if not missing else f"count: {len(missing)}; {', '.join(missing)}",
            "extra": 0 if not extra else f"count: {len(extra)}; {', '.join(extra)}"
        }

        raise HTTPException(
            status_code=400,
            detail=detail
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
        # Skip empty rows (rows where all fields are empty or whitespace)
        if not row or all(not str(value).strip() if value else True for value in row.values()):
            continue
        
        # Check the size of the row: should have exactly 5 entries
        if not (5 == len(row)):
            error_list.append(
                f"Line {line_no}: 'row' should have exactly 5 values"
            )
            continue

        # Normalize
        code = row.get("code", "").strip().lower()
        
        # Skip if code is empty (empty row)
        if not code:
            continue

        # Track validation errors for this row
        row_errors = []
        
        # Empty field check
        for field in PROJECT_REQUIRED_FIELDS:
            if field != "end_date" and field != "is_active" and (not row.get(field) or not row[field].strip()):
                row_errors.append(
                    f"Line {line_no}: '{field}' is missing or 'row' has less than 5 values"
                )
                break
        
        # Validate dates separately (after field checks)
        start_date_str = row.get("start_date", "").strip() if row.get("start_date") else ""
        end_date_str = row.get("end_date", "").strip() if row.get("end_date") else ""
        
        # Validate start_date format (must be YYYY-MM-DD)
        start_date = None
        if start_date_str:
            try:
                from datetime import datetime
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                row_errors.append(
                    f"Line {line_no}: Invalid 'start_date' format '{start_date_str}'. Use YYYY-MM-DD format (e.g., 2024-01-15)"
                )
        else:
            row_errors.append(
                f"Line {line_no}: 'start_date' is required and cannot be empty"
            )
        
        # Validate end_date format (can be empty, but if provided must be YYYY-MM-DD)
        end_date = None
        if end_date_str:
            try:
                from datetime import datetime
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                row_errors.append(
                    f"Line {line_no}: Invalid 'end_date' format '{end_date_str}'. Use YYYY-MM-DD format (e.g., 2024-12-31) or leave empty"
                )
        
        # Validate date relationship: end_date should be >= start_date (if both are valid)
        if start_date and end_date and end_date < start_date:
            row_errors.append(
                f"Line {line_no}: 'end_date' ({end_date_str}) cannot be earlier than 'start_date' ({start_date_str})"
            )
        
        # If there are validation errors, add them and skip this row
        if row_errors:
            error_list.extend(row_errors)
            continue
        
        # Duplicate check
        if code in codes_from_db:
            error_list.append(
                f"Line {line_no}: Project code '{code}' already exists"
            )
            continue

        # Create Project (use parsed date objects)
        insert_list.append(
            Project(
                code=code,
                name=row["name"].strip(),
                is_active=True if row["is_active"].strip().upper() in ['TRUE', '1', 'YES'] else False,
                start_date=start_date,  # Use parsed date object
                end_date=end_date if end_date_str else None,  # Use parsed date object or None
            )
        )

    if insert_list:
        db.bulk_save_objects(insert_list)
        db.commit()

    return {
        "inserted": len(insert_list),
        "errors": error_list,
    }

# Quality assessment CSV format:
# user_email, project_code, metric_date, rating, quality_score (optional), work_role (optional), notes (optional)
QUALITY_REQUIRED_FIELDS = {
    "user_email",
    "project_code",
    "metric_date",
    "rating",
}

@router.post("/quality")
async def bulk_upload_quality(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk upload quality assessments from CSV file"""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a valid .csv file")

    content = file.file.read().decode("utf-8-sig")  # utf-8-sig automatically strips BOM if present
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")
   
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV headers / column names are missing")

    # Validate required fields are present
    fieldnames_set = set(reader.fieldnames)
    if not QUALITY_REQUIRED_FIELDS.issubset(fieldnames_set):
        missing = QUALITY_REQUIRED_FIELDS - fieldnames_set
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing)}"
        )

    # Get user and project mappings
    users_by_email = {u.email.lower(): u for u in db.query(User).all()}
    projects_by_code = {p.code.lower(): p for p in db.query(Project).all()}

    success_count = 0
    error_list = []

    for line_no, row in enumerate(rows, start=2):
        try:
            # Get user
            user_email = row["user_email"].strip().lower()
            user = users_by_email.get(user_email)
            if not user:
                error_list.append(f"Line {line_no}: User with email '{row['user_email']}' not found")
                continue

            # Get project
            project_code = row["project_code"].strip().lower()
            project = projects_by_code.get(project_code)
            if not project:
                error_list.append(f"Line {line_no}: Project with code '{row['project_code']}' not found")
                continue

            # Parse date
            try:
                metric_date = datetime.strptime(row["metric_date"].strip(), "%Y-%m-%d").date()
            except ValueError:
                error_list.append(f"Line {line_no}: Invalid date format '{row['metric_date']}'. Use YYYY-MM-DD")
                continue

            # Validate rating
            rating_str = row["rating"].strip().upper()
            try:
                rating = QualityRating(rating_str)
            except ValueError:
                error_list.append(f"Line {line_no}: Invalid rating '{row['rating']}'. Must be GOOD, AVERAGE, or BAD")
                continue

            # Get optional fields
            quality_score = None
            if row.get("quality_score") and row["quality_score"].strip():
                try:
                    quality_score = float(row["quality_score"].strip())
                    if quality_score < 0 or quality_score > 10:
                        error_list.append(f"Line {line_no}: Quality score must be between 0 and 10")
                        continue
                except ValueError:
                    error_list.append(f"Line {line_no}: Invalid quality_score '{row['quality_score']}'")
                    continue

            accuracy = None
            if row.get("accuracy") and row["accuracy"].strip():
                try:
                    accuracy = float(row["accuracy"].strip())
                    if accuracy < 0 or accuracy > 100:
                        error_list.append(f"Line {line_no}: Accuracy must be between 0 and 100")
                        continue
                except ValueError:
                    error_list.append(f"Line {line_no}: Invalid accuracy '{row['accuracy']}'")
                    continue

            critical_rate = None
            if row.get("critical_rate") and row["critical_rate"].strip():
                try:
                    critical_rate = float(row["critical_rate"].strip())
                    if critical_rate < 0 or critical_rate > 100:
                        error_list.append(f"Line {line_no}: Critical rate must be between 0 and 100")
                        continue
                except ValueError:
                    error_list.append(f"Line {line_no}: Invalid critical_rate '{row['critical_rate']}'")
                    continue

            work_role = row.get("work_role", "").strip() or None
            if not work_role:
                # Try to get from project_members
                member = db.query(ProjectMember).filter(
                    ProjectMember.user_id == user.id,
                    ProjectMember.project_id == project.id
                ).first()
                if member:
                    work_role = member.work_role
                else:
                    work_role = "UNKNOWN"

            notes = row.get("notes", "").strip() or None

            # Convert metric_date (date) to datetime for valid_from
            # Use start of day (00:00:00) for the metric_date
            valid_from_datetime = datetime.combine(metric_date, datetime.min.time())
            
            # Archive existing current quality record
            current_quality = db.query(UserQuality).filter(
                UserQuality.user_id == user.id,
                UserQuality.project_id == project.id,
                UserQuality.is_current == True
            ).first()

            if current_quality:
                current_quality.is_current = False
                # Set valid_to to the end of the day before metric_date
                # This ensures the previous record is valid up to but not including metric_date
                prev_day = metric_date - timedelta(days=1)
                current_quality.valid_to = datetime.combine(prev_day, datetime.max.time())

            # Create new quality record
            new_quality = UserQuality(
                user_id=user.id,
                project_id=project.id,
                work_role=work_role,
                rating=rating,
                quality_score=quality_score,
                accuracy=accuracy,
                critical_rate=critical_rate,
                notes=notes,
                source="MANUAL",
                assessed_by_user_id=current_user.id,
                assessed_at=datetime.now(),
                is_current=True,
                valid_from=valid_from_datetime,
                valid_to=None
            )

            db.add(new_quality)
            success_count += 1

        except Exception as e:
            error_list.append(f"Line {line_no}: Unexpected error - {str(e)}")
            continue

    if success_count > 0:
        db.commit()

    return {
        "inserted": success_count,
        "errors": error_list,
    }
