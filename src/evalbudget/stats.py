"""Intervals and sample sizes for pass/fail evals. Standard library only."""

import random
from math import comb, sqrt
from statistics import NormalDist

_Z = NormalDist().inv_cdf


def wilson(k, n, conf=0.95):
    """Wilson score interval for k successes in n independent trials."""
    if n == 0:
        return (0.0, 1.0)
    z = _Z(1 - (1 - conf) / 2)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def _binom_cdf(k, n, p):
    return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def _bisect(f, lo=0.0, hi=1.0, iters=100):
    # f is decreasing in p; find the root
    for _ in range(iters):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def exact(k, n, conf=0.95, one_sided=False):
    """Clopper-Pearson interval. With one_sided=True only the upper bound is tight."""
    if n == 0:
        return (0.0, 1.0)
    alpha = 1 - conf if one_sided else (1 - conf) / 2
    upper = 1.0 if k == n else _bisect(lambda p: _binom_cdf(k, n, p) - alpha)
    if one_sided or k == 0:
        lower = 0.0
    else:
        # by symmetry, the lower bound for k is 1 - the upper bound for n - k failures
        lower = 1 - _bisect(lambda q: _binom_cdf(n - k, n, q) - alpha)
    return (lower, upper)


def rate_upper_bound(failures, cases, conf=0.95):
    """One-sided exact upper bound on a failure rate, e.g. critical failures."""
    return exact(failures, cases, conf, one_sided=True)[1]


def cluster_bootstrap(outcomes_by_cluster, conf=0.95, reps=2000, seed=0):
    """Percentile interval for a rate, resampling whole clusters.

    outcomes_by_cluster: {cluster: [0/1, ...]}, one entry per distinct case.
    """
    rng = random.Random(seed)
    clusters = list(outcomes_by_cluster.values())
    stats = []
    for _ in range(reps):
        draw = [rng.choice(clusters) for _ in clusters]
        n = sum(len(c) for c in draw)
        stats.append(sum(sum(c) for c in draw) / n if n else 0.0)
    stats.sort()
    a = (1 - conf) / 2
    return (stats[int(a * reps)], stats[min(reps - 1, int((1 - a) * reps))])


def mcnemar_sample_size(diff, discordant, alpha=0.05, power=0.8):
    """Paired tasks needed to detect a pass-rate gap `diff` when the two setups
    disagree on a share `discordant` of tasks (normal approximation)."""
    if not 0 < diff <= discordant <= 1:
        raise ValueError("need 0 < diff <= discordant <= 1")
    za, zb = _Z(1 - alpha / 2), _Z(power)
    return (za * sqrt(discordant) + zb * sqrt(discordant - diff * diff)) ** 2 / diff**2


def mcnemar_p(only_a, only_b):
    """Exact two-sided McNemar p-value from the discordant counts."""
    n, k = only_a + only_b, min(only_a, only_b)
    if n == 0:
        return 1.0
    return min(1.0, 2 * _binom_cdf(k, n, 0.5))


def pass_rate_halfwidth(p, n, conf=0.95):
    """Normal-approximation half-width, the '±10 points' figure."""
    return _Z(1 - (1 - conf) / 2) * sqrt(p * (1 - p) / n)


def equivalent(diff_interval, margin):
    """True if the whole interval for (A - B) lies within ±margin."""
    lo, hi = diff_interval
    return -margin <= lo and hi <= margin
