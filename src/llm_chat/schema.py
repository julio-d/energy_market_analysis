"""Plan and Result dataclasses for the LLM Q&A feature.

The Planner LLM emits a JSON object that we coerce into a ``Plan`` via
``validate_plan``. The Executor consumes a ``Plan`` and returns a ``Result``
that carries everything needed to render an answer + plot, plus a compact
``summary_for_llm`` string fed back to the Explainer LLM.

Keeping this hand-rolled (no pydantic) avoids adding a dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_cls
from typing import Any, Optional

import pandas as pd


# --- Allowed enum values --------------------------------------------------
INTENTS = {
    "extremum",
    "aggregate",
    "threshold_hours",
    "slice",
    "compare",
    "distribution",
    "top_k",
    "tariff_band",
    "negative_prices",
    "peak_offpeak",
    "streak",
    "arbitrage",
    "unsupported",
}
AGGREGATIONS = {"mean", "median", "sum", "min", "max", "std", "count"}
GROUP_BYS = {"none", "hour_of_day", "day_of_week", "month", "date"}
EXTREMUM_KINDS = {"min", "max"}
OPERATORS = {">", "<", ">=", "<=", "=="}
TOP_K_UNITS = {"hour", "day"}
TOP_K_DIRECTIONS = {"highest", "lowest"}
PEAK_OFFPEAK_PRESETS = {
    "peak_vs_offpeak",
    "weekday_vs_weekend",
    "summer_vs_winter",
}
ARBITRAGE_DIRECTIONS = {"best", "worst"}


@dataclass
class TimeWindow:
    start: Optional[date_cls] = None
    end: Optional[date_cls] = None


@dataclass
class Condition:
    op: str
    value: float


@dataclass
class Period:
    label: str
    start: Optional[date_cls] = None
    end: Optional[date_cls] = None


@dataclass
class Plan:
    intent: str
    # extremum
    extremum_kind: Optional[str] = None  # "min" | "max"
    # aggregate
    aggregation: Optional[str] = None
    group_by: str = "none"
    # threshold_hours
    conditions: list[Condition] = field(default_factory=list)
    # compare
    periods: list[Period] = field(default_factory=list)
    # distribution
    bin_width: float = 5.0
    # top_k
    k: int = 5
    top_k_unit: str = "hour"        # "hour" | "day"
    top_k_direction: str = "highest"  # "highest" | "lowest"
    # tariff_band
    tipo_ciclo: Optional[str] = None
    # peak_offpeak
    preset: Optional[str] = None
    # streak — uses `conditions` above; plus:
    min_length: int = 1
    # arbitrage
    arbitrage_direction: str = "best"   # "best" | "worst"
    arbitrage_k: int = 5
    # shared
    time_window: TimeWindow = field(default_factory=TimeWindow)
    # planner's free-form hint, used by the explainer prompt
    explanation_hint: str = ""


@dataclass
class Result:
    intent: str
    plot_kind: str  # "day" | "slice" | "bar" | "hline" | "highlight" | "none"
    summary_for_llm: str
    # Optional payloads (any subset may be set depending on plot_kind)
    value: Optional[float] = None
    timestamp: Optional[pd.Timestamp] = None
    series: Optional[pd.Series] = None
    slice_df: Optional[pd.DataFrame] = None
    mask: Optional[pd.Series] = None
    extra: dict[str, Any] = field(default_factory=dict)


class PlanValidationError(ValueError):
    """Raised when the LLM's JSON does not conform to the Plan schema."""


def _parse_date(v: Any) -> Optional[date_cls]:
    if v is None or v == "":
        return None
    try:
        return pd.Timestamp(v).date()
    except Exception as e:
        raise PlanValidationError(f"Invalid date: {v!r} ({e})")


def validate_plan(raw: dict) -> Plan:
    """Coerce a raw dict (from the LLM) into a validated ``Plan``.

    Raises :class:`PlanValidationError` with a human-readable message that
    can be fed back to the LLM as a retry hint.
    """
    if not isinstance(raw, dict):
        raise PlanValidationError("Plan must be a JSON object.")

    intent = raw.get("intent")
    if intent not in INTENTS:
        raise PlanValidationError(
            f"intent must be one of {sorted(INTENTS)}, got {intent!r}"
        )

    tw_raw = raw.get("time_window") or {}
    if not isinstance(tw_raw, dict):
        raise PlanValidationError("time_window must be an object or omitted.")
    tw = TimeWindow(
        start=_parse_date(tw_raw.get("start")),
        end=_parse_date(tw_raw.get("end")),
    )

    plan = Plan(
        intent=intent,
        time_window=tw,
        explanation_hint=str(raw.get("explanation_hint", "")),
    )

    if intent == "extremum":
        kind = raw.get("extremum_kind")
        if kind not in EXTREMUM_KINDS:
            raise PlanValidationError(
                f"extremum_kind must be one of {sorted(EXTREMUM_KINDS)}, got {kind!r}"
            )
        plan.extremum_kind = kind

    elif intent == "aggregate":
        agg = raw.get("aggregation")
        if agg not in AGGREGATIONS:
            raise PlanValidationError(
                f"aggregation must be one of {sorted(AGGREGATIONS)}, got {agg!r}"
            )
        gb = raw.get("group_by", "none") or "none"
        if gb not in GROUP_BYS:
            raise PlanValidationError(
                f"group_by must be one of {sorted(GROUP_BYS)}, got {gb!r}"
            )
        plan.aggregation = agg
        plan.group_by = gb

    elif intent == "threshold_hours":
        conds_raw = raw.get("conditions") or []
        if not isinstance(conds_raw, list) or not conds_raw:
            raise PlanValidationError(
                "threshold_hours requires a non-empty 'conditions' list."
            )
        for c in conds_raw:
            if not isinstance(c, dict):
                raise PlanValidationError("Each condition must be an object.")
            op = c.get("op")
            if op == "=":
                op = "=="
            if op not in OPERATORS:
                raise PlanValidationError(
                    f"condition.op must be one of {sorted(OPERATORS)}, got {op!r}"
                )
            try:
                value = float(c.get("value"))
            except (TypeError, ValueError):
                raise PlanValidationError(
                    f"condition.value must be a number, got {c.get('value')!r}"
                )
            plan.conditions.append(Condition(op=op, value=value))

    elif intent == "slice":
        if tw.start is None or tw.end is None:
            raise PlanValidationError(
                "slice intent requires a time_window with both start and end."
            )

    elif intent == "compare":
        agg = raw.get("aggregation", "mean") or "mean"
        if agg not in AGGREGATIONS:
            raise PlanValidationError(
                f"aggregation must be one of {sorted(AGGREGATIONS)}, got {agg!r}"
            )
        plan.aggregation = agg
        periods_raw = raw.get("periods") or []
        if not isinstance(periods_raw, list) or len(periods_raw) < 2:
            raise PlanValidationError(
                "compare requires at least 2 entries in 'periods'."
            )
        for i, p in enumerate(periods_raw):
            if not isinstance(p, dict):
                raise PlanValidationError(f"periods[{i}] must be an object.")
            label = str(p.get("label") or f"P{i + 1}")
            start = _parse_date(p.get("start"))
            end = _parse_date(p.get("end"))
            if start is None or end is None:
                raise PlanValidationError(
                    f"periods[{i}] requires both 'start' and 'end'."
                )
            plan.periods.append(Period(label=label, start=start, end=end))

    elif intent == "distribution":
        try:
            bw = float(raw.get("bin_width", 5.0))
        except (TypeError, ValueError):
            raise PlanValidationError(
                f"bin_width must be a number, got {raw.get('bin_width')!r}"
            )
        if bw <= 0:
            raise PlanValidationError("bin_width must be positive.")
        plan.bin_width = bw

    elif intent == "top_k":
        try:
            k = int(raw.get("k", 5))
        except (TypeError, ValueError):
            raise PlanValidationError(f"k must be an integer, got {raw.get('k')!r}")
        if k <= 0 or k > 100:
            raise PlanValidationError("k must be between 1 and 100.")
        unit = raw.get("top_k_unit") or raw.get("unit") or "hour"
        if unit not in TOP_K_UNITS:
            raise PlanValidationError(
                f"top_k_unit must be one of {sorted(TOP_K_UNITS)}, got {unit!r}"
            )
        direction = raw.get("top_k_direction") or raw.get("direction") or "highest"
        if direction not in TOP_K_DIRECTIONS:
            raise PlanValidationError(
                f"top_k_direction must be one of {sorted(TOP_K_DIRECTIONS)}, got {direction!r}"
            )
        plan.k = k
        plan.top_k_unit = unit
        plan.top_k_direction = direction

    elif intent == "tariff_band":
        ciclo = raw.get("tipo_ciclo")
        plan.tipo_ciclo = str(ciclo) if ciclo else None

    elif intent == "negative_prices":
        # Optional time_window only; nothing else required.
        pass

    elif intent == "peak_offpeak":
        preset = raw.get("preset", "peak_vs_offpeak") or "peak_vs_offpeak"
        if preset not in PEAK_OFFPEAK_PRESETS:
            raise PlanValidationError(
                f"preset must be one of {sorted(PEAK_OFFPEAK_PRESETS)}, got {preset!r}"
            )
        plan.preset = preset

    elif intent == "streak":
        conds_raw = raw.get("conditions") or []
        if not isinstance(conds_raw, list) or not conds_raw:
            raise PlanValidationError(
                "streak requires a non-empty 'conditions' list."
            )
        for c in conds_raw:
            if not isinstance(c, dict):
                raise PlanValidationError("Each condition must be an object.")
            op = c.get("op")
            if op == "=":
                op = "=="
            if op not in OPERATORS:
                raise PlanValidationError(
                    f"condition.op must be one of {sorted(OPERATORS)}, got {op!r}"
                )
            try:
                value = float(c.get("value"))
            except (TypeError, ValueError):
                raise PlanValidationError(
                    f"condition.value must be a number, got {c.get('value')!r}"
                )
            plan.conditions.append(Condition(op=op, value=value))
        try:
            ml = int(raw.get("min_length", 1))
        except (TypeError, ValueError):
            raise PlanValidationError("min_length must be an integer.")
        if ml < 1:
            raise PlanValidationError("min_length must be >= 1.")
        plan.min_length = ml

    elif intent == "arbitrage":
        direction = raw.get("arbitrage_direction") or raw.get("direction") or "best"
        if direction not in ARBITRAGE_DIRECTIONS:
            raise PlanValidationError(
                f"arbitrage_direction must be one of {sorted(ARBITRAGE_DIRECTIONS)}, got {direction!r}"
            )
        plan.arbitrage_direction = direction
        try:
            k = int(raw.get("arbitrage_k", raw.get("k", 5)))
        except (TypeError, ValueError):
            raise PlanValidationError("arbitrage_k must be an integer.")
        if k <= 0 or k > 100:
            raise PlanValidationError("arbitrage_k must be between 1 and 100.")
        plan.arbitrage_k = k

    # "unsupported" needs nothing else.
    return plan
