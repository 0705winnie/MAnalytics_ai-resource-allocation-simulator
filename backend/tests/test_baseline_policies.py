"""
Tests for the benchmark policies in app/services/baseline_policies.py.

Unit tests call each policy function directly with hand-built request/state
dicts (matching exactly what simulation_engine.py's `_run_month` constructs)
so each assertion targets one selection rule in isolation. Integration tests
run each policy through the real `run_full_simulation` engine to confirm it
never misuses the policy interface (i.e. never triggers an engine warning)
and that "Always Reject" matches the spec's explicit zero-payoff requirement.
"""

import pytest

from app.services.baseline_policies import (
    BASELINE_POLICIES,
    always_reject_policy,
    best_fit_policy,
    greedy_first_fit_policy,
    least_loaded_policy,
)
from app.services.simulation_engine import DEFAULT_SEED, run_full_simulation


def _request(required_units: int) -> dict:
    return {"type": "standard", "required_units": required_units, "arrival_time": 0.0}


def _state(remaining_capacity: dict) -> dict:
    return {"remaining_capacity": remaining_capacity}


# ---------------------------------------------------------------------------
# Always Reject
# ---------------------------------------------------------------------------


def test_always_reject_returns_zero_for_any_request():
    state = _state({1: 100, 2: 100, 3: 100})
    assert always_reject_policy(_request(1), state, {}, {}) == 0
    assert always_reject_policy(_request(100), state, {}, {}) == 0


# ---------------------------------------------------------------------------
# Greedy First-Fit
# ---------------------------------------------------------------------------


def test_first_fit_returns_lowest_id_feasible_cluster():
    state = _state({1: 5, 2: 50, 3: 50})
    # Cluster 1 has 5 (not enough for 10), cluster 2 is the first feasible one.
    assert greedy_first_fit_policy(_request(10), state, {}, {}) == 2


def test_first_fit_prefers_lower_id_even_when_later_cluster_has_more_room():
    state = _state({1: 20, 2: 100, 3: 100})
    # Cluster 1 is feasible for a 10-unit request even though 2/3 have more room.
    assert greedy_first_fit_policy(_request(10), state, {}, {}) == 1


def test_first_fit_returns_zero_when_no_cluster_feasible():
    state = _state({1: 2, 2: 3, 3: 1})
    assert greedy_first_fit_policy(_request(10), state, {}, {}) == 0


# ---------------------------------------------------------------------------
# Least-Loaded Feasible
# ---------------------------------------------------------------------------


def test_least_loaded_selects_cluster_with_most_remaining_capacity():
    state = _state({1: 20, 2: 90, 3: 50})
    assert least_loaded_policy(_request(10), state, {}, {}) == 2


def test_least_loaded_excludes_infeasible_clusters_from_comparison():
    state = _state({1: 5, 2: 90, 3: 50})
    # Cluster 1 isn't feasible at all, so it can't win even though it's "least loaded".
    assert least_loaded_policy(_request(10), state, {}, {}) == 2


def test_least_loaded_tie_break_is_lowest_cluster_id():
    state = _state({1: 50, 2: 50, 3: 50})
    assert least_loaded_policy(_request(10), state, {}, {}) == 1


def test_least_loaded_returns_zero_when_no_cluster_feasible():
    state = _state({1: 2, 2: 3, 3: 1})
    assert least_loaded_policy(_request(10), state, {}, {}) == 0


# ---------------------------------------------------------------------------
# Best-Fit Feasible
# ---------------------------------------------------------------------------


def test_best_fit_selects_cluster_with_smallest_leftover_capacity():
    state = _state({1: 20, 2: 90, 3: 12})
    # Leftover after admitting 10: cluster1=10, cluster2=80, cluster3=2 -> cluster 3 wins.
    assert best_fit_policy(_request(10), state, {}, {}) == 3


def test_best_fit_excludes_infeasible_clusters_from_comparison():
    state = _state({1: 9, 2: 90, 3: 12})
    # Cluster 1 isn't feasible for a 10-unit request at all.
    assert best_fit_policy(_request(10), state, {}, {}) == 3


def test_best_fit_tie_break_is_lowest_cluster_id():
    state = _state({1: 50, 2: 50, 3: 50})
    assert best_fit_policy(_request(10), state, {}, {}) == 1


def test_best_fit_returns_zero_when_no_cluster_feasible():
    state = _state({1: 2, 2: 3, 3: 1})
    assert best_fit_policy(_request(10), state, {}, {}) == 0


# ---------------------------------------------------------------------------
# Integration: run each benchmark through the real engine
# ---------------------------------------------------------------------------


def test_always_reject_policy_earns_zero_payoff_over_full_year():
    result = run_full_simulation(always_reject_policy, {}, seed=DEFAULT_SEED)
    assert result["total_revenue"] == 0
    assert result["total_unfinished_requests"] == 0
    assert all(m["admitted_requests"] == 0 for m in result["monthly"])
    assert result["warnings"] == []


@pytest.mark.parametrize("name", list(BASELINE_POLICIES))
def test_each_baseline_policy_runs_cleanly_over_full_year(name):
    policy_fn = BASELINE_POLICIES[name]
    result = run_full_simulation(policy_fn, {}, seed=DEFAULT_SEED)

    # A correctly implemented benchmark only ever returns a real cluster id
    # or 0, so the engine should never have to auto-reject/warn on its behalf.
    assert result["warnings"] == []
    assert len(result["monthly"]) == 12
    for month in result["monthly"]:
        assert month["admitted_requests"] <= month["total_requests"]
        assert month["completed_requests"] <= month["admitted_requests"]
        assert month["total_revenue"] >= 0
