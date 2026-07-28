# Data Dictionary

This dictionary describes the generated historical dataset used by students to
study the resource allocation case. The dataset is generated from hidden
environment assumptions, but the hidden parameter values are not included here.

## Historical Requests

File: `data/generated/historical_requests.csv`

Each row represents one historical customer request.

| Column | Type | Student-visible | Meaning |
|---|---|---:|---|
| `request_id` | integer | Yes | Unique identifier for the request. |
| `arrival_time` | integer | Yes | Hour index from the start of the simulated year. |
| `month` | integer | Yes | Month number, from 1 to 12. |
| `day` | integer | Yes | Day within the month, from 1 to 30. |
| `hour` | integer | Yes | Hour of day, from 0 to 23. |
| `type` | string | Yes | Request class: `VIP`, `standard`, or `economy`. |
| `required_units` | integer | Yes | Number of server-capacity units needed while the request is active. |
| `duration` | float | Yes | Observed service duration in hours. |
| `assigned_cluster` | integer | Yes | Cluster used in the historical operation. |
| `completed` | boolean | Yes | Whether the request completed in the historical operation. |
| `unit_price` | integer | Yes | Revenue per required unit for the request type. |
| `revenue` | integer | Yes | Realized revenue. This is positive only for completed requests. |

## Summary Tables

The generated summary tables are derived from `historical_requests.csv`.

### `data/generated/summary_by_month.csv`

| Column | Meaning |
|---|---|
| `month` | Month number. |
| `total_requests` | Number of historical requests in the month. |
| `completed_requests` | Number of requests completed in the month. |
| `total_revenue` | Total realized revenue in the month. |
| `avg_required_units` | Average required units for requests in the month. |
| `avg_duration` | Average service duration for requests in the month. |

### `data/generated/summary_by_type.csv`

| Column | Meaning |
|---|---|
| `type` | Request class. |
| `total_requests` | Number of historical requests of that type. |
| `completed_requests` | Number of completed historical requests of that type. |
| `completion_rate` | Fraction of requests of that type that completed. |
| `total_revenue` | Total realized revenue for that request type. |
| `avg_revenue` | Average realized revenue per request of that type. |
| `avg_required_units` | Average required units for that request type. |
| `avg_duration` | Average service duration for that request type. |

### `data/generated/summary_by_month_type.csv`

| Column | Meaning |
|---|---|
| `month` | Month number. |
| `type` | Request class. |
| `total_requests` | Number of historical requests for that month and type. |
| `completed_requests` | Number of completed requests for that month and type. |
| `total_revenue` | Total realized revenue for that month and type. |
| `avg_required_units` | Average required units for that month and type. |
| `avg_duration` | Average service duration for that month and type. |

## Notes For Students

- The historical data is meant to support estimation and policy design. It does
  not reveal the hidden simulator parameters directly.
- `required_units` and `duration` are important for understanding opportunity
  cost: a request can be valuable, but it also occupies reusable capacity while
  active.
- `revenue` is earned only when a request is completed.
- A good policy should consider request value, capacity usage, service duration,
  and the possibility of future high-value arrivals.
