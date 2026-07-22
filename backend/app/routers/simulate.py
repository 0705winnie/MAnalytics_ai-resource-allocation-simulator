"""
Simulation endpoints.

POST /simulate
  Compiles the student's `admission_policy` code, runs it against a full
  synthetic year of request arrivals with real capacity/departure dynamics,
  and returns monthly + per-type aggregates.

POST /simulate/month
  Same policy compilation, but runs a single simulated month (1-12) in
  isolation and returns that month's full metrics, including its own
  revenue-by-type breakdown and warnings.

The frontend calls these as POST /api/simulate and POST /api/simulate/month.
Vite's dev proxy strips /api and forwards to this router.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.baseline_policies import BASELINE_POLICIES
from app.services.policy_sandbox import PolicyError, compile_policy
from app.services.simulation_engine import DEFAULT_SEED, run_full_simulation, simulate_month

router = APIRouter(prefix="/simulate", tags=["Simulation"])


class SimulateRequest(BaseModel):
    # `seed` is intentionally NOT a field here: every student must be tested
    # against the same arrival stream (DEFAULT_SEED, applied server-side in
    # the route below) so results are fair and comparable on the leaderboard.
    # `extra="forbid"` turns a client-supplied `seed` (or any other unknown
    # field) into a 422 instead of silently accepting/ignoring it.
    model_config = ConfigDict(extra="forbid")

    policy_code: str = Field(..., min_length=1, description="The student's admission_policy source")
    params: Dict[str, float] = Field(default_factory=dict, description="Student-tunable parameters")


class MonthResult(BaseModel):
    month: int
    total_requests: int
    admitted_requests: int
    completed_requests: int
    rejected_requests: int
    total_revenue: float
    unfinished_requests: int
    unfinished_value: float
    avg_utilization: Dict[int, float]
    peak_utilization: Dict[int, float]


class TypeResult(BaseModel):
    type: str
    total_requests: int
    admitted_requests: int
    completed_requests: int
    total_revenue: float


class BenchmarkResult(BaseModel):
    policy: str
    total_revenue: float
    total_unfinished_requests: int
    total_unfinished_value: float
    admitted_requests: int
    completed_requests: int
    rejected_requests: int
    warnings_count: int


class SimulateResponse(BaseModel):
    monthly: List[MonthResult]
    by_type: List[TypeResult]
    total_revenue: float
    total_unfinished_requests: int
    total_unfinished_value: float
    warnings: List[str]
    benchmark_comparison: List[BenchmarkResult]


class SimulateMonthRequest(BaseModel):
    # Same no-client-seed policy as SimulateRequest above: the backend always
    # derives the month's arrival stream from DEFAULT_SEED server-side.
    model_config = ConfigDict(extra="forbid")

    month: int = Field(..., ge=1, le=12, description="Simulated month to run (1-12)")
    policy_code: str = Field(..., min_length=1, description="The student's admission_policy source")
    params: Dict[str, float] = Field(default_factory=dict, description="Student-tunable parameters")
    # Prior completed months' results, in order, echoed straight back from
    # what this endpoint previously returned for those months. Passed through
    # untouched as history["previous_months"] for the policy to optionally
    # read — the backend never inspects its shape, so the client (which
    # already has these from earlier /simulate/month responses) is the
    # simplest source of truth given there's no server-side session storage.
    previous_months: List[Dict[str, Any]] = Field(default_factory=list)


class MonthDetailResponse(MonthResult):
    remaining_capacity: Dict[int, int]
    by_type: List[TypeResult]
    warnings: List[str]
    benchmark_comparison: List[BenchmarkResult]


def _summarize_full_year(policy: str, result: dict) -> BenchmarkResult:
    return BenchmarkResult(
        policy=policy,
        total_revenue=result["total_revenue"],
        total_unfinished_requests=result["total_unfinished_requests"],
        total_unfinished_value=result["total_unfinished_value"],
        admitted_requests=sum(m["admitted_requests"] for m in result["monthly"]),
        completed_requests=sum(m["completed_requests"] for m in result["monthly"]),
        rejected_requests=sum(m["rejected_requests"] for m in result["monthly"]),
        warnings_count=len(result["warnings"]),
    )


def _summarize_month(policy: str, result: dict) -> BenchmarkResult:
    return BenchmarkResult(
        policy=policy,
        total_revenue=result["total_revenue"],
        total_unfinished_requests=result["unfinished_requests"],
        total_unfinished_value=result["unfinished_value"],
        admitted_requests=result["admitted_requests"],
        completed_requests=result["completed_requests"],
        rejected_requests=result["rejected_requests"],
        warnings_count=len(result["warnings"]),
    )


@router.post("", response_model=SimulateResponse)
async def simulate(request: SimulateRequest) -> SimulateResponse:
    try:
        policy_fn = compile_policy(request.policy_code)
    except PolicyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = run_full_simulation(policy_fn, request.params, seed=DEFAULT_SEED)
    benchmark_comparison = [_summarize_full_year("student_policy", result)]
    for name, benchmark_fn in BASELINE_POLICIES.items():
        benchmark_result = run_full_simulation(benchmark_fn, {}, seed=DEFAULT_SEED)
        benchmark_comparison.append(_summarize_full_year(name, benchmark_result))

    result["benchmark_comparison"] = benchmark_comparison
    return SimulateResponse(**result)


@router.post("/month", response_model=MonthDetailResponse)
async def simulate_single_month(request: SimulateMonthRequest) -> MonthDetailResponse:
    try:
        policy_fn = compile_policy(request.policy_code)
    except PolicyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = simulate_month(
        request.month,
        policy_fn,
        request.params,
        seed=DEFAULT_SEED,
        previous_months=request.previous_months,
    )
    benchmark_comparison = [_summarize_month("student_policy", result)]
    for name, benchmark_fn in BASELINE_POLICIES.items():
        benchmark_result = simulate_month(
            request.month,
            benchmark_fn,
            {},
            seed=DEFAULT_SEED,
            previous_months=request.previous_months,
        )
        benchmark_comparison.append(_summarize_month(name, benchmark_result))

    result["benchmark_comparison"] = benchmark_comparison
    return MonthDetailResponse(**result)
