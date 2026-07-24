"""Instructor-owned roster import and one-time activation-code export."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_instructor
from app.db.session import get_db
from app.models import User
from app.routers.instructor_courses import COURSE_NOT_FOUND_MESSAGE
from app.services.instructor_enrollments import find_owned_course
from app.services.roster_imports import (
    MAX_ROSTER_BYTES,
    RosterCsvError,
    import_roster,
    parse_roster_csv,
    render_roster_csv,
    roster_summary,
)


router = APIRouter(prefix="/instructor/courses", tags=["Instructor Rosters"])
ROSTER_CONFLICT_MESSAGE = "The roster could not be imported"


@router.post("/{course_id}/roster/import")
async def import_course_roster(
    course_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
) -> Response:
    """Import one owned active course roster and return its codes once."""

    course = find_owned_course(db, course_id, instructor.id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=COURSE_NOT_FOUND_MESSAGE,
        )
    if not course.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inactive courses cannot accept roster imports",
        )

    try:
        content = await file.read(MAX_ROSTER_BYTES + 1)
    finally:
        await file.close()
    if len(content) > MAX_ROSTER_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The roster CSV exceeds the 1 MB limit",
        )

    try:
        input_rows = parse_roster_csv(content)
    except RosterCsvError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None

    try:
        rows = import_roster(db, course, input_rows)
        csv_content = render_roster_csv(rows)
        counts = roster_summary(rows)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ROSTER_CONFLICT_MESSAGE,
        ) from None
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The roster import could not be completed",
        ) from None

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="roster-activation-codes.csv"'
            ),
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Roster-Created": str(counts["created"]),
            "X-Roster-Already-Enrolled": str(counts["already_enrolled"]),
            "X-Roster-Invalid": str(counts["invalid"]),
            "X-Roster-Conflicts": str(
                counts["role_conflict"] + counts["user_inactive"]
            ),
        },
    )
