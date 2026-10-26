"""Budget for AI models on total cost per task, not the token bill."""

from .cost import Setup, breakeven_failure_cost, expected_failure_cost, monthly, total_cost, upgrade_pays
from .decide import Gates, decide, load_runs, summarise
from .escalation import escalate
from .stats import (
    cluster_bootstrap,
    equivalent,
    exact,
    mcnemar_p,
    mcnemar_sample_size,
    pass_rate_halfwidth,
    rate_upper_bound,
    wilson,
)

__version__ = "0.1.0"
