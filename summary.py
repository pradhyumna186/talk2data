from __future__ import annotations

from typing import Optional

import pandas as pd


def summarize_results(df: pd.DataFrame, question: str) -> str:
    """
    Produce a simple natural language summary of the query results.
    This is heuristic and works best with the shapes produced by `question_to_sql`.
    """
    if df.empty:
        return "No data matched your question. Try broadening the time range or removing filters."

    # Aggregated: dimension + value
    if set(df.columns) >= {"dimension", "value"} and len(df.columns) == 2:
        return _summarize_aggregated(df, question)

    # Single value
    if "value" in df.columns and len(df) == 1:
        val = df["value"].iloc[0]
        return f"The computed value for your question is **{val:,.2f}**."

    # Fallback: row-level summary
    return _summarize_rows(df, question)


def _summarize_aggregated(df: pd.DataFrame, question: str) -> str:
    df_sorted = df.sort_values("value", ascending=False)
    top = df_sorted.iloc[0]
    bottom = df_sorted.iloc[-1]

    parts = []
    parts.append(
        f"The highest value is for **{top['dimension']}** with **{top['value']:,.2f}**."
    )
    if len(df_sorted) > 1 and top["dimension"] != bottom["dimension"]:
        parts.append(
            f"The lowest value is for **{bottom['dimension']}** with **{bottom['value']:,.2f}**."
        )
    if len(df_sorted) > 2:
        parts.append(
            f"There are **{len(df_sorted)}** distinct values in total based on your grouping."
        )
    return " ".join(parts)


def _summarize_rows(df: pd.DataFrame, question: str) -> str:
    n_rows = len(df)
    total_revenue: Optional[float] = None
    if "revenue" in df.columns:
        total_revenue = float(df["revenue"].sum())

    parts = [f"Returned **{n_rows}** rows matching your question."]
    if total_revenue is not None:
        parts.append(f"The total revenue across these rows is **{total_revenue:,.2f}**.")
    return " ".join(parts)

