"""Authoritative, privacy-scoped context for the student AI assistant."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.services.simulation_persistence import get_official_session_response


_MONTH_REFERENCE = re.compile(r"\bmonth\s*(1[0-2]|[1-9])\b", re.IGNORECASE)


class StudentAIContextAssembler:
    """Build one student's compact context without touching peer data."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def build(
        self,
        auth: AuthContext,
        *,
        message: str,
        draft_policy_code: str,
        draft_params: dict[str, float],
    ) -> dict[str, Any]:
        if auth.enrollment is None or auth.course is None:
            raise ValueError("Student AI context requires an authenticated enrollment")
        if (
            auth.enrollment.user_id != auth.user.id
            or auth.enrollment.course_id != auth.course.id
        ):
            raise ValueError("Authenticated student scope is inconsistent")

        official = get_official_session_response(self._db, auth.enrollment.id)
        requested_months = {
            int(match.group(1)) for match in _MONTH_REFERENCE.finditer(message)
        }

        monthly_history: list[dict[str, Any]] = []
        previous_policy_hash: str | None = None
        historical_policies: list[dict[str, Any]] = []
        for result in official.monthly_results:
            monthly_history.append(
                {
                    "month": result.month,
                    "total_requests": result.total_requests,
                    "admitted_requests": result.admitted_requests,
                    "completed_requests": result.completed_requests,
                    "rejected_requests": result.rejected_requests,
                    "total_revenue": result.total_revenue,
                    "unfinished_requests": result.unfinished_requests,
                    "unfinished_value": result.unfinished_value,
                    "warnings_count": len(result.warnings),
                    "warnings": result.warnings[:10],
                    "by_type": [item.model_dump() for item in result.by_type],
                    "avg_utilization": result.avg_utilization,
                    "peak_utilization": result.peak_utilization,
                    "policy_hash": result.policy_hash,
                    "policy_changed_from_previous_month": (
                        previous_policy_hash is not None
                        and previous_policy_hash != result.policy_hash
                    ),
                }
            )
            if result.month in requested_months:
                historical_policies.append(
                    {
                        "month": result.month,
                        "policy_code": result.policy_code,
                        "params": result.params,
                        "policy_hash": result.policy_hash,
                    }
                )
            previous_policy_hash = result.policy_hash

        latest_result = official.monthly_results[-1] if official.monthly_results else None
        return {
            "course_public_context": {
                "course_name": auth.course.course_name,
                "semester": auth.course.semester,
                "public_rules_source": "server-maintained public simulator rules",
            },
            "official_progress": {
                "completed_months": official.completed_months,
                "next_month": official.next_month,
                "status": official.status,
            },
            "official_cumulative_metrics": {
                "total_requests": official.cumulative.total_requests,
                "admitted_requests": official.cumulative.admitted_requests,
                "completed_requests": official.cumulative.completed_requests,
                "rejected_requests": official.cumulative.rejected_requests,
                "total_revenue": official.cumulative.total_revenue,
                "total_unfinished_requests": official.cumulative.total_unfinished_requests,
                "total_unfinished_value": official.cumulative.total_unfinished_value,
                "warnings_count": official.cumulative.warnings_count,
                "by_type": [item.model_dump() for item in official.cumulative.by_type],
            },
            "official_monthly_history": monthly_history,
            "latest_executed_policy": (
                {
                    "month": latest_result.month,
                    "policy_code": latest_result.policy_code,
                    "params": latest_result.params,
                    "policy_hash": latest_result.policy_hash,
                }
                if latest_result is not None
                else None
            ),
            "requested_historical_policies": historical_policies,
            "current_editor_draft": {
                "authoritative": False,
                "has_been_executed": False,
                "policy_code": draft_policy_code,
                "params": draft_params,
            },
        }
