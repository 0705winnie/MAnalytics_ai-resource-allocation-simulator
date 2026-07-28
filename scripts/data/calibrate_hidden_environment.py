"""
Calibrate hidden-environment parameters with simple internal policies.

This script is a Stream A diagnostic tool. It is not the official Stream B
simulator and should not be exposed to students. Its purpose is to check whether
the hidden environment creates meaningful tradeoffs across simple policies.
"""

from __future__ import annotations

import heapq
from pathlib import Path
import sys
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, stdev
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from backend.app.services.hidden_environment import (
    BASE_MONTHLY_ARRIVALS,
    CLUSTER_CAPACITY,
    DAYS_PER_MONTH,
    DEFAULT_RANDOM_SEED,
    MEAN_SERVICE_DURATION,
    MONTHLY_MULTIPLIER,
    PRICE_PER_UNIT,
    REQUIRED_UNITS_DISTRIBUTION,
    REQUEST_TYPES,
    SERVICE_DURATION_GAMMA_SHAPE,
    SIMULATION_MONTHS,
    TYPE_MONTHLY_MULTIPLIER,
)


HOURS_PER_MONTH = DAYS_PER_MONTH * 24
CALIBRATION_SEEDS = tuple(range(DEFAULT_RANDOM_SEED, DEFAULT_RANDOM_SEED + 5))


@dataclass(frozen=True)
class Request:
    """Request sampled from the hidden environment."""

    arrival_time: float
    request_type: str
    required_units: int
    duration: float


@dataclass
class PolicyMetrics:
    """Summary metrics for one policy run."""

    revenue: int = 0
    arrivals: int = 0
    admissions: int = 0
    rejections: int = 0
    unfinished: int = 0
    completions_by_type: dict[str, int] | None = None
    arrivals_by_type: dict[str, int] | None = None
    revenue_by_type: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.completions_by_type is None:
            self.completions_by_type = defaultdict(int)
        if self.arrivals_by_type is None:
            self.arrivals_by_type = defaultdict(int)
        if self.revenue_by_type is None:
            self.revenue_by_type = defaultdict(int)

    @property
    def admission_rate(self) -> float:
        return self.admissions / self.arrivals if self.arrivals else 0.0

    @property
    def vip_completion_rate(self) -> float:
        vip_arrivals = self.arrivals_by_type["VIP"]
        return (
            self.completions_by_type["VIP"] / vip_arrivals
            if vip_arrivals
            else 0.0
        )


Policy = Callable[[Request, dict[int, int]], int]


def sample_required_units(request_type: str, rng: np.random.Generator) -> int:
    """Sample required units for a request type."""
    distribution = REQUIRED_UNITS_DISTRIBUTION[request_type]
    return int(
        rng.choice(
            distribution["values"],
            p=distribution["probabilities"],
        )
    )


def sample_duration(request_type: str, rng: np.random.Generator) -> float:
    """Sample service duration for a request type."""
    mean_duration = MEAN_SERVICE_DURATION[request_type]
    scale = mean_duration / SERVICE_DURATION_GAMMA_SHAPE
    return float(rng.gamma(SERVICE_DURATION_GAMMA_SHAPE, scale))


def generate_month_requests(
    month: int,
    rng: np.random.Generator,
) -> list[Request]:
    """Generate one month of requests from the hidden environment."""
    requests = []

    for request_type in REQUEST_TYPES:
        expected_arrivals = (
            BASE_MONTHLY_ARRIVALS[request_type]
            * MONTHLY_MULTIPLIER[month]
            * TYPE_MONTHLY_MULTIPLIER[request_type][month]
        )
        num_arrivals = rng.poisson(expected_arrivals)

        for _ in range(num_arrivals):
            requests.append(
                Request(
                    arrival_time=float(rng.uniform(0, HOURS_PER_MONTH)),
                    request_type=request_type,
                    required_units=sample_required_units(request_type, rng),
                    duration=sample_duration(request_type, rng),
                )
            )

    return sorted(requests, key=lambda request: request.arrival_time)


def always_reject_policy(
    request: Request,
    remaining_capacity: dict[int, int],
) -> int:
    """Reject every request."""
    return 0


def first_fit_policy(
    request: Request,
    remaining_capacity: dict[int, int],
) -> int:
    """Admit to the lowest-id feasible cluster."""
    for cluster_id in sorted(remaining_capacity):
        if remaining_capacity[cluster_id] >= request.required_units:
            return cluster_id
    return 0


def least_loaded_policy(
    request: Request,
    remaining_capacity: dict[int, int],
) -> int:
    """Admit to the feasible cluster with the most remaining capacity."""
    feasible_clusters = _feasible_clusters(request, remaining_capacity)
    if not feasible_clusters:
        return 0
    return max(feasible_clusters, key=lambda cluster: remaining_capacity[cluster])


def best_fit_policy(
    request: Request,
    remaining_capacity: dict[int, int],
) -> int:
    """Admit to the feasible cluster with the least leftover capacity."""
    feasible_clusters = _feasible_clusters(request, remaining_capacity)
    if not feasible_clusters:
        return 0
    return min(
        feasible_clusters,
        key=lambda cluster: remaining_capacity[cluster] - request.required_units,
    )


def vip_priority_policy(
    request: Request,
    remaining_capacity: dict[int, int],
) -> int:
    """Reject low-value work when capacity is scarce, then best-fit."""
    total_remaining = sum(remaining_capacity.values())
    if request.request_type == "economy" and total_remaining < 65:
        return 0
    if request.request_type == "standard" and total_remaining < 35:
        return 0
    return best_fit_policy(request, remaining_capacity)


def vip_only_policy(
    request: Request,
    remaining_capacity: dict[int, int],
) -> int:
    """Admit only VIP requests, then route them with best-fit."""
    if request.request_type != "VIP":
        return 0
    return best_fit_policy(request, remaining_capacity)


def run_policy(policy: Policy, seed: int = DEFAULT_RANDOM_SEED) -> PolicyMetrics:
    """Run a policy over all simulated months and return aggregate metrics."""
    rng = np.random.default_rng(seed)
    metrics = PolicyMetrics()

    for month in range(1, SIMULATION_MONTHS + 1):
        remaining_capacity = dict(CLUSTER_CAPACITY)
        departures: list[tuple[float, int, int]] = []

        for request in generate_month_requests(month, rng):
            metrics.arrivals += 1
            metrics.arrivals_by_type[request.request_type] += 1

            _release_departed_jobs(
                departures,
                request.arrival_time,
                remaining_capacity,
            )

            selected_cluster = policy(request, remaining_capacity)
            if not _is_feasible(selected_cluster, request, remaining_capacity):
                metrics.rejections += 1
                continue

            metrics.admissions += 1
            remaining_capacity[selected_cluster] -= request.required_units

            departure_time = request.arrival_time + request.duration
            heapq.heappush(
                departures,
                (departure_time, selected_cluster, request.required_units),
            )

            if departure_time <= HOURS_PER_MONTH:
                request_revenue = (
                    request.required_units
                    * PRICE_PER_UNIT[request.request_type]
                )
                metrics.revenue += request_revenue
                metrics.revenue_by_type[request.request_type] += request_revenue
                metrics.completions_by_type[request.request_type] += 1
            else:
                metrics.unfinished += 1

    return metrics


def _release_departed_jobs(
    departures: list[tuple[float, int, int]],
    current_time: float,
    remaining_capacity: dict[int, int],
) -> None:
    """Release capacity for jobs completed by current_time."""
    while departures and departures[0][0] <= current_time:
        _, cluster_id, required_units = heapq.heappop(departures)
        remaining_capacity[cluster_id] += required_units


def _feasible_clusters(
    request: Request,
    remaining_capacity: dict[int, int],
) -> list[int]:
    """Return all clusters that can fit the request."""
    return [
        cluster_id
        for cluster_id, capacity in remaining_capacity.items()
        if capacity >= request.required_units
    ]


def _is_feasible(
    cluster_id: int,
    request: Request,
    remaining_capacity: dict[int, int],
) -> bool:
    """Return whether the selected cluster can admit the request."""
    return (
        cluster_id in remaining_capacity
        and remaining_capacity[cluster_id] >= request.required_units
    )


def print_calibration_report() -> None:
    """Print benchmark-like results for hidden-environment calibration."""
    policies: dict[str, Policy] = {
        "always_reject": always_reject_policy,
        "first_fit": first_fit_policy,
        "least_loaded": least_loaded_policy,
        "best_fit": best_fit_policy,
        "vip_only": vip_only_policy,
        "vip_priority": vip_priority_policy,
    }

    print("Hidden Environment Calibration")
    print("=" * 80)
    print(f"Clusters: {len(CLUSTER_CAPACITY)}")
    print(f"Total capacity units: {sum(CLUSTER_CAPACITY.values())}")
    print(f"Seeds: {CALIBRATION_SEEDS[0]}-{CALIBRATION_SEEDS[-1]}")
    print()
    print(
        f"{'policy':<16} {'avg_revenue':>12} {'rev_sd':>10} "
        f"{'admit%':>8} {'rejects':>9} {'unfinished':>10} "
        f"{'vip_complete%':>14}"
    )
    print("-" * 80)

    for policy_name, policy in policies.items():
        runs = [run_policy(policy, seed=seed) for seed in CALIBRATION_SEEDS]
        print(
            f"{policy_name:<16} "
            f"{mean(run.revenue for run in runs):>12,.0f} "
            f"{_sample_stdev(run.revenue for run in runs):>10,.0f} "
            f"{mean(run.admission_rate for run in runs):>7.1%} "
            f"{mean(run.rejections for run in runs):>9,.0f} "
            f"{mean(run.unfinished for run in runs):>10,.0f} "
            f"{mean(run.vip_completion_rate for run in runs):>13.1%}"
        )


def _sample_stdev(values: object) -> float:
    """Return sample standard deviation, or 0 for a single value."""
    value_list = list(values)
    return stdev(value_list) if len(value_list) > 1 else 0.0


def main() -> None:
    """Run calibration diagnostics."""
    print_calibration_report()


if __name__ == "__main__":
    main()
