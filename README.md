# evalbudget

Choose between AI model setups on your own graded tasks. A setup must clear the quality gates first. Among those that do, pick the one with the lowest total cost per task:

```
model and tool spend + checker and routing cost + expected review cost
+ Σ (failure rate at each severity × cost of that severity)
```

No model calls and no dependencies. You bring the graded runs.

## Graded runs

One row per run, as a CSV:

| column | |
|---|---|
| `setup` | model + prompt + effort + tools, frozen |
| `case_id` | five runs of one case count as one case |
| `passed` | 1 or 0 |
| `severity` | `minor`, `major` or `critical` when failed |
| `cost_usd` | model and tool spend for this run |
| `cluster` | optional: customer or template; intervals then resample whole clusters |
| `latency_s`, `timeout`, `dimension` | optional gates |

```
evalbudget decide runs.csv --cost minor=0.5 major=4 critical=200 \
    --min-pass 0.85 --max-critical 0.02 --volume 100000
evalbudget decide runs.csv --cost major=4 --min-pass 0.85 --pass-on-lower   # gate on the lower bound
evalbudget power --diff 0.05 --discordant 0.09     # about 280 paired tasks
evalbudget bound 0 50                              # 0 of 50 still allows about 5.8%
```

## In Python

```python
from evalbudget import Setup, escalate, monthly

cheap = Setup("cheap", spend=0.006, failure_rates={"major": 0.18})
flag = Setup("flagship", spend=0.14, failure_rates={"major": 0.09})
pipe = escalate(cheap, flag, fix_rate=0.5, checker_recall=0.8,
                checker_false_reject=0.05, checker_cost=0.002)
monthly(pipe, {"major": 4.0}, volume=100_000)
```

`escalate` prices the cheap-first pipeline with a leaky checker: missed failures stay failed, false rejects cost a flagship call, and the flagship can break answers that were already right. Measure those three rates on the same tasks before you rely on the result.

## Noise and drift

Models are not deterministic, and providers change them after release. With 50 tasks, a measured 86% is consistent with a true pass rate as low as 76%, so a setup that just clears `--min-pass` one week can miss it the next with no real change. `--pass-on-lower` checks `--min-pass` against the one-sided lower bound instead, the same way `--max-critical` uses the upper bound. To clear 85% that way you need 47 of 50, 91 of 100 or 266 of 300. Pin dated model versions, re-run a fixed anchor set on a schedule, and treat a drop as real only when it repeats.

## Limits

Intervals assume independent cases unless you give `cluster`. The McNemar sample size assumes one run per task. For clustered tasks or repeated runs, simulate the analysis on pilot data.
