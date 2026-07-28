"""
Tests for the discrete-event simulation engine (app/services/simulation_engine.py).

Two testing styles are used deliberately:
- Deterministic, single/few-arrival scenarios call `_run_month` directly so
  each assertion targets one exact mechanism (a specific warning, a specific
  unfinished job) without depending on the stochastic arrival generator.
- Full-year, seed-driven scenarios call `run_full_simulation` to check
  properties that should hold in aggregate across a realistic run.
"""

from app.services.policy_sandbox import compile_policy
from app.services.simulation_engine import (
    CLUSTER_CAPACITY,
    DEFAULT_SEED,
    MONTH_HOURS,
    N_CLUSTERS,
    PRICE_PER_UNIT,
    _run_month,
    run_full_simulation,
)

FIRST_FIT_SOURCE = """
def admission_policy(request, state, history, params):
    for cluster_id, remaining in state["remaining_capacity"].items():
        if remaining >= request["required_units"]:
            return cluster_id
    return 0
"""


def always_reject_policy(request, state, history, params):
    return 0


def first_fit_policy(request, state, history, params):
    for cluster_id, remaining in state["remaining_capacity"].items():
        if remaining >= request["required_units"]:
            return cluster_id
    return 0


def always_cluster_one_policy(request, state, history, params):
    # Ignores capacity entirely — used to probe the engine's own
    # feasibility guard rather than trusting the policy to behave.
    return 1


def raising_policy(request, state, history, params):
    raise RuntimeError("boom")


def non_int_return_policy(request, state, history, params):
    return "1"


def invalid_cluster_id_policy(request, state, history, params):
    return 99


# ---------------------------------------------------------------------------
# Always-reject: sanity baseline
# ---------------------------------------------------------------------------


def test_always_reject_yields_zero_revenue_unfinished_and_utilization():
    result = run_full_simulation(always_reject_policy, {}, seed=DEFAULT_SEED)

    assert result["total_revenue"] == 0
    assert result["total_unfinished_requests"] == 0
    assert result["total_unfinished_value"] == 0
    assert result["warnings"] == []

    for month in result["monthly"]:
        assert month["total_revenue"] == 0
        assert month["admitted_requests"] == 0
        assert month["completed_requests"] == 0
        assert month["rejected_requests"] == month["total_requests"]
        assert month["unfinished_requests"] == 0
        assert month["unfinished_value"] == 0
        assert all(v == 0.0 for v in month["avg_utilization"].values())
        assert all(v == 0.0 for v in month["peak_utilization"].values())


# ---------------------------------------------------------------------------
# Utilization bounds
# ---------------------------------------------------------------------------


def test_utilization_stays_within_bounds_across_seeds():
    for seed in (1, DEFAULT_SEED, 12345):
        result = run_full_simulation(first_fit_policy, {}, seed=seed)
        for month in result["monthly"]:
            for cluster_id in range(1, N_CLUSTERS + 1):
                avg = month["avg_utilization"][cluster_id]
                peak = month["peak_utilization"][cluster_id]
                assert 0.0 <= avg <= 1.0
                assert 0.0 <= peak <= 1.0
                # Time-weighted average can never exceed the peak.
                assert avg <= peak + 1e-9


# ---------------------------------------------------------------------------
# Unfinished jobs must not earn completed revenue
# ---------------------------------------------------------------------------


def test_unfinished_job_earns_no_completed_revenue():
    arrivals = [
        {
            "type": "VIP",
            "required_units": 5,
            "arrival_time": MONTH_HOURS - 1.0,
            "duration": 1000.0,  # departs long after month end
        }
    ]
    warnings = []
    jobs, _avg_util, _peak_util, remaining_capacity = _run_month(
        1, arrivals, always_cluster_one_policy, {}, {"previous_months": []}, warnings
    )

    assert len(jobs) == 1
    job = jobs[0]
    assert job["admitted"] is True
    assert job["completed"] is False
    assert job["revenue"] == 0
    assert job["potential_revenue"] == 5 * PRICE_PER_UNIT["VIP"]
    # The unfinished job is still "active" at month end, so its 5 units stay
    # occupied in the end-of-month capacity snapshot too.
    assert remaining_capacity[1] == CLUSTER_CAPACITY[1] - 5


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_repeated_runs_with_same_seed_are_reproducible():
    policy_a = compile_policy(FIRST_FIT_SOURCE)
    policy_b = compile_policy(FIRST_FIT_SOURCE)

    result_a = run_full_simulation(policy_a, {}, seed=DEFAULT_SEED)
    result_b = run_full_simulation(policy_b, {}, seed=DEFAULT_SEED)

    assert result_a == result_b


# ---------------------------------------------------------------------------
# Capacity conservation
# ---------------------------------------------------------------------------


def test_capacity_never_exceeds_total_even_when_policy_ignores_state():
    # Four requests that together exceed a single cluster's capacity; the
    # policy blindly asks for cluster 1 regardless of what's actually free.
    cluster_one_capacity = CLUSTER_CAPACITY[1]
    oversized_units = cluster_one_capacity
    arrivals = [
        {"type": "VIP", "required_units": oversized_units, "arrival_time": float(t), "duration": 1000.0}
        for t in range(2)
    ]
    warnings = []
    jobs, _avg_util, peak_util, remaining_capacity = _run_month(
        1, arrivals, always_cluster_one_policy, {}, {"previous_months": []}, warnings
    )

    admitted_units_cluster_1 = sum(
        j["required_units"] for j in jobs if j["admitted"] and j["cluster"] == 1
    )
    assert admitted_units_cluster_1 <= cluster_one_capacity
    assert peak_util[1] <= 1.0
    # Capacity can never go negative, however the policy behaves.
    assert remaining_capacity[1] >= 0
    # Two full-cluster requests against one cluster's capacity means at least
    # one request must have been auto-rejected as infeasible.
    assert len(warnings) > 0


# ---------------------------------------------------------------------------
# Invalid / infeasible actions generate warnings
# ---------------------------------------------------------------------------


def _single_arrival(required_units=4):
    return [{"type": "standard", "required_units": required_units, "arrival_time": 0.0, "duration": 1.0}]


def test_exception_raising_policy_is_auto_rejected_with_warning():
    warnings = []
    jobs, _, _, _ = _run_month(1, _single_arrival(), raising_policy, {}, {"previous_months": []}, warnings)

    assert jobs[0]["admitted"] is False
    assert len(warnings) == 1
    assert "raised an exception" in warnings[0]


def test_non_int_return_is_auto_rejected_with_warning():
    warnings = []
    jobs, _, _, _ = _run_month(1, _single_arrival(), non_int_return_policy, {}, {"previous_months": []}, warnings)

    assert jobs[0]["admitted"] is False
    assert len(warnings) == 1
    assert "must return an int" in warnings[0]


def test_invalid_cluster_id_is_auto_rejected_with_warning():
    warnings = []
    jobs, _, _, _ = _run_month(1, _single_arrival(), invalid_cluster_id_policy, {}, {"previous_months": []}, warnings)

    assert jobs[0]["admitted"] is False
    assert len(warnings) == 1
    assert "invalid cluster id" in warnings[0]


def test_infeasible_capacity_choice_is_auto_rejected_with_warning():
    warnings = []
    jobs, _, _, _ = _run_month(
        1,
        _single_arrival(required_units=max(CLUSTER_CAPACITY.values()) + 1),
        always_cluster_one_policy,
        {},
        {"previous_months": []},
        warnings,
    )

    assert jobs[0]["admitted"] is False
    assert len(warnings) == 1
    assert "without enough capacity" in warnings[0]
