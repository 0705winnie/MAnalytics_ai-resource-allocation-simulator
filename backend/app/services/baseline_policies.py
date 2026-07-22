"""
Benchmark admission policies (Section 8 of the project spec).

These exist for debugging, teaching, and as a performance floor/reference in
the project report. Each function implements the same call contract the
simulation engine uses for a student's `admission_policy`:

    policy_fn(request, state, history, params) -> int

    request : dict — {"type": str, "required_units": int, "arrival_time": float}
    state   : dict — {"remaining_capacity": {cluster_id: int, ...}}
    history : dict — historical data + previous monthly results (unused here)
    params  : dict — student-tunable parameters (unused here)
    returns : int  — a cluster id present in state["remaining_capacity"], or 0 to reject

They are plain Python callables, not source strings — pass them straight into
`run_full_simulation`/`_run_month`/`call_policy` the same way a compiled
student policy is passed in. No separate benchmark simulation path exists;
these are just alternative `policy_fn` values for the existing engine.

Tie-breaking: whenever more than one cluster ties on a policy's selection
criterion, the lowest cluster id wins. This is applied consistently across
all policies below so results are deterministic given a fixed arrival
stream and seed.
"""

from __future__ import annotations

from typing import Callable, Dict

from app.services.hidden_environment import MEAN_SERVICE_DURATION, PRICE_PER_UNIT


def always_reject_policy(request: dict, state: dict, history: dict, params: dict) -> int:
    """Reject every request. Sanity-check baseline — should earn zero payoff."""
    return 0


def greedy_first_fit_policy(request: dict, state: dict, history: dict, params: dict) -> int:
    """Admit to the lowest-numbered cluster with enough remaining capacity."""
    required = request["required_units"]
    for cluster_id in sorted(state["remaining_capacity"]):
        if state["remaining_capacity"][cluster_id] >= required:
            return cluster_id
    return 0


def least_loaded_policy(request: dict, state: dict, history: dict, params: dict) -> int:
    """
    Admit to the feasible cluster with the most remaining capacity (spreads
    load across clusters). Ties broken by lowest cluster id.
    """
    required = request["required_units"]
    feasible = [
        (cluster_id, remaining)
        for cluster_id, remaining in state["remaining_capacity"].items()
        if remaining >= required
    ]
    if not feasible:
        return 0
    feasible.sort(key=lambda pair: (-pair[1], pair[0]))
    return feasible[0][0]


def best_fit_policy(request: dict, state: dict, history: dict, params: dict) -> int:
    """
    Admit to the feasible cluster that leaves the smallest nonnegative
    remaining capacity after admission (packs clusters tightly). Ties broken
    by lowest cluster id.
    """
    required = request["required_units"]
    feasible = [
        (cluster_id, remaining - required)
        for cluster_id, remaining in state["remaining_capacity"].items()
        if remaining >= required
    ]
    if not feasible:
        return 0
    feasible.sort(key=lambda pair: (pair[1], pair[0]))
    return feasible[0][0]


def vip_priority_policy(request: dict, state: dict, history: dict, params: dict) -> int:
    """
    Protect capacity for high-value work.

    VIP requests are admitted whenever feasible. Standard requests are admitted
    unless they would leave the selected cluster almost full. Economy requests
    are admitted only when there is enough spare capacity after assignment.
    """
    request_type = request["type"]
    required = request["required_units"]
    feasible = [
        (cluster_id, remaining - required)
        for cluster_id, remaining in state["remaining_capacity"].items()
        if remaining >= required
    ]
    if not feasible:
        return 0

    feasible.sort(key=lambda pair: (-pair[1], pair[0]))
    best_cluster, leftover = feasible[0]

    if request_type == "economy" and leftover < 8:
        return 0
    if request_type == "standard" and leftover < 4:
        return 0
    return best_cluster


def revenue_density_policy(request: dict, state: dict, history: dict, params: dict) -> int:
    """
    Admit work based on expected revenue per capacity-hour.

    This benchmark uses hidden type-level mean duration as a simple estimate.
    It is useful as a reference policy, not as a policy students should be
    handed directly.
    """
    request_type = request["type"]
    required = request["required_units"]
    density = PRICE_PER_UNIT[request_type] / MEAN_SERVICE_DURATION[request_type]

    feasible = [
        (cluster_id, remaining - required)
        for cluster_id, remaining in state["remaining_capacity"].items()
        if remaining >= required
    ]
    if not feasible:
        return 0

    feasible.sort(key=lambda pair: (pair[1], pair[0]))
    best_cluster, leftover = feasible[0]

    if density < 0.35 and leftover < 10:
        return 0
    if density < 1.0 and leftover < 4:
        return 0
    return best_cluster


BASELINE_POLICIES: Dict[str, Callable[[dict, dict, dict, dict], int]] = {
    "always_reject": always_reject_policy,
    "greedy_first_fit": greedy_first_fit_policy,
    "least_loaded": least_loaded_policy,
    "best_fit": best_fit_policy,
    "vip_priority": vip_priority_policy,
    "revenue_density": revenue_density_policy,
}
