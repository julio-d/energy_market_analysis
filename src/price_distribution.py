"""Utilities for price distribution analysis on spot-market time series.

Pure functions (no Streamlit) operating on a DataFrame with a datetime index
and a ``price`` column. Observations are weighted by the inferred sampling
step so that results are expressed in hours regardless of native granularity
(15-min or hourly).
"""
from __future__ import annotations

import math
from typing import Tuple

import numpy as np
import pandas as pd


def infer_step_hours(df: pd.DataFrame) -> float:
    """Return median spacing between consecutive index entries, in hours.

    Falls back to 1.0 if the index has fewer than two entries or the diff
    cannot be computed.
    """
    if df is None or len(df.index) < 2:
        return 1.0
    try:
        deltas = pd.Series(df.index).diff().dropna()
        if deltas.empty:
            return 1.0
        step = deltas.median().total_seconds() / 3600.0
        if step <= 0 or math.isnan(step):
            return 1.0
        return float(step)
    except Exception:
        return 1.0


def compute_price_histogram(
    df: pd.DataFrame, bin_width: float = 5.0
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Compute a price histogram weighted by step hours.

    Returns ``(bin_edges, hours_per_bin, step_hours)``. Bin edges run from
    ``floor(min/bin_width)*bin_width`` to ``ceil(max/bin_width)*bin_width``.
    An empty/None input yields empty arrays.
    """
    if df is None or df.empty or "price" not in df.columns:
        return np.array([]), np.array([]), 1.0

    prices = df["price"].dropna().to_numpy()
    if prices.size == 0:
        return np.array([]), np.array([]), 1.0

    step_hours = infer_step_hours(df)

    lo = math.floor(prices.min() / bin_width) * bin_width
    hi = math.ceil(prices.max() / bin_width) * bin_width
    if hi <= lo:
        hi = lo + bin_width

    edges = np.arange(lo, hi + bin_width / 2, bin_width)
    counts, _ = np.histogram(prices, bins=edges)
    hours = counts.astype(float) * step_hours
    return edges, hours, step_hours


_OPERATORS = {
    ">": lambda s, v: s > v,
    "<": lambda s, v: s < v,
    ">=": lambda s, v: s >= v,
    "<=": lambda s, v: s <= v,
    "=": lambda s, v: s == v,
}


def count_hours_matching(df: pd.DataFrame, operator: str, threshold: float) -> Tuple[float, float]:
    """Return ``(matching_hours, total_hours)`` for a single condition."""
    return count_hours_matching_conditions(df, [(operator, threshold)])


def count_hours_matching_conditions(df: pd.DataFrame, conditions) -> Tuple[float, float]:
    """Return ``(matching_hours, total_hours)`` for an AND of conditions.

    ``conditions`` is an iterable of ``(operator, threshold)`` pairs.
    Operators must be in ``>``, ``<``, ``>=``, ``<=``, ``=``.
    An empty conditions list matches every sample.
    """
    if df is None or df.empty or "price" not in df.columns:
        return 0.0, 0.0

    step_hours = infer_step_hours(df)
    prices = df["price"].dropna()
    total_hours = float(len(prices)) * step_hours

    mask = pd.Series(True, index=prices.index)
    for operator, threshold in conditions:
        if operator not in _OPERATORS:
            raise ValueError(f"Unsupported operator: {operator}")
        mask &= _OPERATORS[operator](prices, threshold)
    matching_hours = float(mask.sum()) * step_hours
    return matching_hours, total_hours
