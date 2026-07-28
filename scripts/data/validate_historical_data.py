"""
Validate generated historical data against the hidden environment.

This Stream A validation script checks data integrity, feasibility, and summary
table consistency. Run it after regenerating historical data.
"""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from backend.app.services.hidden_environment import (
    CLUSTER_CAPACITY,
    DAYS_PER_MONTH,
    HOURS_PER_DAY,
    PRICE_PER_UNIT,
    REQUEST_TYPES,
    SIMULATION_MONTHS,
)


DATA_DIR = Path("data/generated")
HISTORICAL_DATA_PATH = DATA_DIR / "historical_requests.csv"
SUMMARY_BY_MONTH_PATH = DATA_DIR / "summary_by_month.csv"
SUMMARY_BY_TYPE_PATH = DATA_DIR / "summary_by_type.csv"
SUMMARY_BY_MONTH_TYPE_PATH = DATA_DIR / "summary_by_month_type.csv"

REQUIRED_COLUMNS = {
    "request_id",
    "arrival_time",
    "month",
    "day",
    "hour",
    "type",
    "required_units",
    "duration",
    "assigned_cluster",
    "completed",
    "unit_price",
    "revenue",
}


def validate_historical_data() -> None:
    """Validate the generated historical request dataset and summaries."""
    _check_required_files()
    df = pd.read_csv(HISTORICAL_DATA_PATH)

    _check_required_columns(df)
    _check_no_missing_values(df)
    _check_request_ids(df)
    _check_time_fields(df)
    _check_request_types(df)
    _check_positive_fields(df)
    _check_cluster_feasibility(df)
    _check_prices_and_revenue(df)
    _check_summary_tables(df)

    print("Historical data validation passed.")
    print(f"Rows: {len(df):,}")
    print(f"Request types: {', '.join(REQUEST_TYPES)}")
    print(f"Months: 1-{SIMULATION_MONTHS}")
    print("Cluster feasibility violations: 0")
    print("Summary tables match historical_requests.csv.")


def _check_required_files() -> None:
    """Check that all generated CSV files exist."""
    missing_files = [
        path
        for path in [
            HISTORICAL_DATA_PATH,
            SUMMARY_BY_MONTH_PATH,
            SUMMARY_BY_TYPE_PATH,
            SUMMARY_BY_MONTH_TYPE_PATH,
        ]
        if not path.exists()
    ]

    if missing_files:
        missing = ", ".join(str(path) for path in missing_files)
        raise AssertionError(f"Missing generated file(s): {missing}")


def _check_required_columns(df: pd.DataFrame) -> None:
    """Check historical dataset columns."""
    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise AssertionError(
            f"Missing required column(s): {sorted(missing_columns)}"
        )


def _check_no_missing_values(df: pd.DataFrame) -> None:
    """Check that no generated fields are missing."""
    missing_count = int(df[list(REQUIRED_COLUMNS)].isna().sum().sum())
    if missing_count:
        raise AssertionError(f"Found {missing_count} missing value(s).")


def _check_request_ids(df: pd.DataFrame) -> None:
    """Check request id uniqueness."""
    if not df["request_id"].is_unique:
        raise AssertionError("request_id values must be unique.")


def _check_time_fields(df: pd.DataFrame) -> None:
    """Check month, day, hour, and arrival time ranges."""
    _assert_between(df, "month", 1, SIMULATION_MONTHS)
    _assert_between(df, "day", 1, DAYS_PER_MONTH)
    _assert_between(df, "hour", 0, HOURS_PER_DAY - 1)

    min_arrival = 0
    max_arrival = SIMULATION_MONTHS * DAYS_PER_MONTH * HOURS_PER_DAY
    if not df["arrival_time"].between(min_arrival, max_arrival - 1).all():
        raise AssertionError("arrival_time values are outside the valid range.")


def _check_request_types(df: pd.DataFrame) -> None:
    """Check request type values."""
    invalid_types = sorted(set(df["type"]) - set(REQUEST_TYPES))
    if invalid_types:
        raise AssertionError(f"Invalid request type(s): {invalid_types}")


def _check_positive_fields(df: pd.DataFrame) -> None:
    """Check positive required units and durations."""
    if (df["required_units"] <= 0).any():
        raise AssertionError("required_units must be positive.")
    if (df["duration"] <= 0).any():
        raise AssertionError("duration must be positive.")


def _check_cluster_feasibility(df: pd.DataFrame) -> None:
    """Check assigned clusters and whether they can fit each request."""
    valid_clusters = set(CLUSTER_CAPACITY)
    invalid_clusters = sorted(set(df["assigned_cluster"]) - valid_clusters)
    if invalid_clusters:
        raise AssertionError(f"Invalid assigned cluster(s): {invalid_clusters}")

    infeasible = df[
        df.apply(
            lambda row: CLUSTER_CAPACITY[int(row["assigned_cluster"])]
            < int(row["required_units"]),
            axis=1,
        )
    ]
    if not infeasible.empty:
        raise AssertionError(
            f"Found {len(infeasible)} infeasible cluster assignment(s)."
        )


def _check_prices_and_revenue(df: pd.DataFrame) -> None:
    """Check unit prices and realized revenue."""
    expected_prices = df["type"].map(PRICE_PER_UNIT)
    if not (df["unit_price"] == expected_prices).all():
        raise AssertionError("unit_price does not match PRICE_PER_UNIT.")

    expected_revenue = df.apply(
        lambda row: (
            int(row["required_units"]) * int(row["unit_price"])
            if bool(row["completed"])
            else 0
        ),
        axis=1,
    )
    if not (df["revenue"] == expected_revenue).all():
        raise AssertionError("revenue values do not match completion rule.")


def _check_summary_tables(df: pd.DataFrame) -> None:
    """Check generated summary tables against the source dataset."""
    _assert_frame_matches_csv(
        _summary_by_month(df),
        SUMMARY_BY_MONTH_PATH,
        ["month"],
    )
    _assert_frame_matches_csv(
        _summary_by_type(df),
        SUMMARY_BY_TYPE_PATH,
        ["type"],
    )
    _assert_frame_matches_csv(
        _summary_by_month_type(df),
        SUMMARY_BY_MONTH_TYPE_PATH,
        ["month", "type"],
    )


def _summary_by_month(df: pd.DataFrame) -> pd.DataFrame:
    return (
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


def _summary_by_type(df: pd.DataFrame) -> pd.DataFrame:
    return (
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


def _summary_by_month_type(df: pd.DataFrame) -> pd.DataFrame:
    return (
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


def _assert_frame_matches_csv(
    expected: pd.DataFrame,
    csv_path: Path,
    sort_columns: list[str],
) -> None:
    """Compare an expected summary frame against a generated CSV."""
    actual = pd.read_csv(csv_path)
    expected = expected.sort_values(sort_columns).reset_index(drop=True)
    actual = actual.sort_values(sort_columns).reset_index(drop=True)

    try:
        pd.testing.assert_frame_equal(
            actual,
            expected,
            check_dtype=False,
            atol=1e-9,
            rtol=1e-9,
        )
    except AssertionError as exc:
        raise AssertionError(f"{csv_path} does not match source data.") from exc


def _assert_between(
    df: pd.DataFrame,
    column: str,
    lower: int,
    upper: int,
) -> None:
    """Assert that a numeric column lies inside an inclusive range."""
    if not df[column].between(lower, upper).all():
        raise AssertionError(
            f"{column} values must be between {lower} and {upper}."
        )


def main() -> None:
    """Run historical data validation."""
    validate_historical_data()


if __name__ == "__main__":
    main()
