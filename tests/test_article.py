"""Every figure in the article, recomputed through the package."""

import csv

import pytest

from evalbudget import (
    Gates,
    Setup,
    breakeven_failure_cost,
    decide,
    escalate,
    exact,
    mcnemar_p,
    mcnemar_sample_size,
    monthly,
    pass_rate_halfwidth,
    rate_upper_bound,
    summarise,
    upgrade_pays,
    wilson,
)
from evalbudget.cli import main

VOLUME = 100_000
COST = {"any": 4.0}  # every failure about five minutes of staff time

cheap = Setup("cheap", 600 / VOLUME, {"any": 0.18})
mid = Setup("mid", 4_000 / VOLUME, {"any": 0.14})
flag = Setup("flagship", 14_000 / VOLUME, {"any": 0.09})
# perfect free checker, flagship fixes half of what it receives
esc = escalate(cheap, flag, fix_rate=0.5)


@pytest.mark.parametrize(
    "setup,tokens,failures,total",
    [
        (cheap, 600, 72_000, 72_600),
        (mid, 4_000, 56_000, 60_000),
        (flag, 14_000, 36_000, 50_000),
        (esc, 3_120, 36_000, 39_120),
    ],
)
def test_table(setup, tokens, failures, total):
    m = monthly(setup, COST, VOLUME)
    assert m["spend"] == pytest.approx(tokens)
    assert m["failures"] == pytest.approx(failures)
    assert m["total"] == pytest.approx(total)


def test_escalation_pass_rate():
    assert esc.pass_rate == pytest.approx(0.91)


def test_token_share_1_to_28_percent():
    shares = [monthly(s, COST, VOLUME) for s in (cheap, mid, flag, esc)]
    shares = [m["spend"] / m["total"] for m in shares]
    assert round(min(shares), 2) == 0.01 and round(max(shares), 2) == 0.28


def test_escalation_35_percent_below_mid():
    saving = 1 - monthly(esc, COST, VOLUME)["total"] / monthly(mid, COST, VOLUME)["total"]
    assert round(saving, 2) == 0.35


def test_breakeven_two_dollars():
    assert breakeven_failure_cost(mid, flag) == pytest.approx(2.0)
    assert upgrade_pays(mid, flag, {"any": 2.5})
    assert not upgrade_pays(mid, flag, {"any": 1.5})


def test_formatting_fixes_barely_move_budget():
    base = Setup("base", 0.01, {"minor": 0.10, "critical": 0.02})
    up = Setup("up", 0.05, {"minor": 0.02, "critical": 0.02})
    costs = {"minor": 0.10, "critical": 100.0}
    assert up.pass_rate > base.pass_rate
    assert not upgrade_pays(base, up, costs)


def test_zero_of_fifty_allows_about_six_percent():
    assert rate_upper_bound(0, 50) == pytest.approx(0.058, abs=0.001)
    assert wilson(0, 50)[1] < 0.08


def test_fifty_tasks_plus_minus_ten_points():
    assert round(pass_rate_halfwidth(0.86, 50), 2) == 0.10


@pytest.mark.parametrize("diff,disc,n", [(0.05, 0.09, 280), (0.15, 0.15, 50), (0.20, 0.25, 47)])
def test_mcnemar_sizes(diff, disc, n):
    assert round(mcnemar_sample_size(diff, disc)) == n


def test_exact_interval_matches_known_value():
    lo, hi = exact(5, 20)
    assert lo == pytest.approx(0.0866, abs=1e-3) and hi == pytest.approx(0.4910, abs=1e-3)


def test_mcnemar_p_symmetric():
    assert mcnemar_p(10, 2) == mcnemar_p(2, 10) < 0.05


def test_leaky_checker_costs_more():
    leaky = escalate(cheap, flag, 0.5, checker_recall=0.8, checker_false_reject=0.05, checker_cost=0.002)
    assert leaky.pass_rate < esc.pass_rate
    assert monthly(leaky, COST, VOLUME)["total"] > monthly(esc, COST, VOLUME)["total"]


def _write_runs(path):
    rows = []
    for i in range(60):
        cid = f"c{i}"
        rows.append(dict(setup="cheap", case_id=cid, passed=int(i % 5 != 0),
                         severity="" if i % 5 else "major", cost_usd=0.001, latency_s=2))
        rows.append(dict(setup="big", case_id=cid, passed=int(i % 20 != 0),
                         severity="" if i % 20 else ("critical" if i == 0 else "minor"),
                         cost_usd=0.03, latency_s=9))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_decide_gates_then_cost(tmp_path):
    p = tmp_path / "runs.csv"
    _write_runs(p)
    from evalbudget import load_runs

    s = summarise(load_runs(p))
    assert s["big"].critical_cases == 1 and s["cheap"].cases == 60
    rows = decide(s, Gates(min_pass=0.85), {"minor": 0.5, "major": 4, "critical": 200})
    assert rows[0]["setup"] == "big" and rows[0]["gates"] == "ok"
    assert "pass" in rows[1]["gates"]
    rows = decide(s, Gates(max_critical=0.02), {"minor": 0.5, "major": 4, "critical": 200})
    assert rows[0]["setup"] == "cheap"


def test_missing_severity_is_an_error(tmp_path):
    p = tmp_path / "runs.csv"
    p.write_text("setup,case_id,passed,severity,cost_usd\na,1,0,,0.1\n")
    from evalbudget import load_runs

    with pytest.raises(ValueError):
        summarise(load_runs(p))


def test_cli(tmp_path, capsys):
    p = tmp_path / "runs.csv"
    _write_runs(p)
    main(["decide", str(p), "--cost", "minor=0.5", "major=4", "critical=200", "--min-pass", "0.85", "--volume", "1000"])
    assert "pick: big" in capsys.readouterr().out
    main(["bound", "0", "50"])
    assert "5.8" in capsys.readouterr().out
