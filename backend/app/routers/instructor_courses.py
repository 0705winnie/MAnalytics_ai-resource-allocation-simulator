"""Instructor-owned course instance management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import require_instructor
from app.db.session import get_db
from app.models import CourseInstance, User
from app.services.course_deletions import remove_owned_course


router = APIRouter(prefix="/instructor/courses", tags=["Instructor Courses"])
COURSE_CODE_CONFLICT_MESSAGE = "A course with this course code already exists"
COURSE_NOT_FOUND_MESSAGE = "Course not found"


class CourseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_code: str = Field(min_length=1, max_length=64)
    course_name: str = Field(min_length=1, max_length=255)
    semester: str = Field(min_length=1, max_length=64)

    @field_validator("course_code", "course_name", "semester", mode="before")
    @classmethod
    def trim_text_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_code: str
    course_name: str
    semester: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CourseListResponse(BaseModel):
    items: list[CourseResponse]
    total: int
    offset: int
    limit: int


def _course_code_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=COURSE_CODE_CONFLICT_MESSAGE,
    )


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    request: CourseCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
) -> CourseInstance:
    """Create a globally unique course owned by the authenticated instructor."""

    normalized_code = request.course_code.lower()
    existing_course_id = db.scalar(
        select(CourseInstance.id).where(
            CourseInstance.course_code_normalized == normalized_code
        )
    )
    if existing_course_id is not None:
        raise _course_code_conflict()

    course = CourseInstance(
        course_code=request.course_code,
        course_name=request.course_name,
        semester=request.semester,
        created_by=instructor.id,
        is_active=True,
    )
    db.add(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _course_code_conflict() from None

    db.refresh(course)
    return course


@router.get("", response_model=CourseListResponse)
def list_courses(
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CourseListResponse:
    """List only courses created by the authenticated instructor."""

    owner_filter = CourseInstance.created_by == instructor.id
    total = db.scalar(
        select(func.count())
        .select_from(CourseInstance)
        .where(owner_filter)
    )
    courses = db.scalars(
        select(CourseInstance)
        .where(owner_filter)
        .order_by(CourseInstance.created_at.desc(), CourseInstance.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return CourseListResponse(
        items=[CourseResponse.model_validate(course) for course in courses],
        total=total or 0,
        offset=offset,
        limit=limit,
    )


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
) -> CourseInstance:
    """Return an owned course without revealing other instructors' courses."""

    course = db.scalar(
        select(CourseInstance).where(
            CourseInstance.id == course_id,
            CourseInstance.created_by == instructor.id,
        )
    )
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=COURSE_NOT_FOUND_MESSAGE,
        )
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
) -> Response:
    """Delete an owned course's scoped data while retaining global users."""

    try:
        removed = remove_owned_course(
            db,
            course_id=course_id,
            instructor_id=instructor.id,
        )
        if not removed:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=COURSE_NOT_FOUND_MESSAGE,
            )
        db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The course could not be deleted",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
