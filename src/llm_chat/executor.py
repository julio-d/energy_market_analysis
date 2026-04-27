"""Deterministic executor that turns a validated ``Plan`` into a ``Result``.

No LLM involvement here. Operates on the in-memory MIBEL DataFrame which
has a tz-naive ``DatetimeIndex`` and a single ``price`` column (€/MWh).
"""

from __future__ import annotations

import operator as op_mod

import pandas as pd

from llm_chat.schema import Plan, Result


_OP_FUNCS = {
    ">": op_mod.gt,
    "<": op_mod.lt,
    ">=": op_mod.ge,
    "<=": op_mod.le,
    "==": op_mod.eq,
}


def _apply_window(df: pd.DataFrame, plan: Plan) -> pd.DataFrame:
    """Slice df to plan.time_window, clamping to the loaded range."""
    if plan.time_window.start is None and plan.time_window.end is None:
        return df
    start = plan.time_window.start
    end = plan.time_window.end
    lo = pd.Timestamp(start) if start else df.index.min()
    # End-of-day inclusive
    hi = (
        pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        if end
        else df.index.max()
    )
    return df.loc[(df.index >= lo) & (df.index <= hi)]


def _execute_extremum(df: pd.DataFrame, plan: Plan) -> Result:
    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="extremum",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )
    if plan.extremum_kind == "max":
        idx = sub["price"].idxmax()
    else:
        idx = sub["price"].idxmin()
    value = float(sub.loc[idx, "price"])
    ts = pd.Timestamp(idx)

    # Day-slice for plotting: full day containing the extremum.
    day_start = ts.normalize()
    day_end = day_start + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    day_df = df.loc[(df.index >= day_start) & (df.index <= day_end)].copy()

    summary = (
        f"{plan.extremum_kind}_price={value:.2f} EUR/MWh at "
        f"{ts.strftime('%Y-%m-%d %H:%M')}"
    )
    return Result(
        intent="extremum",
        plot_kind="day",
        summary_for_llm=summary,
        value=value,
        timestamp=ts,
        slice_df=day_df,
    )


def _execute_aggregate(df: pd.DataFrame, plan: Plan) -> Result:
    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="aggregate",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )

    agg = plan.aggregation
    gb = plan.group_by

    if gb == "none":
        value = float(getattr(sub["price"], agg)())
        summary = (
            f"{agg}(price)={value:.2f} EUR/MWh over "
            f"{sub.index.min().date()} → {sub.index.max().date()} ({len(sub)} samples)"
        )
        return Result(
            intent="aggregate",
            plot_kind="hline",
            summary_for_llm=summary,
            value=value,
            slice_df=sub,
        )

    # Grouped
    idx = pd.to_datetime(sub.index)
    if gb == "hour_of_day":
        key = idx.hour
        key_name = "hour_of_day"
    elif gb == "day_of_week":
        key = idx.dayofweek  # 0=Monday
        key_name = "day_of_week"
    elif gb == "month":
        key = idx.month
        key_name = "month"
    elif gb == "date":
        key = idx.date
        key_name = "date"
    else:
        # Defensive; validate_plan should have caught this.
        raise ValueError(f"unknown group_by: {gb}")

    grouped = sub["price"].groupby(key).agg(agg)
    grouped.index.name = key_name

    # Compact summary: top 3 highest + lowest groups.
    top = grouped.nlargest(3)
    bot = grouped.nsmallest(3)
    summary = (
        f"{agg}(price) by {key_name} ({len(grouped)} groups). "
        f"Top: {top.round(2).to_dict()}. Bottom: {bot.round(2).to_dict()}."
    )
    return Result(
        intent="aggregate",
        plot_kind="bar",
        summary_for_llm=summary,
        series=grouped,
        slice_df=sub,
    )


def _execute_threshold_hours(df: pd.DataFrame, plan: Plan) -> Result:
    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="threshold_hours",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )

    mask = pd.Series(True, index=sub.index)
    parts = []
    for c in plan.conditions:
        f = _OP_FUNCS[c.op]
        mask &= f(sub["price"], c.value)
        parts.append(f"price {c.op} {c.value:g}")

    # Approx hours per sample from the median timedelta.
    if len(sub.index) > 1:
        step_hours = (
            pd.Series(sub.index).diff().dt.total_seconds().median() / 3600.0
        )
    else:
        step_hours = 1.0
    matching_samples = int(mask.sum())
    matching_hours = matching_samples * step_hours
    total_hours = len(sub) * step_hours
    pct = (matching_hours / total_hours * 100.0) if total_hours else 0.0

    cond_label = " AND ".join(parts)
    summary = (
        f"{matching_hours:.2f}h matching ({cond_label}) out of {total_hours:.2f}h "
        f"({pct:.2f}%) over {sub.index.min().date()} → {sub.index.max().date()}"
    )
    # Full mask aligned to df (False outside the window) for highlight plotting.
    full_mask = pd.Series(False, index=df.index)
    full_mask.loc[mask.index] = mask.values
    return Result(
        intent="threshold_hours",
        plot_kind="highlight",
        summary_for_llm=summary,
        value=matching_hours,
        mask=full_mask,
        slice_df=df,
        extra={
            "matching_hours": matching_hours,
            "total_hours": total_hours,
            "pct": pct,
            "conditions_label": cond_label,
        },
    )


def _execute_slice(df: pd.DataFrame, plan: Plan) -> Result:
    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="slice",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )
    summary = (
        f"slice {sub.index.min()} → {sub.index.max()}: "
        f"mean={sub['price'].mean():.2f}, min={sub['price'].min():.2f}, "
        f"max={sub['price'].max():.2f}, n={len(sub)}"
    )
    return Result(
        intent="slice",
        plot_kind="slice",
        summary_for_llm=summary,
        slice_df=sub,
    )


def _apply_period(df: pd.DataFrame, start, end) -> pd.DataFrame:
    lo = pd.Timestamp(start)
    hi = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return df.loc[(df.index >= lo) & (df.index <= hi)]


def _execute_compare(df: pd.DataFrame, plan: Plan) -> Result:
    agg = plan.aggregation or "mean"
    values = {}
    for p in plan.periods:
        sub = _apply_period(df, p.start, p.end)
        if sub.empty:
            values[p.label] = float("nan")
        else:
            values[p.label] = float(getattr(sub["price"], agg)())
    series = pd.Series(values, name=f"{agg}_price")
    series.index.name = "period"

    parts = ", ".join(
        f"{lbl}={v:.2f}" for lbl, v in values.items() if pd.notna(v)
    )
    summary = f"compare {agg}(price) across periods: {parts} (EUR/MWh)"
    return Result(
        intent="compare",
        plot_kind="bar",
        summary_for_llm=summary,
        series=series,
    )


def _execute_distribution(df: pd.DataFrame, plan: Plan) -> Result:
    from price_distribution import compute_price_histogram

    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="distribution",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )
    bin_edges, hours_per_bin, _ = compute_price_histogram(
        sub, bin_width=plan.bin_width
    )
    # Build a bar-friendly Series keyed by bin midpoint label.
    labels = [
        f"{bin_edges[i]:g} to {bin_edges[i + 1]:g}"
        for i in range(len(bin_edges) - 1)
    ]
    series = pd.Series(hours_per_bin, index=labels, name="hours")
    series.index.name = "price_bin"

    top = series.nlargest(3)
    summary = (
        f"price distribution (bin={plan.bin_width:g} EUR/MWh) over "
        f"{sub.index.min().date()} -> {sub.index.max().date()}. "
        f"Busiest bins: {top.round(1).to_dict()}"
    )
    return Result(
        intent="distribution",
        plot_kind="bar",
        summary_for_llm=summary,
        series=series,
        slice_df=sub,
    )


def _execute_top_k(df: pd.DataFrame, plan: Plan) -> Result:
    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="top_k",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )

    if plan.top_k_unit == "day":
        daily = sub["price"].groupby(sub.index.date).mean()
        daily.index = pd.to_datetime(daily.index)
        picker = daily.nlargest if plan.top_k_direction == "highest" else daily.nsmallest
        picked = picker(plan.k).sort_values(
            ascending=(plan.top_k_direction == "lowest")
        )
        unit_label = "daily mean"
    else:
        picker = sub["price"].nlargest if plan.top_k_direction == "highest" else sub["price"].nsmallest
        picked = picker(plan.k).sort_values(
            ascending=(plan.top_k_direction == "lowest")
        )
        unit_label = "hourly"

    # Build a label-indexed series for bar plotting.
    labels = [pd.Timestamp(i).strftime("%Y-%m-%d %H:%M" if plan.top_k_unit == "hour" else "%Y-%m-%d") for i in picked.index]
    series = pd.Series(picked.values, index=labels, name="price")
    series.index.name = f"top_{plan.k}_{plan.top_k_direction}_{plan.top_k_unit}"

    # Mask for highlight plot: mark those timestamps on the full series.
    if plan.top_k_unit == "hour":
        mask = pd.Series(False, index=df.index)
        mask.loc[picked.index] = True
    else:
        # Highlight every sample belonging to a picked date.
        picked_dates = set(pd.to_datetime(picked.index).date)
        mask = pd.Series(
            [d in picked_dates for d in df.index.date],
            index=df.index,
        )

    summary = (
        f"top {plan.k} {plan.top_k_direction} {unit_label} prices: "
        f"{series.round(2).to_dict()} (EUR/MWh)"
    )
    return Result(
        intent="top_k",
        plot_kind="highlight",
        summary_for_llm=summary,
        series=series,
        slice_df=df,
        mask=mask,
        extra={"conditions_label": f"top {plan.k} {plan.top_k_direction} {unit_label}"},
    )


def _execute_tariff_band(df: pd.DataFrame, plan: Plan) -> Result:
    from tariff_utils import compute_band_averages, get_tipo_ciclo_options

    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="tariff_band",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )

    ciclo = plan.tipo_ciclo
    valid = get_tipo_ciclo_options()
    if not ciclo or ciclo not in valid:
        ciclo = "Tetra-Horário Ciclo Semanal" if "Tetra-Horário Ciclo Semanal" in valid else valid[0]

    table = compute_band_averages(sub, ciclo)
    if table is None or table.empty:
        return Result(
            intent="tariff_band",
            plot_kind="none",
            summary_for_llm=f"no tariff band data for ciclo={ciclo!r}",
        )
    series = pd.Series(
        table["Average Price (€/MWh)"].values,
        index=table["Period"].values,
        name="price",
    )
    series.index.name = "band"

    summary = (
        f"average price by tariff band (ciclo={ciclo}): "
        f"{series.round(2).to_dict()} (EUR/MWh)"
    )
    return Result(
        intent="tariff_band",
        plot_kind="bar",
        summary_for_llm=summary,
        series=series,
        extra={"tipo_ciclo": ciclo},
    )


def _execute_negative_prices(df: pd.DataFrame, plan: Plan) -> Result:
    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="negative_prices",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )

    if len(sub.index) > 1:
        step_hours = (
            pd.Series(sub.index).diff().dt.total_seconds().median() / 3600.0
        )
    else:
        step_hours = 1.0

    mask_sub = sub["price"] < 0
    neg_samples = int(mask_sub.sum())
    neg_hours = neg_samples * step_hours
    total_hours = len(sub) * step_hours
    pct = (neg_hours / total_hours * 100.0) if total_hours else 0.0

    if neg_samples == 0:
        summary = (
            f"no negative prices over {sub.index.min().date()} -> {sub.index.max().date()} "
            f"({total_hours:.0f}h examined)"
        )
        return Result(
            intent="negative_prices",
            plot_kind="none",
            summary_for_llm=summary,
        )

    neg_prices = sub.loc[mask_sub, "price"]
    min_price = float(neg_prices.min())
    min_ts = pd.Timestamp(neg_prices.idxmin())
    by_hour = neg_prices.groupby(neg_prices.index.hour).size()
    top_hours = by_hour.nlargest(3)

    full_mask = pd.Series(False, index=df.index)
    full_mask.loc[mask_sub.index] = mask_sub.values

    summary = (
        f"{neg_hours:.2f}h of negative prices ({pct:.2f}% of period). "
        f"Minimum: {min_price:.2f} EUR/MWh at {min_ts.strftime('%Y-%m-%d %H:%M')}. "
        f"Most common hours of day: {top_hours.to_dict()}"
    )
    return Result(
        intent="negative_prices",
        plot_kind="highlight",
        summary_for_llm=summary,
        value=neg_hours,
        slice_df=df,
        mask=full_mask,
        extra={
            "negative_hours": neg_hours,
            "pct": pct,
            "min_price": min_price,
            "min_timestamp": str(min_ts),
            "conditions_label": "price < 0",
        },
    )


_PEAK_HOURS = set(range(18, 23))          # 18..22 inclusive
_OFFPEAK_HOURS = set(range(0, 7))         # 0..6 inclusive
_SUMMER_MONTHS = {6, 7, 8, 9}
_WINTER_MONTHS = {12, 1, 2}


def _execute_peak_offpeak(df: pd.DataFrame, plan: Plan) -> Result:
    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="peak_offpeak",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )
    preset = plan.preset or "peak_vs_offpeak"
    idx = sub.index

    if preset == "peak_vs_offpeak":
        a_mask = idx.hour.isin(_PEAK_HOURS)
        b_mask = idx.hour.isin(_OFFPEAK_HOURS)
        a_label = "Peak (18-22h)"
        b_label = "Off-peak (0-6h)"
    elif preset == "weekday_vs_weekend":
        a_mask = idx.dayofweek < 5
        b_mask = idx.dayofweek >= 5
        a_label = "Weekday"
        b_label = "Weekend"
    else:  # summer_vs_winter
        a_mask = idx.month.isin(_SUMMER_MONTHS)
        b_mask = idx.month.isin(_WINTER_MONTHS)
        a_label = "Summer (Jun-Sep)"
        b_label = "Winter (Dec-Feb)"

    a_mean = float(sub.loc[a_mask, "price"].mean()) if a_mask.any() else float("nan")
    b_mean = float(sub.loc[b_mask, "price"].mean()) if b_mask.any() else float("nan")
    series = pd.Series({a_label: a_mean, b_label: b_mean}, name="mean_price")
    series.index.name = "group"

    diff = a_mean - b_mean if pd.notna(a_mean) and pd.notna(b_mean) else float("nan")
    summary = (
        f"{preset}: {a_label}={a_mean:.2f} EUR/MWh, {b_label}={b_mean:.2f} EUR/MWh "
        f"(difference={diff:+.2f} EUR/MWh)"
    )
    return Result(
        intent="peak_offpeak",
        plot_kind="bar",
        summary_for_llm=summary,
        series=series,
        extra={"preset": preset},
    )


def _execute_streak(df: pd.DataFrame, plan: Plan) -> Result:
    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="streak",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )

    if len(sub.index) > 1:
        step_hours = (
            pd.Series(sub.index).diff().dt.total_seconds().median() / 3600.0
        )
    else:
        step_hours = 1.0

    mask = pd.Series(True, index=sub.index)
    parts = []
    for c in plan.conditions:
        f = _OP_FUNCS[c.op]
        mask &= f(sub["price"], c.value)
        parts.append(f"price {c.op} {c.value:g}")
    cond_label = " AND ".join(parts)

    # Find consecutive runs of True.
    values = mask.values
    runs: list[dict] = []
    i = 0
    n = len(values)
    while i < n:
        if values[i]:
            j = i
            while j < n and values[j]:
                j += 1
            length = j - i
            if length >= plan.min_length:
                runs.append(
                    {
                        "length": length,
                        "hours": length * step_hours,
                        "start": sub.index[i],
                        "end": sub.index[j - 1],
                    }
                )
            i = j
        else:
            i += 1

    if not runs:
        return Result(
            intent="streak",
            plot_kind="none",
            summary_for_llm=(
                f"no streaks of {cond_label} with length >= {plan.min_length} "
                f"over {sub.index.min().date()} -> {sub.index.max().date()}"
            ),
        )

    runs.sort(key=lambda r: r["length"], reverse=True)
    longest = runs[0]
    top = runs[: min(5, len(runs))]

    # Highlight the longest streak on the full series.
    full_mask = pd.Series(False, index=df.index)
    full_mask.loc[longest["start"] : longest["end"]] = True

    top_desc = "; ".join(
        f"{r['hours']:.1f}h ({pd.Timestamp(r['start']).strftime('%Y-%m-%d %H:%M')} "
        f"-> {pd.Timestamp(r['end']).strftime('%Y-%m-%d %H:%M')})"
        for r in top
    )
    summary = (
        f"{len(runs)} streak(s) of {cond_label} "
        f"(min_length={plan.min_length}). "
        f"Longest: {longest['hours']:.1f}h. "
        f"Top runs: {top_desc}"
    )
    return Result(
        intent="streak",
        plot_kind="highlight",
        summary_for_llm=summary,
        value=float(longest["hours"]),
        slice_df=df,
        mask=full_mask,
        extra={
            "num_streaks": len(runs),
            "longest_hours": longest["hours"],
            "conditions_label": f"longest streak {cond_label}",
        },
    )


def _execute_arbitrage(df: pd.DataFrame, plan: Plan) -> Result:
    sub = _apply_window(df, plan)
    if sub.empty:
        return Result(
            intent="arbitrage",
            plot_kind="none",
            summary_for_llm="no data in the requested window",
        )

    daily = sub["price"].groupby(sub.index.date).agg(["min", "max"])
    daily["spread"] = daily["max"] - daily["min"]

    avg_spread = float(daily["spread"].mean())
    total_days = len(daily)

    asc = plan.arbitrage_direction == "worst"
    picked = daily["spread"].sort_values(ascending=asc).head(plan.arbitrage_k)
    # Keep chronological within the picked set for readability.
    picked = picked.sort_index()

    labels = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in picked.index]
    series = pd.Series(picked.values, index=labels, name="spread_EUR_per_MWh")
    series.index.name = f"top_{plan.arbitrage_k}_{plan.arbitrage_direction}_days"

    best_day = daily["spread"].idxmax()
    best_val = float(daily["spread"].max())
    worst_day = daily["spread"].idxmin()
    worst_val = float(daily["spread"].min())

    summary = (
        f"arbitrage spread over {total_days} days: "
        f"avg={avg_spread:.2f} EUR/MWh, "
        f"best={best_val:.2f} on {best_day}, worst={worst_val:.2f} on {worst_day}. "
        f"{plan.arbitrage_direction.capitalize()} {plan.arbitrage_k}: "
        f"{series.round(2).to_dict()}"
    )
    return Result(
        intent="arbitrage",
        plot_kind="bar",
        summary_for_llm=summary,
        value=avg_spread,
        series=series,
        extra={
            "avg_spread": avg_spread,
            "best_day": str(best_day),
            "best_spread": best_val,
            "worst_day": str(worst_day),
            "worst_spread": worst_val,
            "total_days": total_days,
            "direction": plan.arbitrage_direction,
        },
    )


def execute(plan: Plan, df: pd.DataFrame) -> Result:
    """Dispatch to the per-intent executor."""
    if df is None or df.empty:
        return Result(
            intent=plan.intent,
            plot_kind="none",
            summary_for_llm="no data loaded",
        )
    if plan.intent == "extremum":
        return _execute_extremum(df, plan)
    if plan.intent == "aggregate":
        return _execute_aggregate(df, plan)
    if plan.intent == "threshold_hours":
        return _execute_threshold_hours(df, plan)
    if plan.intent == "slice":
        return _execute_slice(df, plan)
    if plan.intent == "compare":
        return _execute_compare(df, plan)
    if plan.intent == "distribution":
        return _execute_distribution(df, plan)
    if plan.intent == "top_k":
        return _execute_top_k(df, plan)
    if plan.intent == "tariff_band":
        return _execute_tariff_band(df, plan)
    if plan.intent == "negative_prices":
        return _execute_negative_prices(df, plan)
    if plan.intent == "peak_offpeak":
        return _execute_peak_offpeak(df, plan)
    if plan.intent == "streak":
        return _execute_streak(df, plan)
    if plan.intent == "arbitrage":
        return _execute_arbitrage(df, plan)
    if plan.intent == "unsupported":
        return Result(
            intent="unsupported",
            plot_kind="none",
            summary_for_llm="question is outside the supported intents",
        )
    raise ValueError(f"unknown intent: {plan.intent}")
