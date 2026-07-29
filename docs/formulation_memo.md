# Formulation Memo

This memo summarizes the Stream A problem formulation and hidden-environment
design for the AI-assisted online resource allocation simulator. It is written
for project contributors and instructors. Student-facing materials should use
the case narrative and data dictionary without exposing hidden implementation
details.

## Teaching Goal

The simulator is designed to teach online resource allocation with reusable
capacity. Students should learn that a request can be feasible now but still be
a poor decision if it blocks future high-value work. Different admission and
routing policies should create visibly different outcomes in revenue, rejection
rate, completion rate, VIP service, unfinished work, and utilization.

## System Setting

The platform operates several server clusters. Each cluster has a fixed amount
of reusable capacity. Customer requests arrive over time. A request has:

- a request type;
- an arrival time;
- a required number of server-capacity units;
- a service duration;
- a price per required unit.

If a request is admitted, it occupies capacity in one cluster until service
completion. Once it departs, the capacity is released and can be reused. Revenue
is earned only for completed requests.

## Request Types

The generated case uses three request types:

- `VIP`
- `standard`
- `economy`

The types are intentionally different. VIP requests are high-value and more
capacity-intensive, standard requests provide steady mid-value demand, and
economy requests are lower-value but longer-running. This creates an opportunity
cost: accepting too much lower-value long work can reduce capacity available for
future higher-value requests.

## Capacity Design

The environment uses multiple heterogeneous clusters rather than a small number
of identical clusters. This makes routing meaningful:

- smaller clusters are useful for smaller requests;
- larger clusters preserve feasibility for high-unit requests;
- first-fit, least-loaded, best-fit, and priority policies can behave
  differently.

The cluster capacities are hidden implementation details. Students should see
the public system description and historical data, but not the source file that
defines the exact hidden environment.

## Arrival And Seasonality Design

Arrivals vary by month to create peak and trough periods. Request types also
have different seasonal patterns. This is intended to make historical-data
analysis useful: students can look for demand seasonality and type mix before
designing a policy.

Students should not be shown the true arrival-rate parameters. They should infer
patterns from `historical_requests.csv`, summary tables, plots, and simulation
feedback.

## Required Units And Duration Design

Each request requires a random number of capacity units. Each admitted request
also has a random service duration. These distributions are type-specific:

- VIP requests tend to require more units but have shorter service durations.
- Standard requests have moderate unit requirements and moderate durations.
- Economy requests require fewer units on average but have much longer service
  durations.

The long duration of economy requests is deliberate. It makes "accept every
feasible request" less attractive during scarce-capacity periods and helps
students see opportunity cost.

## Revenue Design

Revenue is calculated as:

```text
revenue = required_units * unit_price
```

for completed requests. Requests that are not completed earn zero realized
revenue in the generated historical data. The simulator should use the same
basic logic unless Stream B intentionally extends the payoff model.

## Historical Data

Stream A generates a compact historical request-level dataset for students to
inspect. The public dataset includes:

- time fields;
- request type;
- required units;
- observed duration;
- historical cluster assignment;
- completion status;
- unit price;
- realized revenue.

The historical dataset is meant to reveal broad patterns without exposing exact
hidden parameters. The data dictionary in `docs/data_dictionary.md` describes
the student-visible fields.

## Validation

`scripts/data/validate_historical_data.py` checks that generated data is internally
consistent. It validates required files, required columns, missing values,
request ids, time ranges, request types, positive units and durations, cluster
assignment feasibility, price consistency, revenue rules, and summary-table
consistency.

## Calibration

`scripts/data/calibrate_hidden_environment.py` is a Stream A diagnostic tool. It is
not the official Stream B simulator. It runs simple internal policies against
the hidden environment to check that the parameter choices create meaningful
tradeoffs.

The calibration policies include:

- always reject;
- first-fit;
- least-loaded;
- best-fit;
- VIP-priority.

Good calibration output should show that:

- always reject earns zero revenue;
- simple routing policies do not all perform the same;
- routing and packing decisions affect revenue;
- value-aware capacity protection improves VIP completion;
- higher revenue can come with more rejections.

This confirms that the environment supports the intended lesson: policy design
matters.

## Hidden Versus Student-Visible

Student-visible:

- generated historical dataset;
- summary tables;
- exploratory plots;
- public case narrative;
- policy interface once Stream B finalizes it;
- simulation feedback once Stream B/C expose it.

Hidden from students:

- exact arrival-rate parameters;
- exact seasonality multipliers;
- exact service-duration distributions;
- exact required-unit probabilities;
- future simulation request streams;
- private evaluation seeds.

Students should be able to infer useful patterns from data, but they should not
receive the hidden implementation values directly.
