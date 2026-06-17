# Workstream A Data Dictionary

## Historical dataset

File: `synthetic_historical_requests.csv`

| Column | Student-facing? | Meaning |
|---|---:|---|
| `request_id` | Yes | Unique request identifier. |
| `arrival_time` | Yes | ISO-8601 UTC timestamp when the request arrives. The simulator can convert this to an hour index. |
| `month` | Yes | Month number from 1 to 12, derived from `arrival_time`. |
| `day` | Yes | Day of month, derived from `arrival_time`. |
| `hour` | Yes | Hour of day from 0 to 23, derived from `arrival_time`. |
| `day_of_week` | Yes | Day label used for exploratory analysis. |
| `request_type` | Yes | Customer class: `VIP`, `standard`, or `economy`. |
| `required_units` | Yes | Server units/GPU slots needed simultaneously while the request is in service. |
| `duration_hours` | Yes | Number of hours the request occupies capacity if accepted. |
| `completion_status` | Yes | Historical outcome under the baseline policy: `completed`, `rejected_capacity`, or `accepted_not_completed_by_year_end`. |
| `assigned_cluster` | Yes | Cluster assigned by the baseline policy. Blank means rejected. |
| `revenue` | Yes | Realized payoff for completed requests only. Rejected or unfinished requests have zero realized revenue. |

## Hidden generator fields

These parameters are intentionally not included as columns in the student-facing dataset: true arrival rates, seasonality multipliers, hour/day multipliers, required-unit probabilities, service-time distribution parameters, cluster preference ordering, and the baseline assignment heuristic.

## Simulator-facing interpretation

The simulator should read each row as one arriving request. At decision time, the student sees at least `arrival_time`, `request_type`, `required_units`, and `duration_hours`. The simulator evaluates whether an accept-and-assign decision fits currently available cluster capacity and awards revenue only when an accepted job completes before the end of the simulated year.
