#!/usr/bin/env python3
"""Render the committed interactive viz for og-precursor-pool from the
precursor-yield-vector artifact. Two panels: the precursor yield vectors (log
molar, against the consumable-concentration threshold) and the DIC-window sweep
(functional pool + aggregate C2:C1 ceiling). Reproducible: reads only the JSON
artifact written by sims/run.py.
"""
from __future__ import annotations

import json
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ART = STUDY_DIR / "artifacts" / "og-precursor-pool" / "precursor_yield_vectors.json"
OUT = STUDY_DIR / "viz" / "og-precursor-pool" / "precursor_yield_vectors.html"

# Accessible, CVD-safe-ish fixed hues (identity by entity, not rank).
C_C1 = "#4C78A8"      # C1 feedstock (blue)
C_FUNC = "#E45756"    # functional C2+ precursors (red)
C_THRESH = "#54A24B"  # consumable threshold (green)
C_RATIO = "#B279A2"   # C2:C1 ratio (purple)


def main() -> int:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    art = json.loads(ART.read_text())
    yv = art["yield_vectors"]
    thresh = art["consumable_threshold_M"]

    # Panel 1 data: species with a finite concentration, sorted ascending.
    rows = [(n, v["concentration_M"], v["n_carbons"], v["functional"],
             v["co2_fixed_fraction"])
            for n, v in yv.items() if v["concentration_M"] > 1e-30]
    rows.sort(key=lambda r: r[1])
    names = [r[0] for r in rows]
    conc = [r[1] for r in rows]
    colors = [C_FUNC if r[3] else C_C1 for r in rows]
    htext = [f"{n}<br>C{nc} {'functional' if f else 'feedstock'}"
             f"<br>{c:.3e} M<br>de-novo CO2-fixed: {cf*100:.0f}%"
             for n, c, nc, f, cf in rows]

    sweep = art["dic_window_sweep"]
    co2 = [s["feed_CO2_mM"] for s in sweep]
    func = [s["functional_pool_carbon_M"] for s in sweep]
    ratio = [s["c2_c1_ratio"] for s in sweep]

    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.56, 0.44],
        horizontal_spacing=0.14,
        subplot_titles=(
            "Precursor yield vectors @ 2 mM DIC (de-novo CO&#8322;-fixed)",
            "DIC-window sweep: the thermodynamic C2+ ceiling",
        ),
        specs=[[{"type": "bar"}, {"secondary_y": True}]],
    )

    fig.add_trace(go.Bar(
        y=names, x=conc, orientation="h", marker_color=colors,
        hovertext=htext, hoverinfo="text", name="precursor",
        showlegend=False,
    ), row=1, col=1)
    # consumable threshold line (log x)
    fig.add_vline(x=thresh, line_dash="dash", line_color=C_THRESH, line_width=2,
                  annotation_text="consumable ~1 &#181;M", annotation_position="top",
                  row=1, col=1)

    fig.add_trace(go.Scatter(
        x=co2, y=func, mode="lines+markers", line=dict(color=C_FUNC, width=2),
        marker=dict(size=9), name="functional pool (M C)",
        hovertemplate="CO&#8322;=%{x:.0f} mM<br>pool=%{y:.2e} M C<extra></extra>",
    ), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(
        x=co2, y=ratio, mode="lines+markers", line=dict(color=C_RATIO, width=2, dash="dot"),
        marker=dict(size=9, symbol="diamond"), name="aggregate C2:C1",
        hovertemplate="CO&#8322;=%{x:.0f} mM<br>C2:C1=%{y:.2e}<extra></extra>",
    ), row=1, col=2, secondary_y=True)
    # Preiner batch reference for C2:C1
    fig.add_hline(y=5.0e-4, line_dash="dash", line_color="#9D7660", line_width=1.5,
                  annotation_text="Preiner batch ~5e-4", annotation_position="top left",
                  row=1, col=2, secondary_y=True)

    fig.update_xaxes(type="log", title_text="concentration (M)", row=1, col=1)
    fig.update_xaxes(title_text="inorganic-carbon feed (mM, DIC window)", row=1, col=2)
    fig.update_yaxes(title_text="functional pool carbon (M)", type="log",
                     row=1, col=2, secondary_y=False)
    fig.update_yaxes(title_text="aggregate C2:C1 ratio", type="log",
                     row=1, col=2, secondary_y=True, showgrid=False)

    fig.update_layout(
        template="plotly_white",
        title=dict(text="A de-novo precursor pool, thermodynamically bounded "
                        "sub-&#181;M within the defensible DIC window (qualified)",
                   x=0.5, xanchor="center", font=dict(size=15)),
        font=dict(size=12),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"),
        margin=dict(l=90, r=60, t=90, b=90),
        height=560, width=1040,
        paper_bgcolor="white", plot_bgcolor="white",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(OUT), include_plotlyjs="cdn", full_html=True)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
