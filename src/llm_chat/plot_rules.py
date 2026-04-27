"""Map an executor ``Result`` to a Plotly figure.

The plot kind is decided by the executor (deterministic), so the LLM never
chooses chart types.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from llm_chat.schema import Result


_DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_LABELS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def build_figure(result: Result) -> Optional[go.Figure]:
    """Return a Plotly figure for the result, or None when unplottable."""
    kind = result.plot_kind
    if kind == "none":
        return None
    if kind == "day":
        return _plot_day(result)
    if kind == "slice":
        return _plot_slice(result)
    if kind == "bar":
        return _plot_bar(result)
    if kind == "hline":
        return _plot_hline(result)
    if kind == "highlight":
        return _plot_highlight(result)
    return None


def _plot_day(r: Result) -> Optional[go.Figure]:
    df = r.slice_df
    if df is None or df.empty:
        return None
    fig = px.line(df, x=df.index, y="price")
    if r.timestamp is not None and r.value is not None:
        fig.add_scatter(
            x=[r.timestamp],
            y=[r.value],
            mode="markers",
            marker=dict(size=12, color="red", symbol="star"),
            name=f"{r.value:.2f} €/MWh",
            hovertemplate=f"{r.timestamp}<br>%{{y:.2f}} €/MWh<extra></extra>",
        )
    fig.update_layout(
        title=f"Day containing the answer ({df.index.min().date()})",
        xaxis_title="Time",
        yaxis_title="Price (€/MWh)",
    )
    return fig


def _plot_slice(r: Result) -> Optional[go.Figure]:
    df = r.slice_df
    if df is None or df.empty:
        return None
    fig = px.line(df, x=df.index, y="price")
    fig.update_layout(
        title=f"Prices {df.index.min().date()} → {df.index.max().date()}",
        xaxis_title="Time",
        yaxis_title="Price (€/MWh)",
    )
    return fig


def _plot_hline(r: Result) -> Optional[go.Figure]:
    df = r.slice_df
    if df is None or df.empty or r.value is None:
        return None
    fig = px.line(df, x=df.index, y="price")
    fig.add_hline(
        y=r.value,
        line_dash="dash",
        line_color="red",
        annotation_text=f"{r.value:.2f} €/MWh",
        annotation_position="top right",
    )
    fig.update_layout(
        title=f"Prices with reference line ({df.index.min().date()} → {df.index.max().date()})",
        xaxis_title="Time",
        yaxis_title="Price (€/MWh)",
    )
    return fig


def _plot_bar(r: Result) -> Optional[go.Figure]:
    s = r.series
    if s is None or s.empty:
        return None
    name = s.index.name or "group"
    df = s.reset_index()
    df.columns = [name, "price"]

    # Pretty labels for known groupings.
    if name == "day_of_week":
        df[name] = df[name].map(lambda i: _DOW_LABELS[int(i)] if 0 <= int(i) < 7 else str(i))
    elif name == "month":
        df[name] = df[name].map(lambda i: _MONTH_LABELS[int(i) - 1] if 1 <= int(i) <= 12 else str(i))
    elif name == "date":
        df[name] = df[name].astype(str)

    fig = px.bar(df, x=name, y="price")
    fig.update_layout(
        title=f"Price by {name}",
        xaxis_title=name,
        yaxis_title="Price (€/MWh)",
    )
    return fig


def _plot_highlight(r: Result) -> Optional[go.Figure]:
    df = r.slice_df
    mask = r.mask
    if df is None or df.empty or mask is None:
        return None
    fig = px.line(df, x=df.index, y="price")
    fig.update_traces(name="All prices", showlegend=True)
    matching = df.loc[mask.reindex(df.index, fill_value=False)]
    if not matching.empty:
        fig.add_scatter(
            x=matching.index,
            y=matching["price"],
            mode="markers",
            marker=dict(size=5, color="red"),
            name="Matching",
            hovertemplate="%{x}<br>%{y:.2f} €/MWh<extra></extra>",
        )
    cond = r.extra.get("conditions_label", "condition")
    fig.update_layout(
        title=f"Prices with hours matching {cond} highlighted",
        xaxis_title="Time",
        yaxis_title="Price (€/MWh)",
    )
    return fig
