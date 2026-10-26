"""evalbudget command line.

  evalbudget decide runs.csv --cost minor=0.5 major=4 critical=200 --min-pass 0.85 --max-critical 0.02
  evalbudget power --diff 0.05 --discordant 0.09
  evalbudget bound 0 50
"""

import argparse
import sys

from .decide import Gates, decide, load_runs, summarise
from .stats import mcnemar_sample_size, rate_upper_bound


def _costs(pairs):
    out = {}
    for p in pairs:
        k, _, v = p.partition("=")
        if not v:
            sys.exit(f"--cost expects severity=amount, got {p!r}")
        out[k.strip().lower()] = float(v)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="evalbudget")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decide", help="apply gates, then rank by total cost per task")
    d.add_argument("runs")
    d.add_argument("--cost", nargs="+", required=True, metavar="SEV=USD")
    d.add_argument("--min-pass", type=float, default=0.0)
    d.add_argument("--max-critical", type=float, default=1.0)
    d.add_argument("--max-p95-latency", type=float, default=float("inf"))
    d.add_argument("--max-timeout-rate", type=float, default=1.0)
    d.add_argument("--volume", type=int, help="tasks per month, to print a monthly budget")

    p = sub.add_parser("power", help="paired tasks needed to detect a pass-rate gap")
    p.add_argument("--diff", type=float, required=True)
    p.add_argument("--discordant", type=float, required=True)
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--power", type=float, default=0.8)

    b = sub.add_parser("bound", help="upper bound on a failure rate from k failures in n cases")
    b.add_argument("k", type=int)
    b.add_argument("n", type=int)
    b.add_argument("--conf", type=float, default=0.95)

    a = ap.parse_args(argv)

    if a.cmd == "power":
        n = mcnemar_sample_size(a.diff, a.discordant, a.alpha, a.power)
        print(f"{n:.0f} paired tasks (independent tasks, one run each)")
    elif a.cmd == "bound":
        print(f"true rate could be up to {rate_upper_bound(a.k, a.n, a.conf):.2%}")
    else:
        gates = Gates(a.min_pass, a.max_critical, a.max_p95_latency, a.max_timeout_rate)
        rows = decide(summarise(load_runs(a.runs)), gates, _costs(a.cost))
        hdr = f"{'setup':<28}{'cases':>6}{'pass':>8}{'interval':>16}{'spend/task':>12}{'total/task':>12}"
        if a.volume:
            hdr += f"{'total/month':>14}"
        print(hdr + "  gates")
        for r in rows:
            lo, hi = r["pass_interval"]
            line = (
                f"{r['setup']:<28}{r['cases']:>6}{r['pass_rate']:>8.1%}"
                f"{f'{lo:.0%}-{hi:.0%}':>16}{r['spend_per_task']:>12.4f}{r['total_per_task']:>12.4f}"
            )
            if a.volume:
                line += f"{r['total_per_task'] * a.volume:>14,.0f}"
            print(line + "  " + r["gates"])
        ok = [r for r in rows if r["gates"] == "ok"]
        print(f"\npick: {ok[0]['setup']}" if ok else "\nno setup clears the gates")


if __name__ == "__main__":
    main()
