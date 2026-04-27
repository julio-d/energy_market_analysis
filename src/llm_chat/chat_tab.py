"""LLM chat UI for the MIBEL tab.

Single-shot, data-aware Q&A box. Plans -> executes -> explains -> plots.
Only the most recent turn is kept on screen.
"""

from __future__ import annotations

import logging
import time

import pandas as pd
import streamlit as st

from llm_chat.executor import execute
from llm_chat.explainer import explain
from llm_chat.openrouter_client import OpenRouterError
from llm_chat.plot_rules import build_figure
from llm_chat.planner import build_df_meta, plan_question

logger = logging.getLogger(__name__)

_LAST_TURN_KEY = "llm_chat_last_turn"
_TURN_COUNTER_KEY = "llm_chat_turn_counter"
_MAX_QUESTION_CHARS = 500


def _render_last_turn(entry: dict) -> None:
    """Render the single most recent Q&A. No history is kept."""
    with st.chat_message("user"):
        st.markdown(entry["question"])
    with st.chat_message("assistant"):
        st.markdown(entry["answer"])
        fig = entry.get("fig")
        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"llm_fig_{entry.get('turn', 0)}",
            )


def render_chat_tab(df: pd.DataFrame, country: str) -> None:
    """Render the data-aware LLM Q&A box.

    Parameters
    ----------
    df : pd.DataFrame
        The currently-loaded MIBEL price DataFrame (datetime index + ``price``).
    country : str
        Country label for context passed to the planner.
    """
    st.markdown("### 💬 Ask the data")
    st.caption(
        "Ask about prices, averages, thresholds, arbitrage, negative prices, "
        "streaks, peak vs off-peak, tariff bands, and more."
    )

    if df is None or df.empty:
        st.info("Load data first to enable the chat.")
        return

    with st.form(key="llm_chat_form", clear_on_submit=True):
        question = st.text_input(
            "Your question",
            key="llm_chat_question_input",
            placeholder="What were the best 5 days for battery arbitrage?",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Ask", type="primary")

    if submitted and question and question.strip():
        # Hard cap on input length to limit token usage and abuse.
        question = question.strip()
        if len(question) > _MAX_QUESTION_CHARS:
            question = question[:_MAX_QUESTION_CHARS]
            st.warning(
                f"Question was truncated to {_MAX_QUESTION_CHARS} characters."
            )

        # Single-shot: forget the previous turn before processing.
        st.session_state.pop(_LAST_TURN_KEY, None)

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                df_meta = build_df_meta(df, country=country)
                try:
                    plan = plan_question(question, df_meta)
                    result = execute(plan, df)
                    answer = explain(question, plan, result)
                    fig = build_figure(result)
                except OpenRouterError as e:
                    logger.warning("OpenRouter call failed: %s", e)
                    st.error(
                        "Sorry, the language model is unavailable right now. "
                        "Please try again in a moment."
                    )
                    return
                except Exception:  # noqa: BLE001
                    # Full traceback goes to the server log; users see only a
                    # generic message to avoid leaking internal paths/state.
                    logger.exception("chat_tab unexpected error")
                    st.error(
                        "Something went wrong while processing your question. "
                        "Please try a different phrasing or try again later."
                    )
                    return

            st.markdown(answer)
            turn_id = st.session_state.get(_TURN_COUNTER_KEY, 0) + 1
            if fig is not None:
                st.plotly_chart(
                    fig, use_container_width=True, key=f"llm_fig_new_{turn_id}"
                )

        st.session_state[_TURN_COUNTER_KEY] = turn_id
        st.session_state[_LAST_TURN_KEY] = {
            "question": question,
            "answer": answer,
            "fig": fig,
            "turn": turn_id,
        }
    else:
        # No new question this rerun — re-render the last turn if any
        # (e.g., after interacting with a Plotly chart triggers a rerun).
        last = st.session_state.get(_LAST_TURN_KEY)
        if last is not None:
            _render_last_turn(last)
