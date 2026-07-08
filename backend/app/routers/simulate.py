"""
Simulation endpoint.

POST /simulate
  Compiles the student's `admission_policy` code, runs it against a full
  synthetic year of request arrivals with real capacity/departure dynamics,
  and returns monthly + per-type aggregates.

The frontend calls this as POST /api/simulate.
Vite's dev proxy strips /api and forwards to /simulate here.
"""

from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.policy_sandbox import PolicyError, compile_policy
from app.services.simulation_engine import DEFAULT_SEED, run_full_simulation

router = APIRouter(prefix="/simulate", tags=["Simulation"])


class SimulateRequest(BaseModel):
    policy_code: str = Field(..., min_length=1, description="The student's admission_policy source")
    params: Dict[str, float] = Field(default_factory=dict, description="Student-tunable parameters")
    seed: int = Field(default=DEFAULT_SEED, description="RNG seed for the synthetic arrival stream")


class MonthResult(BaseModel):
    month: int
    total_requests: int
    admitted_requests: int
    completed_requests: int
    rejected_requests: int
    total_revenue: float


class TypeResult(BaseModel):
    type: str
    total_requests: int
    admitted_requests: int
    completed_requests: int
    total_revenue: float


class SimulateResponse(BaseModel):
    monthly: List[MonthResult]
    by_type: List[TypeResult]
    total_revenue: float
    warnings: List[str]


@router.post("", response_model=SimulateResponse)
async def simulate(request: SimulateRequest) -> SimulateResponse:
    try:
        policy_fn = compile_policy(request.policy_code)
    except PolicyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = run_full_simulation(policy_fn, request.params, seed=request.seed)
    return SimulateResponse(**result)
