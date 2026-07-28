# AI-Assisted Online Resource Allocation Simulator

## 1. Introduction

This project develops an AI-assisted online resource allocation simulator for a
teaching module in operations analysis. The simulator is designed around a
cloud-service setting in which customer requests arrive over time, each request
requires reusable server capacity, and a decision-maker must choose whether to
reject the request or admit it to a feasible server cluster.

The project combines three elements:

- a synthetic but realistic operating environment;
- a historical dataset for students to analyze before making decisions;
- an AI assistant that supports reasoning, policy design, and code debugging
  without revealing hidden simulator parameters.

The central teaching idea is that online decisions have opportunity costs. A
request may be feasible now but still be a poor choice if accepting it blocks
future higher-value work. Students should learn to compare policies, evaluate
tradeoffs, and use AI assistance responsibly as part of an analytical workflow.

## 2. Educational Motivation

Many classroom operations problems are presented as static optimization models.
Those models are valuable, but they can hide the difficulty of making decisions
as information arrives over time. In an online resource allocation problem, the
decision-maker cannot see the future request stream. Each admission decision
changes the available capacity for later arrivals.

This simulator is intended to help students reason about:

- reusable capacity and service completions;
- admission control;
- routing to feasible clusters;
- uncertainty in arrivals and service durations;
- revenue versus service-quality tradeoffs;
- benchmark comparison;
- responsible use of generative AI for modeling and coding.

The goal is not for students to ask an AI tool for a final answer. Instead,
students should use the assistant to interpret historical data, brainstorm
candidate policies, debug code, critique results, and explain why a policy does
or does not perform well.

## 3. Case Narrative

The case represents a cloud or AI-service platform that operates several server
clusters. Customer requests arrive throughout each simulated month. Each request
belongs to one of three classes:

- `VIP`
- `standard`
- `economy`

Each request requires a number of server-capacity units and has a service
duration. If the request is admitted, it occupies capacity on one cluster until
service completion. Once the request departs, that capacity is released and can
be reused by future requests. Revenue is earned only for completed requests.

Students receive historical operating data from a prior simulated year. They use
that data to estimate demand patterns, request mix, capacity needs, service
durations, and revenue tradeoffs. They then design admission and routing
policies and evaluate those policies in a simulator.

## 4. Problem Formulation

The system consists of multiple server clusters. Each cluster has finite
reusable capacity. At each request arrival, the decision-maker observes
student-visible request and system-state information and chooses an action:

```text
0 = reject the request
n = admit the request to cluster n
```

An admission is feasible only if the selected cluster has enough remaining
capacity for the request's required units. If admitted, the request consumes
capacity until its service duration ends. The baseline revenue rule is:

```text
revenue = required_units * unit_price
```

for completed requests. Rejected requests earn zero revenue. Requests that do
not complete within the relevant evaluation period also earn zero realized
revenue under the baseline design.

The objective is to design a policy that performs well over the simulated
horizon. Total revenue is an important metric, but it is not the only diagnostic
of policy quality. The simulator should also report information such as
admission rate, rejection rate, unfinished work, completion rate by request
type, VIP completion rate, utilization, and comparison to benchmark policies.

### Policy Interface

The intended policy shape is:

```python
def admission_policy(request, state, history, params):
    return action
```

where `action` is `0` for rejection or a feasible cluster id for admission.
The final implementation should specify the exact fields available in
`request`, `state`, `history`, and `params`.

## 5. Synthetic Environment Design

The simulator uses a hidden synthetic environment to generate historical data
and future simulation instances. The hidden environment defines request types,
cluster capacity, arrival patterns, required-unit distributions, service-time
patterns, and revenue assumptions.

The environment is designed so that policy choice matters. Request types differ
in value, resource requirement, and duration:

- VIP requests are high-value, more capacity-intensive, and relatively short.
- Standard requests provide steady mid-value demand.
- Economy requests are lower-value and longer-running.

This design creates the core opportunity-cost lesson. Economy requests may be
reasonable to accept when the system has ample capacity, but accepting too many
long-running low-value requests can block future standard or VIP requests. A
strong policy should therefore be value-aware when capacity becomes scarce.

The environment also uses multiple heterogeneous clusters. This makes routing
meaningful because some clusters are better suited for smaller work while larger
clusters preserve feasibility for larger requests. Policies such as first-fit,
least-loaded, best-fit, and value-aware routing can therefore produce different
outcomes.

Exact hidden parameter values should not be revealed to students. Students
should infer useful patterns from historical data, plots, and simulation
feedback.

## 6. Historical Dataset

The historical dataset represents one prior simulated year of request-level
operations. Each row corresponds to one request and includes:

- request id;
- arrival time;
- month, day, and hour;
- request type;
- required units;
- observed service duration;
- historical cluster assignment;
- completion status;
- unit price;
- realized revenue.

The dataset is meant to be small enough for classroom use while still rich
enough to support analysis. Students can inspect seasonality, request mix,
required units, service duration patterns, completion rates, and revenue
differences across request types.

The generated summary tables aggregate the historical data by month, by request
type, and by month/request type. These summaries support dashboard views and
student interpretation.

## 7. Validation And Calibration

The data-generation process includes validation checks to make sure the
historical dataset is internally consistent. The validation checks confirm that:

- required files and columns exist;
- there are no missing generated values;
- request ids are unique;
- month, day, hour, and arrival-time fields are valid;
- request types are valid;
- required units and durations are positive;
- historical cluster assignments are feasible;
- unit prices match request types;
- realized revenue follows the completion rule;
- summary tables match the request-level dataset.

The environment is also calibrated with simple internal policies. This
calibration is not the final simulator evaluation; it is a design check to
confirm that the hidden environment creates meaningful policy tradeoffs.

### Calibration Policies

The calibration uses six simple policies:

| Policy | Description |
|---|---|
| Always reject | Rejects every request. This is a sanity check and should earn zero revenue. |
| First-fit | Admits a request to the lowest-numbered feasible cluster. |
| Least-loaded | Admits a request to the feasible cluster with the most remaining capacity. |
| Best-fit | Admits a request to the feasible cluster that leaves the least unused capacity after admission. |
| VIP-only | Admits only VIP requests and rejects all standard and economy requests. |
| VIP-priority | Uses capacity-aware priority rules: it protects capacity for VIP requests when capacity is scarce, but still admits standard and economy requests when capacity is available. |

### Calibration Results

The table below reports averages across five random seeds. Revenue is total
simulated revenue over the year. `rev_sd` is the standard deviation of revenue
across seeds. `admit%` is the fraction of arrivals admitted. `rejects` is the
average number of rejected requests. `unfinished` is the average number of
admitted requests that do not finish before the end of their simulated month.
`vip_complete%` is the fraction of VIP arrivals that complete.

| Policy | Average Revenue | Revenue SD | Admission Rate | Rejections | Unfinished | VIP Completion |
|---|---:|---:|---:|---:|---:|---:|
| Always reject | 0 | 0 | 0.0% | 11,910 | 0 | 0.0% |
| First-fit | 564,501 | 7,896 | 89.5% | 1,256 | 194 | 62.8% |
| Least-loaded | 456,161 | 6,868 | 83.8% | 1,927 | 189 | 32.5% |
| Best-fit | 581,287 | 9,738 | 90.7% | 1,103 | 196 | 66.4% |
| VIP-only | 258,166 | 5,523 | 11.3% | 10,567 | 8 | 99.4% |
| VIP-priority | 630,525 | 9,237 | 80.8% | 2,281 | 152 | 89.1% |

These results show the intended qualitative behavior. Always reject earns no
revenue. Simple routing policies differ from one another, which means routing
and capacity fragmentation matter. VIP-only protects VIP requests but earns much
less revenue because it rejects too much standard and economy demand.
VIP-priority performs best among these calibration policies because it protects
scarce capacity while still using available capacity for other work. This
supports the desired lesson: the best policy is not simply "serve only VIP"; it
is to make value-aware capacity decisions.

## 8. AI Assistant Design

The AI assistant is designed to support the student's analytical workflow. It
can help students:

- understand the resource allocation problem;
- interpret visible historical data;
- brainstorm admission and routing policies;
- translate policy ideas into pseudocode or code;
- debug policy code;
- compare policies against benchmarks;
- reflect on tradeoffs in simulation feedback.

The assistant has explicit guardrails. It must not reveal hidden simulator
parameters, future simulation data, private evaluation seeds, or other students'
submissions. If a student asks for hidden information, the assistant should
refuse that part of the request and redirect the student toward historical data,
observable feedback, or benchmark testing.

The assistant supports two modes:

- a mock mode that provides deterministic fallback responses without an API key;
- an API-backed mode that can use a configured language model.

The mock mode is useful for development, demonstrations, and environments where
API access is unavailable. The API-backed mode is intended for richer coding and
debugging support. API keys should be stored locally or in backend deployment
secrets and should never be committed to source control.

## 9. Limitations And Future Extensions

The current environment is synthetic by design. This makes the case
reproducible, compact enough for classroom use, and easier to tune toward
specific learning objectives. The tradeoff is that the generated data should be
interpreted as a teaching case rather than as a direct production trace from a
real cloud platform.

Another limitation is the separation between student-visible data and hidden
simulation logic. The exercise depends on preserving that separation. Students
can reasonably infer demand patterns, service-duration differences, and revenue
tradeoffs from historical data, but exact arrival rates, distribution
parameters, future request streams, and private evaluation seeds should remain
unavailable during the activity.

Future extensions could make the simulator richer while preserving the same
core learning objective. Possible extensions include additional request classes,
more observable request features, carryover of unfinished work across months,
more detailed cost models, and richer benchmark policies.
