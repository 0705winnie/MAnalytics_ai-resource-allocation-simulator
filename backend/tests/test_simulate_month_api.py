"""
API-level tests for POST /simulate/month (app/routers/simulate.py).

Focus: the request schema's contract (month bounds, no client seed) and
that the route wires through to `simulate_month` correctly. Simulation math
itself is covered in test_simulate_month.py.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FIRST_FIT_SOURCE = """
def admission_policy(request, state, history, params):
    for cluster_id, remaining in state["remaining_capacity"].items():
        if remaining >= request["required_units"]:
            return cluster_id
    return 0
"""


def test_simulate_month_endpoint_succeeds():
    resp = client.post("/simulate/month", json={"month": 3, "policy_code": FIRST_FIT_SOURCE, "params": {}})

    assert resp.status_code == 200
    body = resp.json()
    assert body["month"] == 3
    assert "by_type" in body
    assert "warnings" in body
    assert "avg_utilization" in body
    assert "peak_utilization" in body
    assert "remaining_capacity" in body
    assert "benchmark_comparison" in body
    # JSON object keys always arrive as strings, even though the Python side
    # keys this dict by int cluster id.
    assert set(body["remaining_capacity"].keys()) == {str(i) for i in range(1, 11)}
    assert {row["policy"] for row in body["benchmark_comparison"]}.issuperset(
        {"student_policy", "greedy_first_fit", "least_loaded", "best_fit", "vip_only"}
    )


def test_simulate_month_endpoint_defaults_previous_months_to_empty():
    # previous_months is optional; omitting it entirely must not error.
    resp = client.post("/simulate/month", json={"month": 1, "policy_code": FIRST_FIT_SOURCE, "params": {}})
    assert resp.status_code == 200


def test_simulate_month_endpoint_passes_previous_months_to_policy():
    history_reading_policy_code = """
def admission_policy(request, state, history, params):
    # Reject everything once any previous month history is present, so the
    # response's admitted_requests is a directly observable proxy for
    # whether `previous_months` actually reached the policy.
    if history["previous_months"]:
        return 0
    for cluster_id, remaining in state["remaining_capacity"].items():
        if remaining >= request["required_units"]:
            return cluster_id
    return 0
"""
    resp_without_history = client.post(
        "/simulate/month",
        json={"month": 2, "policy_code": history_reading_policy_code, "params": {}},
    )
    resp_with_history = client.post(
        "/simulate/month",
        json={
            "month": 2,
            "policy_code": history_reading_policy_code,
            "params": {},
            "previous_months": [{"month": 1, "total_revenue": 999}],
        },
    )

    assert resp_without_history.status_code == 200
    assert resp_with_history.status_code == 200
    # Same arrivals (same month, same server-managed seed) either way, but
    # supplying previous_months flips this policy from admitting to rejecting.
    assert resp_without_history.json()["admitted_requests"] > 0
    assert resp_with_history.json()["admitted_requests"] == 0


def test_simulate_month_endpoint_rejects_month_zero():
    resp = client.post("/simulate/month", json={"month": 0, "policy_code": FIRST_FIT_SOURCE, "params": {}})
    assert resp.status_code == 422


def test_simulate_month_endpoint_rejects_month_thirteen():
    resp = client.post("/simulate/month", json={"month": 13, "policy_code": FIRST_FIT_SOURCE, "params": {}})
    assert resp.status_code == 422


def test_simulate_month_endpoint_rejects_client_provided_seed():
    resp = client.post(
        "/simulate/month",
        json={"month": 3, "policy_code": FIRST_FIT_SOURCE, "params": {}, "seed": 999},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert any("seed" in str(err.get("loc", "")) for err in detail)


def test_simulate_month_endpoint_matches_engine_for_default_seed():
    from app.services.policy_sandbox import compile_policy
    from app.services.simulation_engine import DEFAULT_SEED, simulate_month

    resp = client.post("/simulate/month", json={"month": 5, "policy_code": FIRST_FIT_SOURCE, "params": {}})
    assert resp.status_code == 200

    expected = simulate_month(5, compile_policy(FIRST_FIT_SOURCE), {}, seed=DEFAULT_SEED)
    assert resp.json()["total_revenue"] == expected["total_revenue"]
    assert resp.json()["total_requests"] == expected["total_requests"]


def test_full_year_endpoint_still_works_unchanged():
    # Backward-compatibility guard: /simulate must still behave exactly as
    # before the /simulate/month addition.
    resp = client.post("/simulate", json={"policy_code": FIRST_FIT_SOURCE, "params": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["monthly"]) == 12
    assert "by_type" in body
    assert "total_revenue" in body
