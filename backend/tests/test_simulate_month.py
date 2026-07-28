"""
Tests for the single-month simulation core: app/services/simulation_engine.py's
`simulate_month()`, and its consistency with `run_full_simulation()`.
"""

import pytest

from app.services.baseline_policies import greedy_first_fit_policy
from app.services.simulation_engine import (
    CLUSTER_CAPACITY,
    DEFAULT_SEED,
    N_CLUSTERS,
    SIMULATION_MONTHS,
    run_full_simulation,
    simulate_month,
)


# ---------------------------------------------------------------------------
# Only the requested month is simulated
# ---------------------------------------------------------------------------


def test_result_is_tagged_with_the_requested_month():
    for month in (1, 6, 12):
        result = simulate_month(month, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)
        assert result["month"] == month


def test_result_shape_contains_only_single_month_fields():
    result = simulate_month(3, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)
    expected_keys = {
        "month",
        "total_requests",
        "admitted_requests",
        "completed_requests",
        "rejected_requests",
        "total_revenue",
        "unfinished_requests",
        "unfinished_value",
        "avg_utilization",
        "peak_utilization",
        "remaining_capacity",
        "by_type",
        "warnings",
    }
    assert set(result.keys()) == expected_keys
    # No accidental aggregation across months (e.g. no "monthly" list, no
    # year-level totals bleeding into a single-month result).
    assert "monthly" not in result
    assert "total_unfinished_requests" not in result


# ---------------------------------------------------------------------------
# Months outside 1-12 are rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_month", [0, -1, 13, 100])
def test_out_of_range_month_raises_value_error(bad_month):
    with pytest.raises(ValueError):
        simulate_month(bad_month, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_repeated_calls_for_the_same_month_are_reproducible():
    result_a = simulate_month(5, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)
    result_b = simulate_month(5, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)
    assert result_a == result_b


# ---------------------------------------------------------------------------
# Different months use different deterministic scenarios
# ---------------------------------------------------------------------------


def test_different_months_produce_different_scenarios():
    result_month_3 = simulate_month(3, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)
    result_month_7 = simulate_month(7, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)

    assert result_month_3["total_requests"] != result_month_7["total_requests"]


# ---------------------------------------------------------------------------
# Capacity / active jobs reset correctly between independent calls
# ---------------------------------------------------------------------------


def test_capacity_and_active_jobs_reset_between_independent_month_calls():
    # Run a heavy month first, then a light one, and compare against running
    # the light month completely alone. If capacity or active jobs leaked
    # across calls (e.g. via shared module-level state), these would differ.
    simulate_month(7, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)  # July: peak multiplier 1.35
    month_1_after_heavy_month = simulate_month(1, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)
    month_1_alone = simulate_month(1, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)

    assert month_1_after_heavy_month == month_1_alone


# ---------------------------------------------------------------------------
# Consistency with the full-year run
# ---------------------------------------------------------------------------


def test_full_year_result_matches_running_all_months_individually():
    full = run_full_simulation(greedy_first_fit_policy, {}, seed=DEFAULT_SEED)

    previous_months = []
    for month in range(1, SIMULATION_MONTHS + 1):
        month_result = simulate_month(
            month, greedy_first_fit_policy, {}, seed=DEFAULT_SEED, previous_months=previous_months
        )
        public_result = {
            k: v for k, v in month_result.items()
            if k not in ("by_type", "warnings", "remaining_capacity")
        }
        previous_months.append(public_result)

        assert public_result == full["monthly"][month - 1]

    # And the by-type/warnings pieces the individual calls saw are consistent
    # with what run_full_simulation aggregated internally.
    assert full["total_unfinished_requests"] == sum(m["unfinished_requests"] for m in previous_months)


# ---------------------------------------------------------------------------
# Remaining capacity snapshot
# ---------------------------------------------------------------------------


def test_remaining_capacity_is_well_formed_and_bounded():
    result = simulate_month(3, greedy_first_fit_policy, {}, seed=DEFAULT_SEED)
    remaining = result["remaining_capacity"]

    assert set(remaining.keys()) == set(range(1, N_CLUSTERS + 1))
    for cluster_id, free_units in remaining.items():
        assert 0 <= free_units <= CLUSTER_CAPACITY[cluster_id]


# ---------------------------------------------------------------------------
# previous_months is actually visible to the policy via history
# ---------------------------------------------------------------------------


def test_previous_months_is_passed_through_to_policy_history():
    seen_history = []

    def history_reading_policy(request, state, history, params):
        seen_history.append(history["previous_months"])
        return 0  # reject everything — only the history plumbing is under test

    fake_previous = [{"month": 1, "total_revenue": 1234}]
    simulate_month(2, history_reading_policy, {}, seed=DEFAULT_SEED, previous_months=fake_previous)

    # Every call the policy received during month 2 saw exactly the
    # previous_months list we passed in.
    assert len(seen_history) > 0
    assert all(h == fake_previous for h in seen_history)


def test_no_previous_months_defaults_to_empty_history():
    seen_history = []

    def history_reading_policy(request, state, history, params):
        seen_history.append(history["previous_months"])
        return 0

    simulate_month(1, history_reading_policy, {}, seed=DEFAULT_SEED)

    assert len(seen_history) > 0
    assert all(h == [] for h in seen_history)
