"""
Mock AI assistant for the resource allocation simulator.

This module provides deterministic, API-free responses for the dashboard while
the real LLM integration is still under development. The mock is intentionally
conservative: it helps students reason about the public problem setup without
revealing hidden environment parameters or future simulation outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_OPENING = (
    "I can help you reason about the resource allocation case, interpret the "
    "historical data, brainstorm policy ideas, and debug policy logic. I will "
    "avoid revealing hidden simulator parameters or future test data."
)


@dataclass(frozen=True)
class MockAgentResponse:
    """Structured response returned by the mock assistant."""

    message: str
    topic: str
    follow_up_questions: list[str] = field(default_factory=list)


class MockResourceAllocationAgent:
    """Rule-based assistant for the classroom simulator."""

    def reply(self, user_message: str) -> MockAgentResponse:
        """Return a deterministic response for a student message."""
        text = user_message.lower().strip()

        if not text:
            return MockAgentResponse(
                message=DEFAULT_OPENING,
                topic="opening",
                follow_up_questions=[
                    "Which part are you working on: data, policy design, or results?",
                    "Do you want a baseline policy idea or help interpreting a metric?",
                ],
            )

        if self._mentions(text, "error", "bug", "debug", "infeasible", "invalid"):
            return self._debugging_response()

        if self._mentions(text, "baseline", "benchmark", "first fit", "least loaded", "best fit"):
            return self._benchmark_response()

        if self._mentions(text, "reject", "admit", "admission", "accept every", "accept all"):
            return self._admission_tradeoff_response()

        if self._mentions(text, "capacity", "cluster", "utilization", "remaining", "active"):
            return self._capacity_response()

        if self._mentions(text, "revenue", "payoff", "profit", "unfinished", "completed"):
            return self._metrics_response()

        if self._mentions(text, "vip", "priority", "standard", "economy"):
            return self._request_type_response()

        if self._mentions(text, "policy", "algorithm", "function", "api", "signature"):
            return self._policy_interface_response()

        if self._mentions(text, "historical", "data", "dataset", "plot", "trend"):
            return self._historical_data_response()

        return self._general_response()

    @staticmethod
    def _mentions(text: str, *keywords: str) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _policy_interface_response() -> MockAgentResponse:
        return MockAgentResponse(
            topic="policy_interface",
            message=(
                "Your policy should act like an online decision rule. Each time a "
                "request arrives, it should look at the request, the current cluster "
                "state, available history, and any tuning parameters, then return a "
                "cluster id to admit the request or 0 to reject it. A good policy "
                "checks feasibility first, then weighs value, capacity usage, and "
                "future opportunity cost."
            ),
            follow_up_questions=[
                "What information will your policy use before choosing a cluster?",
                "How will your policy handle a request that fits in more than one cluster?",
            ],
        )

    @staticmethod
    def _historical_data_response() -> MockAgentResponse:
        return MockAgentResponse(
            topic="historical_data",
            message=(
                "Use the historical data to estimate patterns, not to look for the "
                "hidden truth directly. Useful things to inspect are demand by month, "
                "type mix, required-unit distributions, duration distributions, and "
                "completion or revenue differences by request type. Those patterns can "
                "guide admission thresholds and cluster assignment rules."
            ),
            follow_up_questions=[
                "Which request types appear most valuable per unit of capacity?",
                "Do any months look like peak-demand periods?",
            ],
        )

    @staticmethod
    def _benchmark_response() -> MockAgentResponse:
        return MockAgentResponse(
            topic="benchmarks",
            message=(
                "Start with simple benchmark policies before trying a complex one. "
                "Always reject is a sanity check. First-fit admits to the first "
                "feasible cluster. Least-loaded sends the request to the cluster with "
                "the most remaining capacity. Best-fit sends it to the feasible cluster "
                "that leaves the least unused capacity. VIP-only admits VIP requests "
                "and rejects standard/economy requests; it is useful diagnostically, "
                "but may leave too much capacity unused. A VIP-priority or type-priority "
                "rule can reserve scarce capacity for high-value requests."
            ),
            follow_up_questions=[
                "Which benchmark should your policy try to beat first?",
                "Should your policy optimize utilization, revenue, or high-priority completion?",
            ],
        )

    @staticmethod
    def _admission_tradeoff_response() -> MockAgentResponse:
        return MockAgentResponse(
            topic="admission_tradeoff",
            message=(
                "Accepting every feasible request can be tempting, but it may perform "
                "poorly when long, low-value jobs block capacity that could serve future "
                "high-value jobs. Rejection is not automatically bad. It can be a way to "
                "protect scarce capacity when the opportunity cost of admission is high."
            ),
            follow_up_questions=[
                "Which requests consume a lot of capacity for relatively low payoff?",
                "When capacity is scarce, which request types should receive priority?",
            ],
        )

    @staticmethod
    def _capacity_response() -> MockAgentResponse:
        return MockAgentResponse(
            topic="capacity",
            message=(
                "Capacity is reusable. When a request is admitted, it consumes server "
                "units until its service duration ends. After departure, those units "
                "become available again. Your policy should consider both current "
                "remaining capacity and how much work is already active in each cluster."
            ),
            follow_up_questions=[
                "Are you balancing load across clusters or packing jobs tightly?",
                "How will the policy avoid sending a request to an infeasible cluster?",
            ],
        )

    @staticmethod
    def _metrics_response() -> MockAgentResponse:
        return MockAgentResponse(
            topic="metrics",
            message=(
                "The main payoff comes from admitted requests that complete before the "
                "month ends. Useful diagnostics include arrivals, admissions, rejections, "
                "completed revenue, unfinished requests, utilization by cluster, load "
                "imbalance, and high-priority completion rate. Look at these together: "
                "high utilization is good only if it is producing valuable completions."
            ),
            follow_up_questions=[
                "Are unfinished requests large enough to change your policy?",
                "Is revenue concentrated in one request type?",
            ],
        )

    @staticmethod
    def _debugging_response() -> MockAgentResponse:
        return MockAgentResponse(
            topic="debugging",
            message=(
                "When debugging a policy, first check the return value. It should be 0 "
                "for rejection or a valid feasible cluster id. Then test edge cases: no "
                "cluster has enough capacity, exactly one cluster is feasible, multiple "
                "clusters are feasible, and the request has unusually high required "
                "units. Keep the first version simple and compare it against benchmarks."
            ),
            follow_up_questions=[
                "What input caused the invalid or infeasible decision?",
                "Can you reproduce the issue with a tiny hand-written state?",
            ],
        )

    @staticmethod
    def _request_type_response() -> MockAgentResponse:
        return MockAgentResponse(
            topic="request_types",
            message=(
                "Request type matters because different types can have different prices, "
                "resource needs, and service durations. A high-priority or high-price "
                "type may deserve capacity protection, but the policy should still check "
                "whether the request's required units and expected duration make sense "
                "given current capacity."
            ),
            follow_up_questions=[
                "How does each type compare on revenue per required unit?",
                "Would you treat peak months differently from low-demand months?",
            ],
        )

    @staticmethod
    def _general_response() -> MockAgentResponse:
        return MockAgentResponse(
            topic="general",
            message=(
                "A strong approach is to start with a simple feasible benchmark, inspect "
                "which requests it admits or rejects, then add one improvement at a time. "
                "For example, you might first choose the least-loaded feasible cluster, "
                "then add priority logic for valuable request types when capacity becomes "
                "scarce."
            ),
            follow_up_questions=[
                "What decision rule are you currently considering?",
                "Which metric are you trying to improve next?",
            ],
        )


def get_mock_response(user_message: str) -> dict[str, object]:
    """Convenience wrapper for API or dashboard callers."""
    response = MockResourceAllocationAgent().reply(user_message)
    return {
        "message": response.message,
        "topic": response.topic,
        "follow_up_questions": response.follow_up_questions,
    }


if __name__ == "__main__":
    agent = MockResourceAllocationAgent()
    print(DEFAULT_OPENING)
    while True:
        try:
            message = input("\nStudent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting mock assistant.")
            break

        response = agent.reply(message)
        print(f"\nAssistant [{response.topic}]> {response.message}")
        if response.follow_up_questions:
            print("Follow-up questions:")
            for question in response.follow_up_questions:
                print(f"- {question}")
