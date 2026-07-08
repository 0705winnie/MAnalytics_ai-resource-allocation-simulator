"""
Discrete-event simulation engine for Page 3.

Generates a year of synthetic request arrivals using the same distributions
as the historical dataset shown on Page 1 (see src/data/hidden_environment.py
for the canonical parameter definitions this mirrors), then replays them
month by month against the student's `admission_policy`, tracking real
per-cluster capacity and departure events so admit/reject decisions actually
affect what capacity is available later.

Unlike the static historical CSV (where `completed` was a coin flip), here
completion is a real consequence of the policy's admission choices: a job
only earns revenue if it departs before the month ends.
"""

from __future__ import annotations

import heapq
from typing import Callable, Dict, List

import numpy as np

from app.services.policy_sandbox import PolicyRuntimeError, call_policy

REQUEST_TYPES = ["VIP", "standard", "economy"]
N_CLUSTERS = 3
CLUSTER_CAPACITY = 100

SIMULATION_MONTHS = 12
DAYS_PER_MONTH = 30
HOURS_PER_DAY = 24
MONTH_HOURS = DAYS_PER_MONTH * HOURS_PER_DAY  # 720

PRICE_PER_UNIT = {"VIP": 12, "standard": 7, "economy": 4}

BASE_MONTHLY_ARRIVALS = {"VIP": 120, "standard": 450, "economy": 300}

MONTHLY_MULTIPLIER = {
    1: 0.85, 2: 0.90, 3: 1.00, 4: 1.05, 5: 1.10, 6: 1.20,
    7: 1.35, 8: 1.25, 9: 1.10, 10: 1.00, 11: 1.15, 12: 1.30,
}

REQUIRED_UNITS_DISTRIBUTION = {
    "VIP":      {"values": [8, 10, 12, 15], "probabilities": [0.20, 0.35, 0.30, 0.15]},
    "standard": {"values": [4, 6, 8, 10],   "probabilities": [0.25, 0.35, 0.25, 0.15]},
    "economy":  {"values": [2, 3, 4, 6],    "probabilities": [0.30, 0.35, 0.25, 0.10]},
}

MEAN_SERVICE_DURATION = {"VIP": 4, "standard": 6, "economy": 9}
SERVICE_DURATION_GAMMA_SHAPE = 2

DEFAULT_SEED = 42

MAX_WARNINGS = 50


def _sample_required_units(request_type: str, rng: np.random.Generator) -> int:
    dist = REQUIRED_UNITS_DISTRIBUTION[request_type]
    return int(rng.choice(dist["values"], p=dist["probabilities"]))


def _sample_duration(request_type: str, rng: np.random.Generator) -> float:
    mean = MEAN_SERVICE_DURATION[request_type]
    shape = SERVICE_DURATION_GAMMA_SHAPE
    return float(rng.gamma(shape=shape, scale=mean / shape))


def _generate_month_arrivals(month: int, rng: np.random.Generator) -> List[dict]:
    """One month's arrival stream, sorted by arrival_time (hours from month start)."""
    arrivals: List[dict] = []
    for request_type in REQUEST_TYPES:
        expected = BASE_MONTHLY_ARRIVALS[request_type] * MONTHLY_MULTIPLIER[month]
        n = int(rng.poisson(expected))
        for _ in range(n):
            arrival_time = float(rng.uniform(0, MONTH_HOURS))
            arrivals.append({
                "type": request_type,
                "required_units": _sample_required_units(request_type, rng),
                "arrival_time": arrival_time,
                "duration": _sample_duration(request_type, rng),
            })
    arrivals.sort(key=lambda r: r["arrival_time"])
    return arrivals


def _run_month(
    month: int,
    arrivals: List[dict],
    policy_fn: Callable,
    params: dict,
    history: dict,
    warnings: List[str],
) -> List[dict]:
    """
    Replays one month's arrivals against the policy with real capacity
    dynamics. Returns the list of admitted jobs (each with a `completed`
    flag and `revenue`).
    """
    capacity = {i: CLUSTER_CAPACITY for i in range(1, N_CLUSTERS + 1)}
    departures: List[tuple] = []  # heap of (departure_time, cluster_id, units)
    admitted_jobs: List[dict] = []

    for req in arrivals:
        # Release capacity for anything that departed before this arrival.
        while departures and departures[0][0] <= req["arrival_time"]:
            _, cluster_id, units = heapq.heappop(departures)
            capacity[cluster_id] += units

        request_view = {
            "type": req["type"],
            "required_units": req["required_units"],
            "arrival_time": req["arrival_time"],
        }
        state_view = {"remaining_capacity": dict(capacity)}

        try:
            choice = call_policy(policy_fn, request_view, state_view, history, params)
        except PolicyRuntimeError as e:
            choice = 0
            if len(warnings) < MAX_WARNINGS:
                warnings.append(f"Month {month}: {e}")

        if choice != 0:
            if choice not in capacity:
                if len(warnings) < MAX_WARNINGS:
                    warnings.append(
                        f"Month {month}: policy returned invalid cluster id {choice}; auto-rejected."
                    )
                choice = 0
            elif capacity[choice] < req["required_units"]:
                if len(warnings) < MAX_WARNINGS:
                    warnings.append(
                        f"Month {month}: policy chose cluster {choice} without enough capacity; auto-rejected."
                    )
                choice = 0

        if choice == 0:
            admitted_jobs.append({**req, "admitted": False, "completed": False, "revenue": 0})
            continue

        capacity[choice] -= req["required_units"]
        departure_time = req["arrival_time"] + req["duration"]
        heapq.heappush(departures, (departure_time, choice, req["required_units"]))

        completed = departure_time <= MONTH_HOURS
        revenue = req["required_units"] * PRICE_PER_UNIT[req["type"]] if completed else 0

        admitted_jobs.append({
            **req,
            "admitted": True,
            "cluster": choice,
            "completed": completed,
            "revenue": revenue,
        })

    return admitted_jobs


def run_full_simulation(
    policy_fn: Callable,
    params: dict,
    seed: int = DEFAULT_SEED,
) -> dict:
    """
    Runs all 12 months and returns aggregated results:
      { "monthly": [...], "by_type": [...], "total_revenue": float, "warnings": [...] }
    """
    rng = np.random.default_rng(seed)
    warnings: List[str] = []
    monthly_results: List[dict] = []
    previous_months: List[dict] = []

    type_totals: Dict[str, dict] = {
        t: {"total_requests": 0, "admitted_requests": 0, "completed_requests": 0, "total_revenue": 0.0}
        for t in REQUEST_TYPES
    }

    for month in range(1, SIMULATION_MONTHS + 1):
        arrivals = _generate_month_arrivals(month, rng)
        history = {"previous_months": previous_months}
        jobs = _run_month(month, arrivals, policy_fn, params, history, warnings)

        total_requests = len(jobs)
        admitted = sum(1 for j in jobs if j["admitted"])
        completed = sum(1 for j in jobs if j["completed"])
        rejected = total_requests - admitted
        revenue = sum(j["revenue"] for j in jobs)

        month_result = {
            "month": month,
            "total_requests": total_requests,
            "admitted_requests": admitted,
            "completed_requests": completed,
            "rejected_requests": rejected,
            "total_revenue": round(revenue, 2),
        }
        monthly_results.append(month_result)
        previous_months.append(month_result)

        for j in jobs:
            t = type_totals[j["type"]]
            t["total_requests"] += 1
            t["admitted_requests"] += 1 if j["admitted"] else 0
            t["completed_requests"] += 1 if j["completed"] else 0
            t["total_revenue"] += j["revenue"]

    by_type = [
        {
            "type": t,
            "total_requests": v["total_requests"],
            "admitted_requests": v["admitted_requests"],
            "completed_requests": v["completed_requests"],
            "total_revenue": round(v["total_revenue"], 2),
        }
        for t, v in type_totals.items()
    ]

    total_revenue = round(sum(m["total_revenue"] for m in monthly_results), 2)

    return {
        "monthly": monthly_results,
        "by_type": by_type,
        "total_revenue": total_revenue,
        "warnings": warnings,
    }
