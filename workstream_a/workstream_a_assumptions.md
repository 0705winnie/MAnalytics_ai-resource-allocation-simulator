# Workstream A Assumptions

## Problem formulation

The operational setting is a cloud/AI inference platform that receives capacity requests throughout a simulated year. The platform operates four server clusters. Each incoming request consumes a fixed number of server units for a known service duration if accepted.

The student decision is made request by request: reject the request, or accept it and assign it to one feasible cluster with enough available units for the full service interval.

The objective is to maximize completed payoff over the 12-month simulation horizon. Payoff is earned only for accepted requests that complete before the end of the year. The core tradeoff is opportunity cost: accepting a low-value or long-duration request can block scarce capacity that may be needed later by higher-value requests.

## System setup

| Cluster | Capacity units | Role | Relative duration factor |
|---|---:|---|---:|
| cluster_A | 80 | General GPU capacity | 1.00 |
| cluster_B | 80 | General GPU capacity | 1.00 |
| cluster_C | 48 | Premium low-latency capacity | 0.90 |
| cluster_D | 120 | Batch/spot capacity | 1.15 |

The clusters are intentionally different. This gives students assignment choices beyond a single pooled-capacity decision. The horizon is 12 months and the decision time unit is one hour.

## Request types and prices

| Type | Unit price per occupied hour | Volume | Units | Duration | Design intent |
|---|---:|---|---|---|---|
| VIP | 44 | Low | Largest | Short/medium | High value and capacity-sensitive. |
| standard | 24 | Medium | Medium | Medium | Balanced demand that often fits general clusters. |
| economy | 11 | High | Small/medium | Long | Low value but long occupancy, creating opportunity-cost risk. |

Revenue for a completed request equals `required_units * realized_duration_hours * unit_price_per_hour`.

## Hidden demand environment

Base hourly arrival rates are 0.34 for VIP, 0.86 for standard, and 1.18 for economy. The true generator also includes monthly seasonality, weekday effects, and hour-of-day effects. VIP demand peaks more strongly in November and December, while economy demand is relatively stronger early in the year. Weekday business hours have higher arrival intensity than nights and weekends.

These true parameters are hidden from students. Students receive historical request-level data that reveals patterns statistically without exposing the generator directly.

## Required-unit distributions

VIP requests usually require 16 to 24 units, with occasional 32-unit requests. Standard requests usually require 8 to 16 units. Economy requests usually require 4 to 12 units. These sizes are large enough to matter, but small enough that most requests are feasible when capacity is managed well.

## Service-time distributions

VIP and standard durations are generated from lognormal distributions. Economy durations use a gamma-like distribution with a longer tail. Typical means are about 18 hours for VIP, 28 hours for standard, and 58 hours for economy before cluster speed adjustment. The long economy duration is the main source of opportunity-cost tension.

## Historical-data generation

The historical data was generated separately from the student simulator, using the same request environment and a simple baseline assignment policy. The baseline assigns requests to preferred feasible clusters and rejects only when no feasible cluster is available. This gives students realistic completed/rejected outcomes without making the simulator policy itself deterministic from the dataset.

## Dependencies for later workstreams

Workstream B should use request rows as simulator events. Arrival times can be represented as ISO timestamps or converted to integer hour offsets from the start of the year. Durations should be integer hours, and active jobs should reserve `required_units` on their assigned cluster until release.

Workstream C should show raw data plus summary tables. Recommended dashboard plots are demand by month, demand by type, demand by month and type, required units by type, service duration by type, revenue by type, and completion rate by type. Useful filters are month, request type, required-unit range, duration range, completion status, and assigned cluster.

Workstream D can use this document and the data dictionary as tutorial assumptions. The tutorial should direct students to notice seasonal demand, VIP value concentration, economy duration risk, and the difference between high request volume and high revenue contribution.

## Limitations and extensions

This first version assumes known units and durations at arrival time, no cancellations, no preemption, no queueing, and fixed prices by request type. Later versions could add forecast uncertainty, service-level penalties, stochastic realized durations, dynamic pricing, cluster maintenance outages, or request-specific deadlines.
