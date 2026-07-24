"""Complete SQLAlchemy model registry for metadata and Alembic discovery."""

from app.models.course_instance import CourseInstance
from app.models.enrollment import Enrollment
from app.models.user import User

__all__ = ["CourseInstance", "Enrollment", "User"]
