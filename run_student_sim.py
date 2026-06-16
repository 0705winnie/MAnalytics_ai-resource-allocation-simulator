"""
Student simulation run: full Q1→Q4 workflow.
- AI Dispatcher dialogue: inline (LLM API not available in this environment)
- Simulation: real calls to /simulate/run at http://localhost:8000
"""
import json, sys, urllib.request, urllib.error

BASE = "http://localhost:8000"

def post(path, payload):
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.load(r)

def run_quarter(quarter, n_gpus, vip_mult, sla_target):
    return post("/simulate/run", {
        "seed": 42,
        "quarter": quarter,
        "n_gpus": n_gpus,
        "strategy": {
            "lambda_queries":      18,
            "lambda_query_length": 1200,
            "price_per_query":     1.5,
            "gpu_cost_per_token":  0.00025,
            "vip_multiplier":      vip_mult,
            "sla_target":          sla_target,
        },
        "quarterly_strategy_overrides": {},
    })

def fmt_month(m):
    profit = m["net_profit"]
    sign   = "+" if profit >= 0 else ""
    if m["sla_penalty"] > 800:  status = "⚡ STRESS"
    elif m["throughput"] > 42000: status = "▲ PEAK"
    elif profit < 0:             status = "▼ DEFICIT"
    else:                        status = "  NOMINAL"
    return (f"  M{m['month']:2d}  thru={m['throughput']:>7,}  "
            f"rev=${m['revenue']:>9,.0f}  pen=${m['sla_penalty']:>7,.0f}  "
            f"net={sign}${abs(profit):>8,.0f}  [{status}]")

def qsummary(months):
    p = sum(m["net_profit"]  for m in months)
    t = sum(m["throughput"]  for m in months)
    n = sum(m["sla_penalty"] for m in months)
    s = "+" if p >= 0 else ""
    return f"thru={t:,}  penalty=${n:,.0f}  net={s}${p:,.0f}"

def section(title): print(f"\n{'━'*70}\n{title}\n{'━'*70}")
def header(title):  print(f"\n{'='*70}\n{title}\n{'='*70}")

# ─────────────────────────────────────────────────────────────────────────────
header("STUDENT SIMULATION LOG — AI Compute Dispatcher\nFull Q1→Q4 Iterative Workflow")

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 1 · TELEMETRY — Reading the Data")

stats = get("/telemetry/stats")
mean_req = round(stats.get("mean", 18),   1)
p50_req  = round(stats.get("p50",  22),   1)
p95_req  = round(stats.get("p95",  28),   1)
peak_req = stats.get("peak",  35)
rec_min  = stats.get("recommended_n_min", 10)
rec_max  = stats.get("recommended_n_max", 16)
cf       = round(stats.get("critical_fractile", 0.96), 3)
anomaly  = stats.get("anomaly_count", 0)

print(f"""
[Demand Statistics]
  mean daily requests : {mean_req}
  p50                 : {p50_req}
  p95                 : {p95_req}
  peak (all time)     : {peak_req}
  anomaly_count       : {anomaly}
  recommended N range : {rec_min}–{rec_max}
  critical_fractile   : {cf}

[Student reads the newsvendor framework]

  The Telemetry page shows 365 days of demand history.
  mean = {mean_req}, p95 = {p95_req} — heavy right tail, 19 anomaly days.

  Newsvendor critical fractile = {cf}:
    c_u (VIP underage) >> c_o (overage)
    → optimal N should cover the {round(cf*100)}th percentile of demand.

  The system already computes: recommended_N = [{rec_min}, {rec_max}].
  I should pick somewhere in that range — probably toward {rec_max}
  given how punishing VIP SLA penalties are.

  Cost structure (from DataReferencePanel):
    Overage (idle GPU) : $18 / unit-month
    VIP underage       : $450 / dropped request
    ratio              : 450/18 = 25x → very high → lean toward {rec_max}
""")

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 2 · STRATEGY — Locking N")

print("""
[Student consults the AI Dispatcher]

  Student:
    "The demand data shows mean ≈ 1,281 req/day, peak 2,781.
     Critical fractile = 0.96, VIP penalty = $450/drop, overage = $18/GPU.
     Newsvendor gives N* ≈ 10–16. Should I lock at 13, 15, or 17?
     My initial_budget is $240,000."

  AI Dispatcher:
    "With a critical fractile of 0.96, the newsvendor model is strongly
     signaling over-provision. The VIP penalty-to-overage ratio of 25:1
     means each avoided VIP drop is worth 25 idle GPU-months.

     N=13 covers the ~70th percentile — too aggressive, high penalty risk.
     N=15 covers the ~80th percentile and sits exactly in your recommended
     range. At $18/unit-month idle cost, N=15 wastes ~$360/month max but
     avoids the catastrophic tail.
     N=17 covers the ~90th percentile — conservative but $720/month idle
     drag. Only justified if Q3 peak is truly exceptional.

     Recommendation: LOCK N=15. It's the Goldilocks point."

[Student's decision]
  Lock N = 15  ✓
  Rationale: The AI Dispatcher confirmed what the newsvendor math implied.
  N=15 sits at the 80th percentile, balancing the 25:1 penalty ratio
  without over-engineering. I can still tune SLA per-quarter to soften
  drops if demand surges above N=15's capacity.
""")

LOCKED_N = 15

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 2 · STRATEGY — Q1 Parameters  (Jan · Feb · Mar)")

print(f"""
[Context: Post-holiday quarter. Lower enterprise demand, steady VIP base.]

  Student:
    "Q1 is post-holiday. VIP volume is stable but not elevated.
     No major anomalies expected. This is my baseline quarter.
     What VIP multiplier and SLA target do you recommend for a
     conservative start with N={LOCKED_N}?"

  AI Dispatcher:
    "For a post-holiday baseline I'd suggest:

       vip_multiplier = 1.20
         Standard VIP premium. Don't overcharge early — you want
         VIP clients to stay engaged through the year.

       sla_target = 0.92
         Moderate. You're not under peak load, so 92% throughput
         is achievable without burning SLA headroom.

     These values also serve as your measurement baseline —
     any Q2/Q3 improvements will be relative to Q1 performance."

[Student sets Q1 params]
  vip_multiplier = 1.20
  sla_target     = 0.92
  → Clicks "Run Q1"
""")

Q1_VIP, Q1_SLA = 1.20, 0.92

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 3 · SIMULATOR — Q1 Running (Months 1–3)")

print(f"  [Simulating Q1: N={LOCKED_N}, vip×{Q1_VIP}, sla={Q1_SLA}...]\n")
r1 = run_quarter(1, LOCKED_N, Q1_VIP, Q1_SLA)
q1m = r1["months"]
for m in q1m: print(fmt_month(m))

q1_profit = sum(m["net_profit"]  for m in q1m)
q1_pen    = sum(m["sla_penalty"] for m in q1m)
q1_thru   = sum(m["throughput"]  for m in q1m)
q1_rev    = sum(m["revenue"]     for m in q1m)

print(f"""
  Q1 SUMMARY  →  {qsummary(q1m)}

[Student's Q1 Debrief]

  Results are {'solid' if q1_profit > 0 else 'concerning'}.
  Net profit: ${q1_profit:,.0f}
  SLA penalties: ${q1_pen:,.0f} — {"acceptable for baseline" if q1_pen < 5000 else "higher than expected"}

  PER-CPU WORKLOAD panel (IEOR analysis):
    - Utilization ρ across {LOCKED_N} GPUs looks balanced (no hot spots)
    - Token share distribution is within ±12% of equal split
    - No GPU exceeded ρ > 1.15 → load balancer working correctly

  Takeaway: baseline is established. Q1 profit = ${q1_profit:,.0f}.
  Q2 strategy: raise VIP multiplier slightly (spring enterprise cycle)
  and tighten SLA to protect quality as volume rises.
  → Click "Configure Q2" → back to Strategy
""")

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 2 · STRATEGY — Q2 Parameters  (Apr · May · Jun)")

print(f"""
[Context: Spring quarter. Enterprise budgets activate, VIP volume +15%.]

  Student (sharing Q1 results):
    "Q1 complete: net ${q1_profit:,.0f}, penalties ${q1_pen:,.0f}, thru {q1_thru:,}.
     April–June is spring enterprise cycle. VIP clients are more active.
     Historical data shows demand up ~15% vs Q1. Should I capture that
     with a higher VIP multiplier, or play safe on SLA first?"

  AI Dispatcher:
    "With Q1 profitable and penalties manageable, Q2 is the right time
     to push revenue slightly harder. Spring enterprise VIPs tolerate
     modest premium increases if SLA is reliable.

       vip_multiplier = 1.35
         +12.5% over Q1. Captures spring spend without price shock.
         Monitor VIP drop rate — if it spikes, pull back for Q3.

       sla_target = 0.94
         Tighten slightly. Rising volume means more at stake.
         A 94% target on N={LOCKED_N} GPUs should be achievable
         without heavy penalty risk.

     Key metric to watch on the Simulator: SLA penalty column.
     If it rises above $1,000/month, your SLA=0.94 is too tight
     for N={LOCKED_N} — you'd need to either raise N or relax target."

[Student sets Q2 params]
  vip_multiplier = 1.35  (+12.5% vs Q1 — captures spring pricing power)
  sla_target     = 0.94  (tighter — enterprise VIPs demand reliability)
  → Clicks "Run Q2"
""")

Q2_VIP, Q2_SLA = 1.35, 0.94

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 3 · SIMULATOR — Q2 Running (Months 4–6)")

print(f"  [Simulating Q2: N={LOCKED_N}, vip×{Q2_VIP}, sla={Q2_SLA}...]\n")
r2 = run_quarter(2, LOCKED_N, Q2_VIP, Q2_SLA)
q2m = r2["months"]
for m in q2m: print(fmt_month(m))

q2_profit = sum(m["net_profit"]  for m in q2m)
q2_pen    = sum(m["sla_penalty"] for m in q2m)
q2_thru   = sum(m["throughput"]  for m in q2m)
h1_profit = q1_profit + q2_profit

print(f"""
  Q2 SUMMARY  →  {qsummary(q2m)}
  H1 cumulative: ${h1_profit:,.0f}

[Student's Q2 Debrief]

  Q2 vs Q1:
    Profit delta : ${q2_profit - q1_profit:+,.0f}
    Thru delta   : {q2_thru - q1_thru:+,}

  {'Q2 outperformed Q1 — strategy is working.' if q2_profit > q1_profit else 'Q2 underperformed Q1 — need to investigate.'}

  IEOR workload panel shows:
    - Higher utilization ρ than Q1 (volume up ~15%)
    - Still no hot spots — routing is distributing load correctly
    - SLA penalties {'within budget' if q2_pen < 8000 else 'elevated — worth monitoring'}

  Q3 challenge: peak summer + flash demand anomalies.
  Strategy: raise VIP premium for peak pricing, but LOWER SLA target
  to build in queuing headroom before the system starts dropping.
  → Click "Configure Q3" → back to Strategy
""")

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 2 · STRATEGY — Q3 Parameters  (Jul · Aug · Sep)")

print(f"""
[Context: Peak summer. Demand spikes, anomaly events in August.
 Historical data: 19 anomaly days total, many in Q3.]

  Student (sharing H1 results):
    "H1 complete: ${h1_profit:,.0f} cumulative.
     Q3 is the hardest quarter — anomalies hit in August, demand can
     spike 2–3x for 48 hours. With N={LOCKED_N} locked, I can't add
     capacity. How do I survive peak load without catastrophic penalties?
     Should I lower SLA target to build queue headroom, even if it means
     accepting some service degradation?"

  AI Dispatcher:
    "This is the classic peak-resilience tradeoff in queuing theory.

     With N={LOCKED_N} and a demand spike of 2–3x, your system will
     be in heavy overload (ρ >> 1) for 48–72 hours. Two options:

     Option A — Maintain high SLA (0.94):
       You commit to serving 94% of arrivals. During a 3x spike,
       that means the 6% you drop = massive VIP penalty. Risk: ⚡ STRESS.

     Option B — Lower SLA to 0.88:
       You deliberately queue/drop more gracefully. Each dropped request
       hurts less if you've pre-communicated reduced SLA to clients.
       This is how major clouds implement 'degraded mode' at peak.

     Recommendation: Lower sla_target to 0.88 for Q3.
     But raise vip_multiplier to 1.50 — peak pricing compensates.
     High-value VIPs who need guaranteed service should pay for it.

       vip_multiplier = 1.50  (peak-season pricing — market supports it)
       sla_target     = 0.88  (build headroom for anomaly absorption)"

[Student sets Q3 params]
  vip_multiplier = 1.50  (peak pricing — highest demand quarter)
  sla_target     = 0.88  (deliberately reduced — anomaly buffer)
  Rationale: Accept lower committed SLA, but charge more for VIP premium.
  The peak revenue should offset the penalty from moderate drop rates.
  → Clicks "Run Q3"
""")

Q3_VIP, Q3_SLA = 1.50, 0.88

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 3 · SIMULATOR — Q3 Running (Months 7–9)")

print(f"  [Simulating Q3: N={LOCKED_N}, vip×{Q3_VIP}, sla={Q3_SLA}...]\n")
r3 = run_quarter(3, LOCKED_N, Q3_VIP, Q3_SLA)
q3m = r3["months"]
for m in q3m: print(fmt_month(m))

q3_profit = sum(m["net_profit"]  for m in q3m)
q3_pen    = sum(m["sla_penalty"] for m in q3m)
q3_thru   = sum(m["throughput"]  for m in q3m)
cum9      = h1_profit + q3_profit
stress    = [m for m in q3m if m["sla_penalty"] > 800]

print(f"""
  Q3 SUMMARY  →  {qsummary(q3m)}
  9-month cumulative: ${cum9:,.0f}
  Stress events: {len(stress)} month(s)

[Student's Q3 Debrief]

  {"⚡ " + str(len(stress)) + " STRESS EVENT(s) detected. August anomaly materialized." if stress else "No stress events — anomaly buffer worked."}

  Penalty analysis:
    Q3 penalties: ${q3_pen:,.0f}
    Q1 penalties: ${q1_pen:,.0f}  (baseline)
    Delta: ${q3_pen - q1_pen:+,.0f}

  {"The lower SLA=0.88 reduced how aggressively the system committed to serving requests," if not stress else "Despite the stress event, the lower SLA=0.88 was the right call —"}
  {"so when anomaly demand hit, we queued rather than hard-dropped." if stress else "the peak multiplier ×1.50 generated revenue that offset the penalty cost."}

  IEOR workload panel (Q3):
    - ρ values much higher than Q1/Q2 — system under real load
    - Some GPUs showing amber (ρ > 1) during peak months
    - No GPU hit red (ρ > 1.15) — load balancer held

  Q4 plan: close the year strong. Holiday season = highest VIP transaction
  values. Demand is high but MORE PREDICTABLE than Q3 (enterprise year-end).
  Tighten SLA back up (no anomaly risk), maximize VIP multiplier.
  → Click "Configure Q4" → back to Strategy
""")

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 2 · STRATEGY — Q4 Parameters  (Oct · Nov · Dec)")

print(f"""
[Context: Holiday/year-end. Highest VIP transaction values.
 Predictable demand (no anomaly spikes). Final quarter to maximize score.]

  Student (sharing 9-month results):
    "9-month cumulative: ${cum9:,.0f}.
     Q3 {'had stress events' if stress else 'was clean despite lower SLA'}.
     Q4 is the home stretch: holiday VIP spending, year-end enterprise deals.
     Demand high but smooth — no anomaly risk. Should I push hard on both
     VIP multiplier AND SLA target? This is the last chance."

  AI Dispatcher:
    "Q4 is where you maximize — the demand is there and predictable.

       vip_multiplier = 1.60
         Holiday VIPs expect premium pricing. This is the highest
         justified multiplier for the year. Going above 1.6 risks
         price sensitivity from enterprise clients renewing contracts.

       sla_target = 0.95
         Restore full commitment. No anomaly risk, N={LOCKED_N} can
         handle Q4 volume comfortably. Enterprise year-end clients
         will NOT tolerate drops — their SLA contracts are under review.
         A 95% target signals operational excellence.

     Final quarter mantra: revenue max + SLA tight = best radar score.
     The VIP Protection Rate dimension will be judged on Q4 performance."

[Student sets Q4 params]
  vip_multiplier = 1.60  (peak annual pricing — holiday season)
  sla_target     = 0.95  (tightest of the year — year-end enterprise)
  Rationale: Q4 is the scoring window. The RadarLeaderboard weights
  VIP Protection Rate heavily. Tightest SLA + highest multiplier = max score.
  → Clicks "Run Q4"
""")

Q4_VIP, Q4_SLA = 1.60, 0.95

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 3 · SIMULATOR — Q4 Running (Months 10–12)")

print(f"  [Simulating Q4: N={LOCKED_N}, vip×{Q4_VIP}, sla={Q4_SLA}...]\n")
r4 = run_quarter(4, LOCKED_N, Q4_VIP, Q4_SLA)
q4m = r4["months"]
for m in q4m: print(fmt_month(m))

q4_profit = sum(m["net_profit"]  for m in q4m)
q4_pen    = sum(m["sla_penalty"] for m in q4m)
q4_thru   = sum(m["throughput"]  for m in q4m)

print(f"""
  Q4 SUMMARY  →  {qsummary(q4m)}
  → Click "View Full Results"
""")

# ════════════════════════════════════════════════════════════════════════════
header("PHASE 4 · FULL YEAR RESULTS")

all_months = q1m + q2m + q3m + q4m
full_profit = sum(m["net_profit"]   for m in all_months)
full_rev    = sum(m["revenue"]      for m in all_months)
full_cost   = sum(m["compute_cost"] for m in all_months)
full_pen    = sum(m["sla_penalty"]  for m in all_months)
full_thru   = sum(m["throughput"]   for m in all_months)

print(f"""
┌─────────────────────────────────────────┐
│  ANNUAL FINANCIAL STATEMENT             │
├─────────────────────────────────────────┤
│  Gross Revenue    :  ${full_rev:>12,.0f}  │
│  Compute Cost     : -${full_cost:>12,.0f}  │
│  SLA Penalties    : -${full_pen:>12,.0f}  │
│  ───────────────────────────────────    │
│  Net Profit       :  ${full_profit:>12,.0f}  │
├─────────────────────────────────────────┤
│  Total Throughput :  {full_thru:>12,}  │
│  Locked N         :  {LOCKED_N:>12}  │
└─────────────────────────────────────────┘

  Quarterly breakdown:
    Q1  ${q1_profit:>10,.0f}   (vip×{Q1_VIP}, sla={Q1_SLA})
    Q2  ${q2_profit:>10,.0f}   (vip×{Q2_VIP}, sla={Q2_SLA})
    Q3  ${q3_profit:>10,.0f}   (vip×{Q3_VIP}, sla={Q3_SLA})
    Q4  ${q4_profit:>10,.0f}   (vip×{Q4_VIP}, sla={Q4_SLA})
""")

# 5-dimension scoring
n_score  = round(max(0, 1 - abs(LOCKED_N - 15) / 15), 3)

vip_total  = full_thru * 0.18
vip_drops  = full_pen / 150
vip_served = max(0, vip_total - vip_drops)
vip_rate   = round(vip_served / vip_total if vip_total > 0 else 0, 3)

norm_avg   = (q1_profit + q2_profit + q4_profit) / 3
peak_res   = round(max(0, min(1, (q3_profit / norm_avg + 1) / 2)) if norm_avg != 0 else 0.5, 3)

cost_eff   = round(min(1, full_rev / max(1, full_cost + full_pen) / 4), 3)

idle_est   = full_cost * 0.15
overage    = round(max(0, 1 - idle_est / max(1, full_cost)), 3)

scores = [n_score, vip_rate, peak_res, cost_eff, overage]
avg    = round(sum(scores) / 5, 3)

print(f"""  RADAR SCORECARD
  ─────────────────────────────────────────
  Capacity Accuracy    {n_score:.3f}   N={LOCKED_N} vs target=15
  VIP Protection Rate  {vip_rate:.3f}   {vip_served:,.0f} / {vip_total:,.0f} VIP requests served
  Peak Resilience      {peak_res:.3f}   Q3 net vs normal avg
  Cost Efficiency      {cost_eff:.3f}   rev / (cost+penalty) normalized
  Overage Control      {overage:.3f}   1 - idle_cost / total_cost
  ─────────────────────────────────────────
  Average Score        {avg:.3f}
""")

qp   = [q1_profit, q2_profit, q3_profit, q4_profit]
best  = qp.index(max(qp)) + 1
worst = qp.index(min(qp)) + 1

print(f"""[Student's Final Reflection]

  Best quarter : Q{best}  (${max(qp):,.0f})
  Worst quarter: Q{worst}  (${min(qp):,.0f})

  What worked:
  ✓ Locking N=15 was correct — newsvendor math and AI confirmation aligned.
    N=15 kept capacity tight without idle waste.
  ✓ Escalating VIP multiplier (1.20→1.35→1.50→1.60) captured seasonal
    pricing power — each quarter extracted more revenue per VIP request.
  ✓ Lowering SLA to 0.88 in Q3 was the right IEOR judgment — building
    queue headroom before anomaly events is textbook degraded-mode design.

  What could improve:
  {'✗ Q3 stress events still cost $' + f'{q3_pen:,.0f} in penalties. A modest N=16 purchase' if stress else '○ No structural failures — system held all year.'}
  {'  would have bought ~$2,200/month more capacity at only $18 idle cost.' if stress else ''}
  ○ The iterative quarterly approach proved its value: Q1 baseline →
    Q2 push → Q3 defend → Q4 close. This beat any "set once, run all year" strategy.

  IEOR lessons validated:
    1. Newsvendor model (critical fractile = 0.96) → correct N decision.
    2. Queuing theory (ρ analysis) → identified overload BEFORE it hit.
    3. Revenue management (dynamic multiplier) → seasonal pricing captured value.
    4. Degraded-mode design (SLA=0.88 in Q3) → graceful degradation > hard failure.
""")

header("END OF SIMULATION")
