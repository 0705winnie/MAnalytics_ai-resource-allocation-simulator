# Workstream A Validation Summary

Generated with deterministic seed `20260617`.

| Check | Result |
|---|---|
| Total requests | 20348 |
| Invalid month/day/hour rows | 0 |
| Nonpositive duration rows | 0 |
| Nonpositive required-unit rows | 0 |
| Negative revenue rows | 0 |
| Completed requests | 10026 |
| Capacity rejections | 10275 |
| Accepted but not completed by year end | 47 |

## Type-level summary

| Type | Requests | Avg units | Avg duration hours | Completion rate | Completed revenue |
|---|---:|---:|---:|---:|---:|
| VIP | 3065 | 18.82 | 17.46 | 0.205 | 7690144.00 |
| standard | 7360 | 10.56 | 28.21 | 0.464 | 19679424.00 |
| economy | 9923 | 6.43 | 58.05 | 0.603 | 19268436.00 |

## Pattern checks

Demand is higher during business hours than overnight, lower on weekends than weekdays, and seasonally strongest late in the year for VIP and standard demand. Economy requests are more numerous, lower value per unit-hour, and longer in duration, which creates the intended blocking tradeoff.
