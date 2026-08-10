"""
Student submission endpoint.

POST /submissions
  A separate, authenticated flow from POST /simulate: the student submits
  policy_code + params, and this endpoint independently recomputes the
  full-year result server-side (same policy compiler, same DEFAULT_SEED,
  same run_full_simulation used by /simulate) rather than trusting any
  client-supplied numbers, then persists it against the caller's own
  enrollment. POST /simulate itself is unchanged and still never persists.

The frontend calls this as POST /api/submissions.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_student
from app.db.session import get_db
from app.models import Submission
from app.schemas.submissions import SubmitResultRequest, SubmitResultResponse
from app.services.policy_sandbox import PolicyError, compile_policy
from app.services.simulation_engine import DEFAULT_SEED, run_full_simulation

router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.post("", response_model=SubmitResultResponse, status_code=201)
def submit_result(
    request: SubmitResultRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_student)],
) -> SubmitResultResponse:
    try:
        policy_fn = compile_policy(request.policy_code)
    except PolicyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = run_full_simulation(policy_fn, request.params, seed=DEFAULT_SEED)

    submission = Submission(
        enrollment_id=context.enrollment.id,
        total_revenue=result["total_revenue"],
        total_unfinished_requests=result["total_unfinished_requests"],
        total_unfinished_value=result["total_unfinished_value"],
        warnings_count=len(result["warnings"]),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return SubmitResultResponse.from_submission(submission)
