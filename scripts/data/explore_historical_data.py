"""
Explore the synthetic historical dataset.

This script reads the generated historical request-level dataset,
prints basic validation summaries, and saves exploratory plots for
dashboard/report use.
"""

import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(Path("outputs/.matplotlib-cache")))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


DATA_PATH = Path("data/generated/historical_requests.csv")
OUTPUT_DIR = Path("outputs/figures")


def load_data() -> pd.DataFrame:
    """Load the generated historical requests dataset."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {DATA_PATH}. "
            "Run `python scripts/data/generate_historical_data.py` first."
        )

    return pd.read_csv(DATA_PATH)


def print_basic_summary(df: pd.DataFrame) -> None:
    """Print basic dataset checks and summary statistics."""
    print("Dataset shape:")
    print(df.shape)
    print()

    print("First five rows:")
    print(df.head())
    print()

    print("Missing values:")
    print(df.isna().sum())
    print()

    print("Requests by type:")
    print(df["type"].value_counts())
    print()

    print("Requests by month:")
    print(df.groupby("month").size())
    print()

    print("Average required units, duration, and revenue by type:")
    print(df.groupby("type")[["required_units", "duration", "revenue"]].mean())
    print()

    print("Completion rate by type:")
    print(df.groupby("type")["completed"].mean())
    print()


def save_requests_by_month(df: pd.DataFrame) -> None:
    """Save bar chart of total requests by month."""
    requests_by_month = df.groupby("month").size()

    plt.figure(figsize=(9, 5))
    requests_by_month.plot(kind="bar")
    plt.title("Historical Requests by Month")
    plt.xlabel("Month")
    plt.ylabel("Number of Requests")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "requests_by_month.png", dpi=300)
    plt.close()


def save_requests_by_type(df: pd.DataFrame) -> None:
    """Save bar chart of total requests by request type."""
    requests_by_type = df["type"].value_counts()

    plt.figure(figsize=(7, 5))
    requests_by_type.plot(kind="bar")
    plt.title("Historical Requests by Type")
    plt.xlabel("Request Type")
    plt.ylabel("Number of Requests")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "requests_by_type.png", dpi=300)
    plt.close()


def save_requests_by_month_type(df: pd.DataFrame) -> None:
    """Save line chart of requests by month and request type."""
    month_type_counts = (
        df.groupby(["month", "type"])
        .size()
        .reset_index(name="requests")
    )

    pivot = month_type_counts.pivot(
        index="month",
        columns="type",
        values="requests",
    )

    plt.figure(figsize=(9, 5))
    pivot.plot(marker="o")
    plt.title("Historical Requests by Month and Type")
    plt.xlabel("Month")
    plt.ylabel("Number of Requests")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "requests_by_month_type.png", dpi=300)
    plt.close()


def save_duration_by_type(df: pd.DataFrame) -> None:
    """Save boxplot of service duration by request type."""
    plt.figure(figsize=(8, 5))
    df.boxplot(column="duration", by="type")
    plt.title("Service Duration by Request Type")
    plt.suptitle("")
    plt.xlabel("Request Type")
    plt.ylabel("Duration (hours)")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "duration_by_type.png", dpi=300)
    plt.close()


def save_required_units_by_type(df: pd.DataFrame) -> None:
    """Save boxplot of required server units by request type."""
    plt.figure(figsize=(8, 5))
    df.boxplot(column="required_units", by="type")
    plt.title("Required Server Units by Request Type")
    plt.suptitle("")
    plt.xlabel("Request Type")
    plt.ylabel("Required Server Units")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "required_units_by_type.png", dpi=300)
    plt.close()


def save_revenue_by_type(df: pd.DataFrame) -> None:
    """Save bar chart of total revenue by request type."""
    revenue_by_type = df.groupby("type")["revenue"].sum().sort_values(ascending=False)

    plt.figure(figsize=(7, 5))
    revenue_by_type.plot(kind="bar")
    plt.title("Total Historical Revenue by Request Type")
    plt.xlabel("Request Type")
    plt.ylabel("Total Revenue")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "revenue_by_type.png", dpi=300)
    plt.close()


def save_completion_rate_by_type(df: pd.DataFrame) -> None:
    """Save bar chart of completion rate by request type."""
    completion_by_type = df.groupby("type")["completed"].mean().sort_values(ascending=False)

    plt.figure(figsize=(7, 5))
    completion_by_type.plot(kind="bar")
    plt.title("Historical Completion Rate by Request Type")
    plt.xlabel("Request Type")
    plt.ylabel("Completion Rate")
    plt.ylim(0, 1)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "completion_rate_by_type.png", dpi=300)
    plt.close()


def save_all_plots(df: pd.DataFrame) -> None:
    """Generate and save all exploratory plots."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    save_requests_by_month(df)
    save_requests_by_type(df)
    save_requests_by_month_type(df)
    save_duration_by_type(df)
    save_required_units_by_type(df)
    save_revenue_by_type(df)
    save_completion_rate_by_type(df)

    print(f"Saved plots to {OUTPUT_DIR}")


def main() -> None:
    """Run historical data exploration."""
    df = load_data()
    print_basic_summary(df)
    save_all_plots(df)


if __name__ == "__main__":
    main()
