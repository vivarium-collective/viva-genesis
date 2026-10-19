#!/usr/bin/env python3
"""Render the committed interactive viz for og-self-maintaining-individual from the
closure artifact: the cascading A->B->C concentration gap (acetate vs the
CAC-clearance threshold) and the aggregation-competence of every condition against
the competent=1 line (none clear it endogenously). Reproducible: reads only the JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ART = STUDY_DIR / "artifacts" / "og-self-maintaining-individual" / "self_maintaining.json"
OUT = STUDY_DIR / "viz" / "og-self-maintaining-individual" / "self_maintaining.html"

C_BAR = "#4C78A8"
C_FAIL = "#E45756"
C_THRESH = "#54A24B"


def main() -> int:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    a = json.loads(ART.read_text())
    casc = a["cascade"]
    ace_need = a["acetate_for_cac_clearance_M"]

    # Panel 1: cascade gap — acetate the membrane sees vs the CAC-clearance threshold.
    stages = ["A pool<br>(canonical)", "B corner<br>(enriched)", "needed for<br>membrane (CAC)"]
    vals = [casc["A_acetate_canonical_M"], casc["B_corner_acetate_fed_M"], ace_need]
    colors = [C_FAIL, C_FAIL, C_THRESH]

    # Panel 2: aggregation competence across conditions (log), vs competent = 1.
    conds = a["conditions"]
    order = ["canonical:full_no_gain", "b_corner:full_no_gain", "b_corner:full_built_in_gain",
             "b_corner:ablate_chem_to_mem", "b_corner:ablate_mem_to_chem", "b_corner:ablate_external_feed"]
    labels = ["canonical (full)", "B-corner (full)", "B-corner (built-in gain)",
              "B-corner ablate chem→mem", "B-corner ablate mem→chem", "B-corner ablate feed"]
    comp = [max(conds[k]["aggregation_competent"], 1e-12) for k in order]

    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.42, 0.58], horizontal_spacing=0.18,
        subplot_titles=("Cascading A→B→C concentration gap",
                        "Aggregation competence by condition (none clear CAC)"),
        specs=[[{"type": "bar"}, {"type": "bar"}]],
    )

    fig.add_trace(go.Bar(
        x=stages, y=vals, marker_color=colors,
        hovertemplate="%{x}<br>%{y:.2e} M<extra></extra>", showlegend=False,
    ), row=1, col=1)
    fig.add_annotation(x=1, y=casc["B_corner_acetate_fed_M"], yref="y",
                       text=f"~{casc['orders_short_b_corner']:.1f} orders<br>short at best corner",
                       showarrow=True, arrowhead=2, ay=-40, row=1, col=1)

    fig.add_trace(go.Bar(
        x=comp, y=labels, orientation="h", marker_color=C_BAR,
        hovertemplate="%{y}<br>aggregation_competent=%{x:.2e}<extra></extra>", showlegend=False,
    ), row=1, col=2)
    fig.add_vline(x=1.0, line_dash="dash", line_color=C_THRESH, line_width=2,
                  annotation_text="competent = 1 (membrane forms)", annotation_position="top",
                  row=1, col=2)

    fig.update_yaxes(type="log", title_text="acetate / threshold (M)", row=1, col=1)
    fig.update_xaxes(type="log", title_text="aggregation_competent (long-chain pool / CAC)", row=1, col=2)
    fig.update_yaxes(autorange="reversed", row=1, col=2)

    closed_c = a["closes_without_built_in_gain"]["canonical"]
    closed_b = a["closes_without_built_in_gain"]["b_corner"]
    fig.update_layout(
        template="plotly_white",
        title=dict(text="NEW C — reciprocal maintenance does NOT close endogenously "
                        f"(canonical={closed_c}, B-corner={closed_b}); the nM gap cascades ~4 orders (REFUTED, scoped)",
                   x=0.5, xanchor="center", font=dict(size=13.5)),
        font=dict(size=12), margin=dict(l=160, r=40, t=90, b=70),
        height=520, width=1060, paper_bgcolor="white", plot_bgcolor="white",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUT), include_plotlyjs="cdn", full_html=True)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
