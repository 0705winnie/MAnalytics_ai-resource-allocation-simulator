"""Official simulation session reads and atomic next-month preparation."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MonthlyResult, SimulationSession
from app.schemas.simulation_sessions import (
    BenchmarkResultResponse,
    CumulativeResultResponse,
    LatestPolicyResponse,
    OfficialMonthlyResultResponse,
    OfficialSessionResponse,
    RunNextMonthRequest,
    RunNextMonthResponse,
)
from app.services.baseline_policies import BASELINE_POLICIES
from app.services.policy_sandbox import compile_policy
from app.services.simulation_engine import DEFAULT_SEED, simulate_month


class OfficialSimulationIntegrityError(RuntimeError):
    """Persisted official state is missing or internally inconsistent."""


class OfficialSimulationConflictError(RuntimeError):
    """A safe client-visible conflict that must not change official state."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context

    def as_detail(self) -> dict[str, Any]:
        detail: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.context is not None:
            detail["context"] = self.context
        return detail


def canonicalize_policy_params(params: Mapping[str, float]) -> str:
    """Return stable JSON for numeric params, independent of key order."""

    normalized = {key: float(value) for key, value in params.items()}
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def calculate_policy_hash(policy_code: str, params: Mapping[str, float]) -> str:
    """Hash exact source plus deterministic params without altering source."""

    source_bytes = policy_code.encode("utf-8")
    params_bytes = canonicalize_policy_params(params).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(len(source_bytes).to_bytes(8, "big"))
    digest.update(source_bytes)
    digest.update(len(params_bytes).to_bytes(8, "big"))
    digest.update(params_bytes)
    return digest.hexdigest()


def _money(value: Decimal | int | float) -> float:
    return float(value)


def _benchmark_result(value: Mapping[str, Any]) -> BenchmarkResultResponse:
    return BenchmarkResultResponse(
        policy=str(value["policy"]),
        total_revenue=_money(value["total_revenue"]),
        total_unfinished_requests=int(value["total_unfinished_requests"]),
        total_unfinished_value=_money(value["total_unfinished_value"]),
        admitted_requests=int(value["admitted_requests"]),
        completed_requests=int(value["completed_requests"]),
        rejected_requests=int(value["rejected_requests"]),
        warnings_count=int(value["warnings_count"]),
    )


def _monthly_response(result: MonthlyResult) -> OfficialMonthlyResultResponse:
    return OfficialMonthlyResultResponse(
        month=result.month,
        policy_code=result.policy_code,
        params={key: float(value) for key, value in result.policy_params.items()},
        policy_hash=result.policy_hash,
        total_requests=result.total_requests,
        admitted_requests=result.admitted_requests,
        completed_requests=result.completed_requests,
        rejected_requests=result.rejected_requests,
        total_revenue=_money(result.total_revenue),
        unfinished_requests=result.unfinished_requests,
        unfinished_value=_money(result.unfinished_value),
        avg_utilization={
            str(key): float(value) for key, value in result.avg_utilization.items()
        },
        peak_utilization={
            str(key): float(value) for key, value in result.peak_utilization.items()
        },
        by_type=[
            {"type": str(value["type"]), "total_revenue": _money(value["total_revenue"])}
            for value in result.by_type
        ],
        warnings=list(result.warnings),
        benchmark_comparison=[
            _benchmark_result(value) for value in result.benchmark_comparison
        ],
        completed_at=result.completed_at,
    )


def _public_history_result(result: MonthlyResult) -> dict[str, Any]:
    """Match run_full_simulation's public previous-month history shape."""

    return {
        "month": result.month,
        "total_requests": result.total_requests,
        "admitted_requests": result.admitted_requests,
        "completed_requests": result.completed_requests,
        "rejected_requests": result.rejected_requests,
        "total_revenue": _money(result.total_revenue),
        "unfinished_requests": result.unfinished_requests,
        "unfinished_value": _money(result.unfinished_value),
        "avg_utilization": {
            str(key): float(value) for key, value in result.avg_utilization.items()
        },
        "peak_utilization": {
            str(key): float(value) for key, value in result.peak_utilization.items()
        },
    }


def _validate_progress(
    session: SimulationSession,
    monthly_results: Sequence[MonthlyResult],
) -> None:
    expected_months = list(range(1, session.completed_months + 1))
    actual_months = [result.month for result in monthly_results]
    if actual_months != expected_months:
        raise OfficialSimulationIntegrityError(
            "Official simulation progress does not match persisted monthly results"
        )


def _aggregate_results(
    monthly_results: Sequence[MonthlyResult],
) -> CumulativeResultResponse:
    type_totals: dict[str, dict[str, int | Decimal]] = {}
    benchmark_totals: dict[str, dict[str, int | Decimal]] = {}

    for result in monthly_results:
        for value in result.by_type:
            name = str(value["type"])
            total = type_totals.setdefault(
                name,
                {
                    "total_requests": 0,
                    "admitted_requests": 0,
                    "completed_requests": 0,
                    "total_revenue": Decimal("0.00"),
                },
            )
            total["total_requests"] += int(value["total_requests"])
            total["admitted_requests"] += int(value["admitted_requests"])
            total["completed_requests"] += int(value["completed_requests"])
            total["total_revenue"] += Decimal(str(value["total_revenue"]))

        for value in result.benchmark_comparison:
            name = str(value["policy"])
            total = benchmark_totals.setdefault(
                name,
                {
                    "total_revenue": Decimal("0.00"),
                    "total_unfinished_requests": 0,
                    "total_unfinished_value": Decimal("0.00"),
                    "admitted_requests": 0,
                    "completed_requests": 0,
                    "rejected_requests": 0,
                    "warnings_count": 0,
                },
            )
            total["total_revenue"] += Decimal(str(value["total_revenue"]))
            total["total_unfinished_requests"] += int(
                value["total_unfinished_requests"]
            )
            total["total_unfinished_value"] += Decimal(
                str(value["total_unfinished_value"])
            )
            total["admitted_requests"] += int(value["admitted_requests"])
            total["completed_requests"] += int(value["completed_requests"])
            total["rejected_requests"] += int(value["rejected_requests"])
            total["warnings_count"] += int(value["warnings_count"])

    return CumulativeResultResponse(
        total_requests=sum(result.total_requests for result in monthly_results),
        admitted_requests=sum(
            result.admitted_requests for result in monthly_results
        ),
        completed_requests=sum(
            result.completed_requests for result in monthly_results
        ),
        rejected_requests=sum(
            result.rejected_requests for result in monthly_results
        ),
        total_revenue=_money(
            sum(
                (result.total_revenue for result in monthly_results),
                Decimal("0.00"),
            )
        ),
        total_unfinished_requests=sum(
            result.unfinished_requests for result in monthly_results
        ),
        total_unfinished_value=_money(
            sum(
                (result.unfinished_value for result in monthly_results),
                Decimal("0.00"),
            )
        ),
        warnings_count=sum(len(result.warnings) for result in monthly_results),
        by_type=[
            {"type": name, "total_revenue": _money(total["total_revenue"])}
            for name, total in type_totals.items()
        ],
        benchmark_comparison=[
            BenchmarkResultResponse(
                policy=name,
                total_revenue=_money(total["total_revenue"]),
                total_unfinished_requests=int(total["total_unfinished_requests"]),
                total_unfinished_value=_money(total["total_unfinished_value"]),
                admitted_requests=int(total["admitted_requests"]),
                completed_requests=int(total["completed_requests"]),
                rejected_requests=int(total["rejected_requests"]),
                warnings_count=int(total["warnings_count"]),
            )
            for name, total in benchmark_totals.items()
        ],
    )


def load_official_session(
    db: Session,
    enrollment_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> SimulationSession:
    statement = select(SimulationSession).where(
        SimulationSession.enrollment_id == enrollment_id
    )
    if for_update:
        statement = statement.with_for_update()
    session = db.scalar(statement)
    if session is None:
        raise OfficialSimulationIntegrityError(
            "Authenticated enrollment has no official simulation session"
        )
    return session


def _load_monthly_results(
    db: Session,
    session_id: uuid.UUID,
) -> list[MonthlyResult]:
    return list(
        db.scalars(
            select(MonthlyResult)
            .where(MonthlyResult.session_id == session_id)
            .order_by(MonthlyResult.month.asc())
        )
    )


def build_session_response(
    db: Session,
    session: SimulationSession,
) -> OfficialSessionResponse:
    monthly_results = _load_monthly_results(db, session.id)
    _validate_progress(session, monthly_results)
    latest = monthly_results[-1] if monthly_results else None
    status = (
        "not_started"
        if session.completed_months == 0
        else "completed"
        if session.completed_months == 12
        else "in_progress"
    )
    return OfficialSessionResponse(
        session_id=session.id,
        completed_months=session.completed_months,
        next_month=(
            session.completed_months + 1
            if session.completed_months < 12
            else None
        ),
        status=status,
        cumulative=_aggregate_results(monthly_results),
        monthly_results=[_monthly_response(result) for result in monthly_results],
        latest_policy=(
            LatestPolicyResponse(
                policy_code=latest.policy_code,
                params={
                    key: float(value) for key, value in latest.policy_params.items()
                },
                policy_hash=latest.policy_hash,
            )
            if latest is not None
            else None
        ),
    )


def get_official_session_response(
    db: Session,
    enrollment_id: uuid.UUID,
) -> OfficialSessionResponse:
    return build_session_response(db, load_official_session(db, enrollment_id))


def _summarize_month(policy: str, result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "policy": policy,
        "total_revenue": result["total_revenue"],
        "total_unfinished_requests": result["unfinished_requests"],
        "total_unfinished_value": result["unfinished_value"],
        "admitted_requests": result["admitted_requests"],
        "completed_requests": result["completed_requests"],
        "rejected_requests": result["rejected_requests"],
        "warnings_count": len(result["warnings"]),
    }


def _run_month_with_benchmarks(
    month: int,
    policy_code: str,
    params: dict[str, float],
    previous_months: list[dict[str, Any]],
) -> dict[str, Any]:
    policy_fn = compile_policy(policy_code)
    result = simulate_month(
        month,
        policy_fn,
        params,
        seed=DEFAULT_SEED,
        previous_months=previous_months,
    )
    benchmark_comparison = [_summarize_month("student_policy", result)]
    for name, benchmark_fn in BASELINE_POLICIES.items():
        benchmark_result = simulate_month(
            month,
            benchmark_fn,
            {},
            seed=DEFAULT_SEED,
            previous_months=previous_months,
        )
        benchmark_comparison.append(_summarize_month(name, benchmark_result))
    result["benchmark_comparison"] = benchmark_comparison
    return result


def _is_matching_replay(
    existing: MonthlyResult,
    request: RunNextMonthRequest,
    policy_hash: str,
) -> bool:
    return (
        existing.month == request.expected_month
        and existing.policy_hash == policy_hash
        and existing.policy_code == request.policy_code
        and canonicalize_policy_params(existing.policy_params)
        == canonicalize_policy_params(request.params)
    )


def run_next_official_month(
    db: Session,
    enrollment_id: uuid.UUID,
    request: RunNextMonthRequest,
) -> RunNextMonthResponse:
    session = load_official_session(db, enrollment_id, for_update=True)
    policy_hash = calculate_policy_hash(request.policy_code, request.params)
    existing = db.scalar(
        select(MonthlyResult).where(
            MonthlyResult.session_id == session.id,
            MonthlyResult.idempotency_key == request.idempotency_key,
        )
    )
    if existing is not None:
        if not _is_matching_replay(existing, request, policy_hash):
            raise OfficialSimulationConflictError(
                "idempotency_key_conflict",
                "The idempotency key was already used for different inputs",
            )
        return RunNextMonthResponse(
            replayed=True,
            executed_month=existing.month,
            session=build_session_response(db, session),
        )

    if session.completed_months == 12:
        raise OfficialSimulationConflictError(
            "session_completed",
            "The official simulation is already complete",
            context={"completed_months": 12, "next_month": None},
        )

    actual_next_month = session.completed_months + 1
    if request.expected_month != actual_next_month:
        raise OfficialSimulationConflictError(
            "wrong_expected_month",
            "The requested month is no longer the next official month",
            context={
                "completed_months": session.completed_months,
                "expected_month": request.expected_month,
                "next_month": actual_next_month,
            },
        )

    previous_results = _load_monthly_results(db, session.id)
    _validate_progress(session, previous_results)
    previous_months = [
        _public_history_result(result) for result in previous_results
    ]
    result = _run_month_with_benchmarks(
        actual_next_month,
        request.policy_code,
        request.params,
        previous_months,
    )
    completed_at = datetime.now(UTC)
    monthly_result = MonthlyResult(
        session_id=session.id,
        month=actual_next_month,
        idempotency_key=request.idempotency_key,
        policy_code=request.policy_code,
        policy_params=dict(request.params),
        policy_hash=policy_hash,
        total_requests=result["total_requests"],
        admitted_requests=result["admitted_requests"],
        completed_requests=result["completed_requests"],
        rejected_requests=result["rejected_requests"],
        total_revenue=Decimal(str(result["total_revenue"])),
        unfinished_requests=result["unfinished_requests"],
        unfinished_value=Decimal(str(result["unfinished_value"])),
        avg_utilization=result["avg_utilization"],
        peak_utilization=result["peak_utilization"],
        remaining_capacity=result["remaining_capacity"],
        by_type=result["by_type"],
        warnings=result["warnings"],
        benchmark_comparison=result["benchmark_comparison"],
        completed_at=completed_at,
    )
    db.add(monthly_result)
    session.completed_months = actual_next_month
    session.updated_at = completed_at
    session.last_completed_at = completed_at
    db.flush()
    return RunNextMonthResponse(
        replayed=False,
        executed_month=actual_next_month,
        session=build_session_response(db, session),
    )
