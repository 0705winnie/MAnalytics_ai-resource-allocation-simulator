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
all four policies below so results are deterministic given a fixed arrival
stream and seed.
"""

from __future__ import annotations

from typing import Callable, Dict


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


BASELINE_POLICIES: Dict[str, Callable[[dict, dict, dict, dict], int]] = {
    "always_reject": always_reject_policy,
    "greedy_first_fit": greedy_first_fit_policy,
    "least_loaded": least_loaded_policy,
    "best_fit": best_fit_policy,
}
