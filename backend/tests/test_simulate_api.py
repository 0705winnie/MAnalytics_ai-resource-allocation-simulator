"""
API-level tests for POST /simulate (app/routers/simulate.py).

Focus: the request schema's contract, not the simulation math (covered in
test_simulation_engine.py).
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


def test_simulate_endpoint_succeeds_without_seed():
    resp = client.post("/simulate", json={"policy_code": FIRST_FIT_SOURCE, "params": {}})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["monthly"]) == 12
    assert "total_unfinished_requests" in body
    assert "total_unfinished_value" in body
    assert "benchmark_comparison" in body
    assert {row["policy"] for row in body["benchmark_comparison"]}.issuperset(
        {"student_policy", "greedy_first_fit", "least_loaded", "best_fit", "vip_only"}
    )


def test_simulate_endpoint_rejects_client_provided_seed():
    resp = client.post(
        "/simulate",
        json={"policy_code": FIRST_FIT_SOURCE, "params": {}, "seed": 12345},
    )

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert any("seed" in str(err.get("loc", "")) for err in detail)


def test_simulate_endpoint_result_matches_backend_default_seed():
    # Two clients trying to smuggle different seeds in should still get
    # rejected, and a normal (seed-less) request should match what the
    # engine itself produces for DEFAULT_SEED — i.e. the server, not the
    # client, controls the arrival stream.
    from app.services.policy_sandbox import compile_policy
    from app.services.simulation_engine import DEFAULT_SEED, run_full_simulation

    resp = client.post("/simulate", json={"policy_code": FIRST_FIT_SOURCE, "params": {}})
    assert resp.status_code == 200

    expected = run_full_simulation(compile_policy(FIRST_FIT_SOURCE), {}, seed=DEFAULT_SEED)
    assert resp.json()["total_revenue"] == expected["total_revenue"]
