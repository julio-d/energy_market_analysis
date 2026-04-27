"""LLM planner: turn a natural-language question into a validated ``Plan``.

The free Nemotron model on OpenRouter is not guaranteed to honour strict
JSON-schema / tool-calling. Strategy:
  1. Prompt asks for a JSON object inside ```json ... ``` fences.
  2. Robust extraction: fenced block → first {...} substring → ``json.loads``.
  3. ``validate_plan`` raises a clear error on failure.
  4. On failure we retry ONCE with the validation error appended.
  5. After 2 failures, return an ``unsupported`` plan so the UI degrades gracefully.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from llm_chat.openrouter_client import OpenRouterError, chat
from llm_chat.schema import Plan, PlanValidationError, validate_plan

logger = logging.getLogger(__name__)

_FENCED_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_FIRST_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


SYSTEM_PROMPT = """You convert questions about an electricity day-ahead price time series into a strict JSON plan.

The data is a single price series in EUR/MWh, indexed by tz-naive datetime (Europe/Madrid).

Reply with ONLY a JSON object inside a ```json ... ``` fenced block. No prose outside the fence.

Schema:
{
  "intent": "extremum" | "aggregate" | "threshold_hours" | "slice"
          | "compare" | "distribution" | "top_k" | "tariff_band"
          | "negative_prices" | "peak_offpeak" | "streak" | "arbitrage"
          | "unsupported",

  "extremum_kind": "min" | "max",                       // required for extremum

  "aggregation": "mean"|"median"|"sum"|"min"|"max"|"std"|"count",
                                                        // required for aggregate and compare
  "group_by": "none"|"hour_of_day"|"day_of_week"|"month"|"date",
                                                        // aggregate only, default "none"

  "conditions": [{"op": ">"|"<"|">="|"<="|"==", "value": number}],
                                                        // required for threshold_hours and streak

  "periods": [{"label": "str", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}, ...],
                                                        // required for compare (>=2 entries)

  "bin_width": number,                                  // distribution, default 5 (EUR/MWh)

  "k": int, "top_k_unit": "hour"|"day",
  "top_k_direction": "highest"|"lowest",                // required for top_k

  "tipo_ciclo": "Tetra-Horário Ciclo Semanal" | ...,    // optional for tariff_band

  "preset": "peak_vs_offpeak"|"weekday_vs_weekend"|"summer_vs_winter",
                                                        // required for peak_offpeak

  "min_length": int,                                    // streak, default 1 (samples)

  "arbitrage_direction": "best"|"worst",                // arbitrage, default "best"
  "arbitrage_k": int,                                   // arbitrage, default 5

  "time_window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
                                                        // optional for most; required for slice

  "explanation_hint": "short note on what the user asked"
}

Choosing the intent:
- "extremum" — single highest/lowest price point.
- "aggregate" — averages, totals, counts, or grouped summaries ("by month", "per hour of day").
- "threshold_hours" — "how many hours were prices above/below X".
- "slice" — user wants to SEE a specific time range.
- "compare" — comparing two or more named periods (e.g. "Q1 vs Q2" with explicit dates).
- "distribution" — price histogram / "how are prices distributed".
- "top_k" — "top N most expensive/cheapest hours/days".
- "tariff_band" — Portuguese tariff bands (vazio, cheia, ponta, etc.).
- "negative_prices" — questions about negative-price hours / when prices went below zero.
- "peak_offpeak" — pre-canned comparisons: peak vs off-peak hours, weekday vs weekend, summer vs winter. Use this instead of "compare" when the user does not supply explicit dates.
- "streak" — longest or consecutive runs of hours/days meeting a condition ("longest stretch above X", "longest run of negative prices").
- "arbitrage" — daily max-min price spread (battery arbitrage potential). "best" = biggest spreads, "worst" = smallest.
- "unsupported" — when the question cannot be expressed above.

Rules:
- Dates MUST be inside the data window provided in the user message. Clamp if needed.
- Do NOT invent columns or metrics other than price.
- If the user follow-up refers to a previous question ("and what about August?"), inherit context from the recent turns shown in the user message.
"""


def build_df_meta(df, country: str) -> dict[str, Any]:
    """Compact metadata sent to the planner. Never includes raw rows."""
    if df is None or df.empty:
        return {"country": country, "loaded": False}
    return {
        "country": country,
        "loaded": True,
        "start": str(df.index.min().date()),
        "end": str(df.index.max().date()),
        "n_rows": int(len(df)),
        "granularity_min": _granularity_min(df),
        "price_min": round(float(df["price"].min()), 2),
        "price_max": round(float(df["price"].max()), 2),
        "price_mean": round(float(df["price"].mean()), 2),
    }


def _granularity_min(df) -> int:
    if len(df.index) < 2:
        return 60
    import pandas as pd

    delta = pd.Series(df.index).diff().dt.total_seconds().median()
    return int(round(delta / 60.0)) if delta else 60


def _extract_json(text: str) -> Optional[dict]:
    m = _FENCED_RE.search(text)
    if m:
        candidate = m.group(1)
    else:
        m = _FIRST_OBJ_RE.search(text)
        if not m:
            return None
        candidate = m.group(0)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _format_history(history: Optional[list]) -> str:
    """Render the last few turns for the planner user message."""
    if not history:
        return ""
    lines = ["Recent conversation (most recent last):"]
    for turn in history[-3:]:
        q = turn.get("question", "")
        plan_dict = turn.get("plan_dict", {})
        summary = turn.get("summary", "")
        lines.append(
            f"- Q: {q}\n  plan: {json.dumps(plan_dict, ensure_ascii=False)}\n  result: {summary}"
        )
    return "\n".join(lines) + "\n\n"


def plan_question(
    question: str,
    df_meta: dict,
    model: Optional[str] = None,
    history: Optional[list] = None,
) -> Plan:
    """Run the planner; return a validated ``Plan`` (possibly ``unsupported``).

    Parameters
    ----------
    history : list, optional
        Previous chat turns, each a dict with ``question``, ``plan_dict``, ``summary``.
        Only the last 3 are sent, to keep tokens bounded.
    """
    history_block = _format_history(history)
    user_msg = (
        f"Data window: {json.dumps(df_meta)}\n\n"
        f"{history_block}"
        f"Question: {question}\n\n"
        f"Return the JSON plan now."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    last_error: Optional[str] = None
    for attempt in range(2):
        # First attempt requests json_mode; on retry we drop it in case the
        # model rejected it (some free models return 400 on response_format).
        try:
            raw_text = chat(
                messages,
                model=model,
                temperature=0.0,
                max_tokens=500,
                json_mode=(attempt == 0),
            )
        except OpenRouterError as e:
            # If json_mode was the trigger, retry once without it.
            if attempt == 0 and "response_format" in str(e).lower():
                try:
                    raw_text = chat(
                        messages,
                        model=model,
                        temperature=0.0,
                        max_tokens=500,
                        json_mode=False,
                    )
                except OpenRouterError as e2:
                    logger.warning("planner LLM call failed: %s", e2)
                    return Plan(intent="unsupported", explanation_hint=f"LLM error: {e2}")
            else:
                logger.warning("planner LLM call failed: %s", e)
                return Plan(intent="unsupported", explanation_hint=f"LLM error: {e}")

        parsed = _extract_json(raw_text)
        if parsed is None:
            last_error = "Reply did not contain a parseable JSON object."
        else:
            try:
                return validate_plan(parsed)
            except PlanValidationError as e:
                last_error = str(e)

        # Retry once with the error fed back.
        if attempt == 0:
            messages.append({"role": "assistant", "content": raw_text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Your previous reply was invalid: {last_error}. "
                        "Reply again with ONLY a valid JSON plan inside a "
                        "```json fenced block."
                    ),
                }
            )

    logger.info("planner gave up after retry; last_error=%s", last_error)
    return Plan(
        intent="unsupported",
        explanation_hint=f"could not parse plan: {last_error}",
    )
