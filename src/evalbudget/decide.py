"""Gates first, then the lowest total cost per task, from a file of graded runs.

Runs file columns (CSV):
  setup, case_id, passed (1/0), severity (minor/major/critical, blank if passed),
  cost_usd, and optionally cluster, latency_s, timeout (1/0), dimension.
"""

import csv
from collections import defaultdict
from dataclasses import dataclass, field

from .cost import Setup, total_cost
from .stats import cluster_bootstrap, rate_upper_bound, wilson


@dataclass
class Gates:
    min_pass: float = 0.0  # applied overall and to every dimension
    max_critical: float = 1.0  # applied to the upper bound, not the point estimate
    max_p95_latency: float = float("inf")
    max_timeout_rate: float = 1.0
    conf: float = 0.95


@dataclass
class Summary:
    setup: Setup
    cases: int
    runs: int
    pass_interval: tuple
    critical_cases: int
    critical_upper: float
    p95_latency: float = None
    timeout_rate: float = 0.0
    dimension_pass: dict = field(default_factory=dict)


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "pass")


def _p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(0.95 * len(xs)))] if xs else None


def load_runs(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def summarise(rows, conf=0.95):
    by_setup = defaultdict(list)
    for r in rows:
        by_setup[r["setup"]].append(r)

    out = {}
    for name, rs in by_setup.items():
        bad = [r["case_id"] for r in rs if not _truthy(r["passed"]) and not r.get("severity", "").strip()]
        if bad:
            raise ValueError(f"{name}: failed runs with no severity, cases {bad[:5]}")

        sev_counts = defaultdict(int)
        for r in rs:
            if not _truthy(r["passed"]):
                sev_counts[r["severity"].strip().lower()] += 1
        n = len(rs)
        setup = Setup(
            name=name,
            spend=sum(float(r.get("cost_usd") or 0) for r in rs) / n,
            failure_rates={s: c / n for s, c in sev_counts.items()},
        )

        # five runs of one case are one case
        case_runs = defaultdict(list)
        case_cluster = {}
        for r in rs:
            case_runs[r["case_id"]].append(1 if _truthy(r["passed"]) else 0)
            case_cluster[r["case_id"]] = r.get("cluster") or r["case_id"]
        crit_cases = {r["case_id"] for r in rs if r.get("severity", "").strip().lower() == "critical"}
        has_clusters = any(r.get("cluster") for r in rs)
        repeated = any(len(v) > 1 for v in case_runs.values())

        if has_clusters or repeated:
            means, crits = defaultdict(list), defaultdict(list)
            for cid, v in case_runs.items():
                means[case_cluster[cid]].append(sum(v) / len(v))
                crits[case_cluster[cid]].append(1 if cid in crit_cases else 0)
            pass_iv = cluster_bootstrap(means, conf)
            # one-sided upper bound: take the upper end of a (2*conf - 1) two-sided interval
            crit_up = cluster_bootstrap(crits, 2 * conf - 1)[1]
        else:
            k = sum(v[0] for v in case_runs.values())
            pass_iv = wilson(k, len(case_runs), conf)
            crit_up = rate_upper_bound(len(crit_cases), len(case_runs), conf)

        dims = defaultdict(list)
        for r in rs:
            if r.get("dimension"):
                dims[r["dimension"]].append(1 if _truthy(r["passed"]) else 0)

        lat = [float(r["latency_s"]) for r in rs if r.get("latency_s")]
        out[name] = Summary(
            setup=setup,
            cases=len(case_runs),
            runs=n,
            pass_interval=pass_iv,
            critical_cases=len(crit_cases),
            critical_upper=crit_up,
            p95_latency=_p95(lat),
            timeout_rate=sum(_truthy(r.get("timeout", 0)) for r in rs) / n,
            dimension_pass={d: sum(v) / len(v) for d, v in dims.items()},
        )
    return out


def gate_failures(s, gates):
    reasons = []
    if s.setup.pass_rate < gates.min_pass:
        reasons.append(f"pass {s.setup.pass_rate:.1%} < {gates.min_pass:.1%}")
    for d, p in s.dimension_pass.items():
        if p < gates.min_pass:
            reasons.append(f"{d} pass {p:.1%} < {gates.min_pass:.1%}")
    if s.critical_upper > gates.max_critical:
        reasons.append(
            f"critical up to {s.critical_upper:.1%} ({s.critical_cases}/{s.cases} cases) > {gates.max_critical:.1%}"
        )
    if s.p95_latency is not None and s.p95_latency > gates.max_p95_latency:
        reasons.append(f"p95 latency {s.p95_latency:.1f}s > {gates.max_p95_latency:.1f}s")
    if s.timeout_rate > gates.max_timeout_rate:
        reasons.append(f"timeouts {s.timeout_rate:.1%} > {gates.max_timeout_rate:.1%}")
    return reasons


def decide(summaries, gates, failure_costs):
    """Return rows sorted with gate-passing setups first, cheapest first."""
    rows = []
    for s in summaries.values():
        reasons = gate_failures(s, gates)
        rows.append(
            {
                "setup": s.setup.name,
                "cases": s.cases,
                "pass_rate": s.setup.pass_rate,
                "pass_interval": s.pass_interval,
                "spend_per_task": s.setup.spend,
                "total_per_task": total_cost(s.setup, failure_costs),
                "gates": "ok" if not reasons else "; ".join(reasons),
            }
        )
    rows.sort(key=lambda r: (r["gates"] != "ok", r["total_per_task"]))
    return rows
