"""
charts.py — Visualization builders for Kelola

Contains Sankey diagram construction and the SVG text-stroke cleanup renderer.
"""

import re

import plotly.graph_objects as go
import streamlit.components.v1 as components

from parser import format_idr
from categories import PAYMENT_CATEGORIES


def build_sankey(dataframe, payment_categories=None) -> go.Figure | None:
    """
    Build an interactive Sankey diagram.

    Layout: [Account/Source] -> [Expense Categories]
    Excludes card payments (Pembayaran Kartu) — those are balance settlements,
    not real spending.
    """
    if payment_categories is None:
        payment_categories = PAYMENT_CATEGORIES

    if dataframe.empty:
        return None

    expense_rows = dataframe[
        (dataframe["transaction_type"] == "expense") &
        (~dataframe["category"].isin(payment_categories))
    ]

    if expense_rows.empty:
        return None

    account_nodes = sorted(expense_rows["source"].unique().tolist())
    expense_categories = sorted(expense_rows["category"].unique().tolist())

    all_labels = account_nodes + expense_categories

    def idx(label):
        return all_labels.index(label)

    node_colors = (
        ["#c4a882"] * len(account_nodes)
        + ["#c0504a"] * len(expense_categories)
    )

    sources, targets, values, hover_labels = [], [], [], []

    for account in account_nodes:
        acc_expense = expense_rows[expense_rows["source"] == account]
        for cat in expense_categories:
            total = acc_expense[acc_expense["category"] == cat]["amount"].abs().sum()
            if total > 0:
                sources.append(idx(account))
                targets.append(idx(cat))
                values.append(total)
                hover_labels.append(f"{account} → {cat}  {format_idr(total)}")

    if not values:
        return None

    category_colors = {
        cat: f"rgba(184, 66, 51, {0.15 + 0.05 * i})"
        for i, cat in enumerate(expense_categories)
    }
    link_colors = [
        category_colors.get(all_labels[t], "rgba(184, 66, 51, 0.2)")
        for t in targets
    ]

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=24,
            thickness=24,
            line=dict(color="rgba(0,0,0,0)", width=0),
            label=all_labels,
            color=node_colors,
            hovertemplate="<b>%{label}</b><extra></extra>",
        ),
        textfont=dict(
            family="Inter, sans-serif",
            size=13,
            color="#2d3a2e",
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            label=hover_labels,
            color=link_colors,
            hovertemplate="<b>%{label}</b><extra></extra>",
        ),
    ))

    fig.update_layout(
        title=dict(
            text="Arus Pengeluaran",
            font=dict(size=15, color="#2d3a2e", family="Inter, sans-serif"),
            x=0,
        ),
        font=dict(family="Inter, sans-serif", size=13, color="#2d3a2e"),
        height=500,
        margin=dict(l=8, r=8, t=48, b=8),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
    )
    return fig


def build_sankey_v2(dataframe, payment_categories=None) -> go.Figure | None:
    """
    Bidirectional Sankey: Income Sources → Accounts → Expense Categories.

    Three-column layout:
      Left:   income category nodes (green)
      Center: account/source nodes (tan)
      Right:  expense category nodes (red)

    Excludes PAYMENT_CATEGORIES (card payments, refunds) from both sides
    since those are internal balance transfers, not real money flow.
    """
    if payment_categories is None:
        payment_categories = PAYMENT_CATEGORIES

    if dataframe.empty:
        return None

    # Separate income and expense, excluding internal transfers
    income_rows = dataframe[
        (dataframe["transaction_type"] == "income") &
        (~dataframe["category"].isin(payment_categories))
    ]
    expense_rows = dataframe[
        (dataframe["transaction_type"] == "expense") &
        (~dataframe["category"].isin(payment_categories))
    ]

    if income_rows.empty and expense_rows.empty:
        return None

    # Collect unique node labels for each column
    income_categories = sorted(income_rows["category"].unique().tolist()) if not income_rows.empty else []
    account_nodes = sorted(dataframe["source"].unique().tolist())
    expense_categories = sorted(expense_rows["category"].unique().tolist()) if not expense_rows.empty else []

    # Build ordered label list: [income_cats..., accounts..., expense_cats...]
    all_labels = income_categories + account_nodes + expense_categories

    def idx(label):
        return all_labels.index(label)

    # Node colors: green (income), tan (accounts), red (expenses)
    node_colors = (
        ["#4a7c59"] * len(income_categories)
        + ["#c4a882"] * len(account_nodes)
        + ["#c0504a"] * len(expense_categories)
    )

    sources, targets, values, hover_labels, link_colors = [], [], [], [], []

    # Income links: income_category → account/source
    for cat in income_categories:
        cat_rows = income_rows[income_rows["category"] == cat]
        for account in account_nodes:
            total = cat_rows[cat_rows["source"] == account]["amount"].abs().sum()
            if total > 0:
                sources.append(idx(cat))
                targets.append(idx(account))
                values.append(total)
                hover_labels.append(f"{cat} → {account}  {format_idr(total)}")
                link_colors.append("rgba(74, 124, 89, 0.25)")

    # Expense links: account/source → expense_category
    for account in account_nodes:
        acc_expense = expense_rows[expense_rows["source"] == account]
        for cat in expense_categories:
            total = acc_expense[acc_expense["category"] == cat]["amount"].abs().sum()
            if total > 0:
                sources.append(idx(account))
                targets.append(idx(cat))
                values.append(total)
                hover_labels.append(f"{account} → {cat}  {format_idr(total)}")
                link_colors.append("rgba(184, 66, 51, 0.25)")

    if not values:
        return None

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=24,
            thickness=24,
            line=dict(color="rgba(0,0,0,0)", width=0),
            label=all_labels,
            color=node_colors,
            hovertemplate="<b>%{label}</b><extra></extra>",
        ),
        textfont=dict(
            family="Inter, sans-serif",
            size=13,
            color="#2d3a2e",
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            label=hover_labels,
            color=link_colors,
            hovertemplate="<b>%{label}</b><extra></extra>",
        ),
    ))

    fig.update_layout(
        title=dict(
            text="Arus Keuangan",
            font=dict(size=15, color="#2d3a2e", family="Inter, sans-serif"),
            x=0,
        ),
        font=dict(family="Inter, sans-serif", size=13, color="#2d3a2e"),
        height=500,
        margin=dict(l=8, r=8, t=48, b=8),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
    )
    return fig


def render_sankey_clean(fig: go.Figure, height: int = 540) -> None:
    """
    Render Sankey without Plotly's SVG white-stroke halo on labels.

    Plotly bakes stroke: rgb(255,255,255); stroke-width: 2px; paint-order: stroke fill
    into every SVG text node. On our light background this creates an ugly emboss
    artefact. We strip those properties from the generated HTML.
    """
    html = fig.to_html(full_html=False, include_plotlyjs="cdn")
    html = re.sub(r"\bstroke:\s*rgb\(255,\s*255,\s*255\)\s*;?", "", html)
    html = re.sub(r"\bstroke-width:\s*[\d.]+px\s*;?", "", html)
    html = re.sub(r"\bpaint-order:\s*stroke\s+fill\s*;?", "", html)
    components.html(html, height=height, scrolling=False)
