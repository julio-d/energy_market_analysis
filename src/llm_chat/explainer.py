"""Second LLM call: turn an executor ``Result`` into a 1-3 sentence answer.

We pass only the compact ``summary_for_llm`` string, never the raw series,
to keep tokens and latency low. If the LLM call fails we fall back to the
summary verbatim so the user still sees a useful answer.
"""

from __future__ import annotations

import logging
from typing import Optional

from llm_chat.openrouter_client import OpenRouterError, chat
from llm_chat.schema import Plan, Result

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a concise energy-market analyst. Given the user's question, the "
    "structured plan that was executed, and the numeric result summary, write "
    "a clear 1-3 sentence answer in the same language as the question. "
    "Use the numbers from the summary verbatim. Do NOT invent extra figures. "
    "Mention units (€/MWh, hours, %) where relevant."
)


def explain(
    question: str,
    plan: Plan,
    result: Result,
    model: Optional[str] = None,
) -> str:
    """Return a human-readable answer; never raises."""
    if result.intent == "unsupported":
        return (
            "Sorry, I couldn't translate that question into a supported "
            "operation. Try asking about the highest/lowest price, an average, "
            "hours above/below a threshold, or to show a specific date range."
        )
    if result.plot_kind == "none":
        return f"No data matched: {result.summary_for_llm}"

    user_msg = (
        f"Question: {question}\n"
        f"Plan intent: {plan.intent}\n"
        f"Result summary: {result.summary_for_llm}\n\n"
        f"Write the answer now."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    try:
        return chat(messages, model=model, temperature=0.2, max_tokens=600).strip()
    except OpenRouterError as e:
        logger.warning("explainer LLM call failed: %s", e)
        # Graceful fallback: just show the deterministic summary.
        return result.summary_for_llm
