"""Transaction cost model."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.config import COST_BPS

logger = logging.getLogger(__name__)


def compute_monthly_turnover(portfolios: pd.Series) -> pd.Series:
    """Compute month-over-month turnover of the long-short portfolio."""
    dates = portfolios.index.get_level_values("date").unique().sort_values()
    turnovers = {}
    prev_pos: set[tuple] = set()
    for date in dates:
        try:
            cur_df = portfolios.xs(date, level="date")
        except KeyError:
            continue
        cur_pos = set(cur_df.index)
        n_total = len(cur_pos | prev_pos)
        if n_total == 0:
            turnovers[date] = 0.0
        elif not prev_pos:
            turnovers[date] = 1.0
        else:
            n_changed = len(cur_pos.symmetric_difference(prev_pos))
            turnovers[date] = n_changed / n_total
        prev_pos = cur_pos
    return pd.Series(turnovers, name="turnover")


def apply_costs(gross_returns: pd.Series, turnover: pd.Series, cost_bps: int = COST_BPS) -> pd.Series:
    """Deduct round-trip transaction costs from gross returns."""
    cost_rate = cost_bps / 10_000
    aligned_turnover = turnover.reindex(gross_returns.index).fillna(0.0)
    net = gross_returns - cost_rate * aligned_turnover
    assert (net <= gross_returns + 1e-10).all(), "Cost model violated monotonicity!"
    return net.rename("net_return")


def annualised_cost_drag(mean_turnover: float, cost_bps: int = COST_BPS) -> float:
    """Compute the annualised cost drag (12 months × monthly cost)."""
    return 12 * (cost_bps / 10_000) * mean_turnover
