"""
Generate a synthetic historical request-level dataset for the resource allocation case.

This script creates "last year's" operating data for students to inspect.
The hidden parameters come from backend/app/services/hidden_environment.py.
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from backend.app.services.hidden_environment import (
    REQUEST_TYPES,
    PRICE_PER_UNIT,
    CLUSTER_CAPACITY,
    SIMULATION_MONTHS,
    DAYS_PER_MONTH,
    HOURS_PER_DAY,
    BASE_MONTHLY_ARRIVALS,
    MONTHLY_MULTIPLIER,
    TYPE_MONTHLY_MULTIPLIER,
    REQUIRED_UNITS_DISTRIBUTION,
    MEAN_SERVICE_DURATION,
    SERVICE_DURATION_GAMMA_SHAPE,
    HISTORICAL_COMPLETION_PROBABILITY,
    DEFAULT_RANDOM_SEED,
)


def sample_required_units(request_type: str, rng: np.random.Generator) -> int:
    """Sample the number of server units required by a request."""
    distribution = REQUIRED_UNITS_DISTRIBUTION[request_type]

    return int(
        rng.choice(
            distribution["values"],
            p=distribution["probabilities"],
        )
    )


def sample_service_duration(request_type: str, rng: np.random.Generator) -> float:
    """Sample service duration in hours for a request."""
    mean_duration = MEAN_SERVICE_DURATION[request_type]
    shape = SERVICE_DURATION_GAMMA_SHAPE
    scale = mean_duration / shape

    return float(rng.gamma(shape=shape, scale=scale))


def sample_assigned_cluster(required_units: int, rng: np.random.Generator) -> int:
    """Sample a historical cluster that could feasibly fit the request."""
    feasible_clusters = [
        cluster_id
        for cluster_id, capacity in CLUSTER_CAPACITY.items()
        if capacity >= required_units
    ]

    if not feasible_clusters:
        raise ValueError(
            f"No cluster can fit a request requiring {required_units} units."
        )

    return int(rng.choice(feasible_clusters))


def generate_historical_requests(seed: int = DEFAULT_RANDOM_SEED) -> pd.DataFrame:
    """Generate one year of synthetic historical request data."""
    rng = np.random.default_rng(seed)

    rows = []
    request_id = 1

    for month in range(1, SIMULATION_MONTHS + 1):
        for request_type in REQUEST_TYPES:
            expected_arrivals = (
                BASE_MONTHLY_ARRIVALS[request_type]
                * MONTHLY_MULTIPLIER[month]
                * TYPE_MONTHLY_MULTIPLIER[request_type][month]
            )

            num_arrivals = rng.poisson(expected_arrivals)

            for _ in range(num_arrivals):
                day = int(rng.integers(1, DAYS_PER_MONTH + 1))
                hour = int(rng.integers(0, HOURS_PER_DAY))

                arrival_time = (
                    (month - 1) * DAYS_PER_MONTH * HOURS_PER_DAY
                    + (day - 1) * HOURS_PER_DAY
                    + hour
                )

                required_units = sample_required_units(request_type, rng)
                duration = sample_service_duration(request_type, rng)

                completed = bool(
                    rng.random()
                    < HISTORICAL_COMPLETION_PROBABILITY[request_type]
                )

                unit_price = PRICE_PER_UNIT[request_type]
                revenue = required_units * unit_price if completed else 0

                row = {
                    "request_id": request_id,
                    "arrival_time": arrival_time,
                    "month": month,
                    "day": day,
                    "hour": hour,
                    "type": request_type,
                    "required_units": required_units,
                    "duration": round(duration, 3),
                    "assigned_cluster": sample_assigned_cluster(
                        required_units,
                        rng,
                    ),
                    "completed": completed,
                    "unit_price": unit_price,
                    "revenue": revenue,
                }

                rows.append(row)
                request_id += 1

    df = pd.DataFrame(rows)
    df = df.sort_values("arrival_time").reset_index(drop=True)

    return df


def create_summary_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Create summary tables for dashboard and report use."""
    summary_by_month = (
        df.groupby("month")
        .agg(
            total_requests=("request_id", "count"),
            completed_requests=("completed", "sum"),
            total_revenue=("revenue", "sum"),
            avg_required_units=("required_units", "mean"),
            avg_duration=("duration", "mean"),
        )
        .reset_index()
    )

    summary_by_type = (
        df.groupby("type")
        .agg(
            total_requests=("request_id", "count"),
            completed_requests=("completed", "sum"),
            completion_rate=("completed", "mean"),
            total_revenue=("revenue", "sum"),
            avg_revenue=("revenue", "mean"),
            avg_required_units=("required_units", "mean"),
            avg_duration=("duration", "mean"),
        )
        .reset_index()
    )

    summary_by_month_type = (
        df.groupby(["month", "type"])
        .agg(
            total_requests=("request_id", "count"),
            completed_requests=("completed", "sum"),
            total_revenue=("revenue", "sum"),
            avg_required_units=("required_units", "mean"),
            avg_duration=("duration", "mean"),
        )
        .reset_index()
    )

    return {
        "summary_by_month": summary_by_month,
        "summary_by_type": summary_by_type,
        "summary_by_month_type": summary_by_month_type,
    }


def main() -> None:
    """Generate and save historical dataset and summary tables."""
    output_dir = Path("data/generated")
    output_dir.mkdir(parents=True, exist_ok=True)

    df = generate_historical_requests()
    df.to_csv(output_dir / "historical_requests.csv", index=False)

    summaries = create_summary_tables(df)

    for name, table in summaries.items():
        table.to_csv(output_dir / f"{name}.csv", index=False)

    print("Generated synthetic historical dataset.")
    print(f"Rows: {len(df)}")
    print(f"Saved to: {output_dir / 'historical_requests.csv'}")
    print()
    print("Requests by type:")
    print(df["type"].value_counts())
    print()
    print("Average duration by type:")
    print(df.groupby("type")["duration"].mean())
    print()
    print("Total revenue by type:")
    print(df.groupby("type")["revenue"].sum())


if __name__ == "__main__":
    main()
