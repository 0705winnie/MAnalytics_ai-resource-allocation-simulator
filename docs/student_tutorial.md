# Student Tutorial

## 1. Learning Objectives

In this activity, you will manage capacity for an AI service platform. By the
end, you should be able to:

- explain why online capacity decisions have opportunity costs;
- use historical data to identify demand and service patterns;
- design an admission and routing policy;
- compare simple baseline policies with your own policy;
- interpret revenue, rejection, completion, and utilization metrics;
- use an AI assistant as a thinking partner for reasoning, coding, and
  debugging.

## 2. Case Overview

You are managing a platform that serves customer requests using several server
clusters. Each cluster has limited reusable capacity. Customer requests arrive
over time. If you admit a request, it uses capacity until its service is
complete. Once the request finishes, the capacity becomes available again.

Each request has:

- a request type;
- an arrival time;
- a number of required server units;
- a service duration;
- a unit price.

Revenue is earned when an admitted request completes. Rejected requests earn no
revenue. Requests that are admitted but do not complete within the evaluation
period may also fail to earn revenue, depending on the simulator setting.

Your challenge is to decide which requests to admit and where to route them.

## 3. Your Decision Problem

Each time a request arrives, your policy must choose one action:

```text
0 = reject the request
n = admit the request to cluster n
```

If you admit a request, the selected cluster must have enough remaining capacity
for that request's required units. If no cluster has enough remaining capacity,
the request should be rejected.

The difficult part is that a feasible request is not always a good request to
accept. A low-value request with a long service duration can occupy capacity
that might later be needed for a higher-value request. Your policy should
therefore consider both the current request and the future opportunity cost of
using capacity now.

## 4. Request Types

The case uses three request types:

| Type | General Interpretation |
|---|---|
| `VIP` | High-priority, high-value requests. These may require more capacity, but they are usually important to protect. |
| `standard` | Mid-value requests that make up a large share of normal demand. |
| `economy` | Lower-value requests. These may still be useful to admit when capacity is available, but they can become costly if they occupy capacity during scarce periods. |

Do not assume that one type should always be accepted or always rejected. A good
policy uses request type together with current capacity, required units, service
duration, and historical patterns.

## 5. Historical Data Fields

You will receive historical data from a previous simulated year. Each row
represents one request.

| Field | Meaning |
|---|---|
| `request_id` | Unique identifier for the request. |
| `arrival_time` | Time index of the request arrival, measured in hours from the start of the year. |
| `month` | Month number, from 1 to 12. |
| `day` | Day within the month. |
| `hour` | Hour of day. |
| `type` | Request type: `VIP`, `standard`, or `economy`. |
| `required_units` | Number of server-capacity units needed while the request is active. |
| `duration` | Observed service duration in hours. |
| `assigned_cluster` | Cluster used in the historical operation. |
| `completed` | Whether the request completed in the historical operation. |
| `unit_price` | Revenue per required unit for the request. |
| `revenue` | Realized revenue. This is positive only when the request completed. |

The historical data is meant to help you estimate useful patterns. It does not
tell you the exact future request stream.

## 6. How To Analyze The Historical Data

Before writing a policy, look for patterns that might affect capacity decisions.

Important questions include:

- Which months have the most demand?
- Does demand differ by request type?
- Which request types require the most capacity?
- Which request types have the longest service durations?
- Which request types produce the most revenue?
- Are some request types completed more often than others?
- Are peak months different from lower-demand months?

Pay special attention to the relationship between value and duration. A request
with low revenue and long duration can be risky because it occupies capacity for
a long time. A request with high revenue and shorter duration may be more
valuable, especially when capacity is scarce.

## 7. Policy Function

Your dashboard will provide the exact policy template. The intended structure is
similar to:

```python
def admission_policy(request, state, history, params):
    return action
```

The policy is called when a request arrives.

The inputs represent:

- `request`: information about the arriving request;
- `state`: current system state, such as remaining capacity and active jobs;
- `history`: historical data and possibly previous simulation feedback;
- `params`: tuning parameters you may control.

The return value should be:

```text
0
```

to reject the request, or a valid cluster id to admit the request.

Your first responsibility is feasibility. Do not assign a request to a cluster
that does not have enough remaining capacity. After checking feasibility, think
about value, required units, service duration, and capacity scarcity.

## 8. Baseline Policy Ideas

A baseline policy is a simple rule used for comparison. You should understand
these before designing a more complex policy.

| Policy | Idea |
|---|---|
| Always reject | Reject every request. This should earn zero revenue and is mainly a sanity check. |
| First-fit | Admit to the first feasible cluster. This is simple but may overuse early clusters. |
| Least-loaded | Admit to the feasible cluster with the most remaining capacity. This spreads load but may not preserve capacity efficiently. |
| Best-fit | Admit to the feasible cluster that leaves the least unused capacity after admission. This can reduce wasted capacity. |
| VIP-only | Admit only VIP requests. This protects VIP service but may waste capacity and lose revenue from other requests. |
| VIP-priority | Protect capacity for VIP requests when capacity is scarce, but still admit other request types when capacity is available. |

The goal is not just to copy a baseline. Use baselines to understand what your
policy improves and what tradeoffs it creates.

## 9. Using The AI Assistant

You may use the AI assistant to help you think through the problem. Good uses
include:

- asking it to explain a data field;
- asking it to summarize visible historical patterns;
- brainstorming admission and routing policies;
- converting a policy idea into pseudocode;
- debugging policy code;
- comparing your policy to a baseline;
- interpreting simulation feedback that you provide.

The assistant is a thinking partner, not a source of hidden answers. It will not
reveal hidden simulator parameters, future request data, private evaluation
details, or other students' work.

Good prompts:

```text
What should I look for when comparing VIP and economy requests?
```

```text
Can you help me write pseudocode for a best-fit policy?
```

```text
My policy rejects many VIP requests during peak months. What diagnostics should
I check?
```

Poor prompts:

```text
What are the hidden arrival rates?
```

```text
What exact policy will get the highest score?
```

```text
What future requests will arrive next month?
```

When using the assistant, ask for reasoning and explanation. You should be able
to justify your final policy in your own words.

### Suggested Workflow With The AI Assistant

A useful workflow is:

1. Inspect the historical data yourself.
2. Write down one or two policy ideas.
3. Ask the AI assistant to critique or compare your ideas.
4. Implement a simple version of your policy.
5. Run the simulation.
6. Review the metrics and warnings.
7. Ask the assistant to help interpret the feedback.
8. Revise your policy and test again.

The assistant should help you reason more clearly. It should not replace your
own judgment.

## 10. Understanding Simulation Results

The primary objective is to earn as much completed revenue as possible over the
simulation. However, total revenue alone does not explain why a policy performs
well or poorly. Use the supporting metrics to diagnose your policy. For example,
a policy with high admissions may still earn low revenue if it fills capacity
with low-value long-duration requests. A policy with strong VIP completion may
still lose revenue if it rejects too many standard requests.

Important metrics include:

| Metric | What It Tells You |
|---|---|
| Total revenue | How much revenue your completed requests earned. |
| Admissions | How many requests your policy accepted. |
| Rejections | How many requests your policy rejected. |
| Completion rate | How often admitted or arriving requests completed. |
| VIP completion rate | Whether high-priority requests were protected. |
| Unfinished requests | How much admitted work failed to complete within the evaluation period. |
| Utilization | How much cluster capacity was used. |
| Benchmark comparison | Whether your policy improves on simple baselines. |

A strong policy earns high completed revenue by using capacity for valuable work
while avoiding unnecessary future blockage. The supporting metrics help you
understand the tradeoffs behind that revenue.

## 11. Common Debugging Examples

If your policy performs poorly, debug it step by step. First check feasibility.
Then inspect which request types are being rejected, which clusters are filling
up, and whether long low-value jobs are blocking capacity.

### Invalid Cluster ID

Problem:

```python
return 999
```

This is invalid if `999` is not a real cluster id.

Fix: return either `0` to reject or one of the valid cluster ids provided by the
dashboard.

### Assigning To A Cluster Without Enough Capacity

Problem:

```python
return cluster_id
```

without checking whether the cluster has enough remaining capacity.

Fix:

```python
if remaining_capacity[cluster_id] >= request["required_units"]:
    return cluster_id
return 0
```

### Using The Wrong Field Name

Problem:

```python
units = request["units_required"]
```

when the field is:

```python
request["required_units"]
```

Fix: use the exact field names shown in the dashboard policy template.

### Accepting Too Many Long-Duration Requests

Symptom: utilization is high, but revenue is low or many requests are
unfinished.

Possible reason: your policy may be accepting requests that occupy capacity for
a long time but do not create enough completed revenue.

Possible improvement: consider request type, required units, duration, time
remaining, or capacity reservation rules.

### Low VIP Completion Rate

Symptom: total revenue may look reasonable, but VIP completion is low.

Possible reason: your policy may not protect enough capacity for high-priority
requests.

Possible improvement: consider a type-priority rule or a reserve-capacity
threshold.

### Load Imbalance Across Clusters

Symptom: one cluster is often full while other clusters remain underused.

Possible reason: a first-fit policy may repeatedly assign requests to the same
cluster.

Possible improvement: try least-loaded, best-fit, or another capacity-aware
routing rule.

## 12. Final Checklist

Before running or submitting a policy, ask yourself:

- Does my policy always return either `0` or a valid cluster id?
- Does it check that the selected cluster has enough remaining capacity?
- Does it consider request type, required units, and duration?
- Does it avoid accepting too much low-value long-running work during scarce
  capacity periods?
- Does it use spare capacity when the system is not crowded?
- Can I explain why my policy should beat at least one simple baseline?
- Have I used the AI assistant to improve my reasoning rather than replace it?

## 13. Final Reflection

After your final simulation run, you should be able to explain:

- what policy you used;
- what historical patterns influenced your design;
- how your policy performed compared with simple baselines;
- which metrics improved or worsened after revisions;
- how you used the AI assistant;
- what limitations your policy still has.

A good final explanation should connect your policy choices to evidence from
the data and feedback from the simulator.
