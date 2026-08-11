"""Complete SQLAlchemy model registry for metadata and Alembic discovery."""

from app.models.course_instance import CourseInstance
from app.models.enrollment import Enrollment
from app.models.llm_daily_usage import LLMDailyUsage
from app.models.monthly_result import MonthlyResult
from app.models.simulation_session import SimulationSession
from app.models.submission import Submission
from app.models.user import User

__all__ = [
    "CourseInstance",
    "Enrollment",
    "LLMDailyUsage",
    "MonthlyResult",
    "SimulationSession",
    "Submission",
    "User",
]
