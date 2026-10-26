"""Cheap model first, checker decides, flagship gets what the checker flags."""

from .cost import Setup


def escalate(
    cheap,
    flagship,
    fix_rate,
    checker_recall=1.0,
    checker_false_reject=0.0,
    checker_cost=0.0,
    name=None,
):
    """Price a cheap-first pipeline as one Setup.

    fix_rate: share of escalated cheap failures the flagship fixes.
    checker_recall: share of cheap failures the checker catches.
    checker_false_reject: share of cheap passes the checker escalates anyway;
        the flagship then fails those at its own rate.
    Failures keep the severity mix of whichever model produced them.
    """
    fail_c = 1 - cheap.pass_rate
    caught = fail_c * checker_recall
    false_rej = (1 - fail_c) * checker_false_reject
    escalated = caught + false_rej

    def mix(rates):
        total = sum(rates.values())
        return {s: r / total for s, r in rates.items()} if total else {}

    residual = {}
    # failures the checker missed, plus caught ones the flagship could not fix
    for sev, share in mix(cheap.failure_rates).items():
        residual[sev] = residual.get(sev, 0.0) + share * (
            fail_c * (1 - checker_recall) + caught * (1 - fix_rate)
        )
    # good cheap answers sent up and then broken by the flagship
    for sev, rate in flagship.failure_rates.items():
        residual[sev] = residual.get(sev, 0.0) + false_rej * rate

    return Setup(
        name=name or f"{cheap.name} -> {flagship.name}",
        spend=cheap.spend + escalated * flagship.spend,
        failure_rates=residual,
        checker=checker_cost + cheap.checker,
        review=cheap.review + escalated * flagship.review,
    )
