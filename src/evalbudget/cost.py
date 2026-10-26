"""Total cost per task: spend plus what failures cost.

total = model and tool spend + checker and routing cost + expected review cost
        + sum over severities (failure rate x cost of that severity)
"""

from dataclasses import dataclass, field


@dataclass
class Setup:
    """A model plus its prompt, effort, tools, retries and limits, priced per task."""

    name: str
    spend: float  # model and tool spend per task
    failure_rates: dict = field(default_factory=dict)  # severity -> share of tasks
    checker: float = 0.0  # checker and routing cost per task
    review: float = 0.0  # expected human review cost per task

    @property
    def pass_rate(self):
        return 1 - sum(self.failure_rates.values())


def expected_failure_cost(failure_rates, failure_costs):
    missing = set(failure_rates) - set(failure_costs)
    if missing:
        raise KeyError(f"no cost given for severity: {sorted(missing)}")
    return sum(rate * failure_costs[sev] for sev, rate in failure_rates.items())


def total_cost(setup, failure_costs):
    return setup.spend + setup.checker + setup.review + expected_failure_cost(
        setup.failure_rates, failure_costs
    )


def monthly(setup, failure_costs, volume):
    """Monthly budget = task volume x total cost per task."""
    return {
        "spend": setup.spend * volume,
        "checker": setup.checker * volume,
        "review": setup.review * volume,
        "failures": expected_failure_cost(setup.failure_rates, failure_costs) * volume,
        "total": total_cost(setup, failure_costs) * volume,
    }


def upgrade_pays(base, upgrade, failure_costs):
    """An upgrade pays when its extra cost per task is less than the drop in
    expected failure cost, summed across severities."""
    extra = (upgrade.spend + upgrade.checker + upgrade.review) - (
        base.spend + base.checker + base.review
    )
    saved = expected_failure_cost(base.failure_rates, failure_costs) - expected_failure_cost(
        upgrade.failure_rates, failure_costs
    )
    return extra < saved


def breakeven_failure_cost(base, upgrade):
    """Per-failure cost above which `upgrade` beats `base`. Only meaningful
    when every failure costs the same."""
    extra = (upgrade.spend + upgrade.checker + upgrade.review) - (
        base.spend + base.checker + base.review
    )
    drop = upgrade.pass_rate - base.pass_rate
    if drop <= 0:
        return float("inf")
    return extra / drop
