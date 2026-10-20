#!/usr/bin/env python3
"""Render the committed interactive viz for og-evolvable-lineages from the artifact:
the selection response (composition shift) vs the two matched nulls, and the
open-ended-vs-bounded signal (heritable-variance ratio vs the =1 open-ended line,
plus the changed-environment re-tracking). Reproducible: reads only the JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ART = STUDY_DIR / "artifacts" / "og-evolvable-lineages" / "evolvable_lineages.json"
OUT = STUDY_DIR / "viz" / "og-evolvable-lineages" / "evolvable_lineages.html"

C_FULL = "#4C78A8"
C_NULL = "#BAB0AC"
C_BOUND = "#E45756"
C_OPEN = "#54A24B"


def main() -> int:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    a = json.loads(ART.read_text())
    se = a["static_ensemble"]
    ce = a["changed_environment"]
    ob = a["open_ended_vs_bounded"]

    labels = ["full<br>(inherit + select)", "no-inheritance<br>null", "shared-feed<br>null"]
    shifts = [se["full"]["shift_mean"], se["no_inheritance_null"]["shift_mean"], se["shared_feed_null"]["shift_mean"]]
    errs = [se["full"]["shift_std"], se["no_inheritance_null"]["shift_std"], se["shared_feed_null"]["shift_std"]]
    colors = [C_FULL, C_NULL, C_NULL]

    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.55, 0.45], horizontal_spacing=0.16,
        subplot_titles=("Selection response vs two matched nulls",
                        "Open-ended vs bounded (heritable-variance ratio)"),
        specs=[[{"type": "bar"}, {"type": "bar"}]],
    )

    fig.add_trace(go.Bar(
        x=labels, y=shifts, marker_color=colors,
        error_y=dict(type="data", array=errs, visible=True),
        hovertemplate="%{x}<br>composition shift=%{y:.3f}<extra></extra>", showlegend=False,
    ), row=1, col=1)

    ratio = ob["heritable_variance_ratio_full"]
    fig.add_trace(go.Bar(
        x=["heritable variance<br>ratio (final/initial)"], y=[ratio],
        marker_color=C_BOUND if ratio < 1 else C_OPEN,
        hovertemplate="variance ratio=%{y:.2f}<extra></extra>", showlegend=False,
    ), row=1, col=2)
    fig.add_hline(y=1.0, line_dash="dash", line_color=C_OPEN, line_width=2,
                  annotation_text="= 1: open-ended (variance sustained)", annotation_position="top left",
                  row=1, col=2)

    fig.update_yaxes(title_text="mean composition shift (over generations)", row=1, col=1)
    fig.update_yaxes(title_text="variance ratio (final / initial)", row=1, col=2)

    retrack = ce["full_retrack"]
    fig.update_layout(
        template="plotly_white",
        title=dict(text="Evolvability given an individual: real heritable selection above both nulls, "
                        f"adapts to change (re-track {retrack:+.2f}), but bounded (variance ratio {ratio:.2f} < 1) — qualified",
                   x=0.5, xanchor="center", font=dict(size=13)),
        font=dict(size=12), margin=dict(l=70, r=40, t=90, b=70),
        height=520, width=1040, paper_bgcolor="white", plot_bgcolor="white",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUT), include_plotlyjs="cdn", full_html=True)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
