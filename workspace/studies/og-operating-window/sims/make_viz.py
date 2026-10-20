#!/usr/bin/env python3
"""Render the committed interactive viz for og-operating-window from the
operating-window artifact: the enriched-pool phase map over (Soret x thermal
gradient) at the favorable DIC, with the consumable (uM) contour and the
defensible-Soret boundary, plus the Morris parameter-sensitivity ranking.
Reproducible: reads only the JSON artifact written by sims/run.py.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ART = STUDY_DIR / "artifacts" / "og-operating-window" / "operating_window.json"
OUT = STUDY_DIR / "viz" / "og-operating-window" / "operating_window.html"


def main() -> int:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    art = json.loads(ART.read_text())
    soret = art["axes"]["soret_coeff"]
    dT = art["axes"]["delta_T"]
    co2 = art["axes"]["feed_CO2"]
    surf = art["enriched_surface_M"]           # [soret][dT][co2]
    thresh = art["consumable_threshold_M"]
    defensible_max = art["defensible_soret_max"]
    jco2 = len(co2) - 1                         # favorable (highest) DIC slice
    # z[dT][soret] = log10(enriched) at the favorable DIC
    z = [[math.log10(max(surf[i][j][jco2], 1e-30)) for i in range(len(soret))]
         for j in range(len(dT))]

    mor = art["sensitivity_morris"]
    ranking = mor["ranking"]
    mu_star = [mor["mu_star"][n] for n in ranking]

    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.6, 0.4], horizontal_spacing=0.16,
        subplot_titles=(f"Enriched+retained pool (log10 M) @ DIC {co2[jco2]*1e3:.0f} mM",
                        "Morris parameter sensitivity (mu*)"),
        specs=[[{"type": "heatmap"}, {"type": "bar"}]],
    )

    fig.add_trace(go.Heatmap(
        z=z, x=soret, y=dT, colorscale="Viridis",
        colorbar=dict(title="log10 M", x=0.52),
        hovertemplate="S_T=%{x:.0e}/K<br>dT=%{y:.0f} K<br>pool=10^%{z:.2f} M<extra></extra>",
    ), row=1, col=1)
    # consumable (uM) contour
    fig.add_trace(go.Contour(
        z=z, x=soret, y=dT, showscale=False, contours=dict(
            start=math.log10(thresh), end=math.log10(thresh), size=1,
            coloring="lines"), line=dict(color="#E45756", width=3),
        hoverinfo="skip", name="uM threshold",
    ), row=1, col=1)
    # defensible small-molecule Soret boundary
    fig.add_vline(x=defensible_max, line_dash="dash", line_color="#54A24B", line_width=2,
                  annotation_text="defensible S_T max", annotation_position="top",
                  row=1, col=1)

    fig.add_trace(go.Bar(
        x=mu_star, y=ranking, orientation="h", marker_color="#4C78A8",
        hovertemplate="%{y}: mu*=%{x:.2f}<extra></extra>", showlegend=False,
    ), row=1, col=2)

    fig.update_xaxes(type="log", title_text="Soret coefficient S_T (1/K)", row=1, col=1)
    fig.update_yaxes(title_text="thermal gradient dT (K)", row=1, col=1)
    fig.update_xaxes(title_text="Morris mu* (elementary effect)", row=1, col=2)
    fig.update_yaxes(autorange="reversed", row=1, col=2)

    ov = art["overlap_volume_defensible"]
    cross = art["soret_crossover_per_K"]
    fig.update_layout(
        template="plotly_white",
        title=dict(text=f"Narrow rescue window: uM reached in ~{ov*100:.0f}% of the "
                        f"defensible grid, only at S_T&#8805;{cross:.0e}/K + high dT + high DIC (qualified)",
                   x=0.5, xanchor="center", font=dict(size=14)),
        font=dict(size=12), margin=dict(l=80, r=40, t=90, b=70),
        height=520, width=1040, paper_bgcolor="white", plot_bgcolor="white",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUT), include_plotlyjs="cdn", full_html=True)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
