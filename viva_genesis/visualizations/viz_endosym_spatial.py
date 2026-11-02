"""Eukaryogenesis spatial views — show the *spatiality* of the spatial bridge models.

Two of the endosymbiosis composites carry genuine spatial state, and these figures render
that state directly rather than reducing it to a scalar:

- ``SpatialExchangeFieldViz`` (study-spatial-exchange-proximity, M6): the 1-D metabolite field
  emitted by ``proto_endosymbiosis_spatial`` — a producer at cell 0 and a screened-diffusion
  profile decaying outward. Rendered as an animated profile over Monte-Carlo time (the "video")
  plus a space x time kymograph (the "snapshots"), with the consumer's distance marked so the
  reader sees *why* contact beats distance.
- ``CommunityPlacementViz`` (s2-ecology-to-proximity): the actual agent layout along the pore
  from ``metabolite_exchange_community`` — fixers and reducers interleaved (mixed) vs clustered
  (segregated) — so the proximity advantage is visible as geometry, not just a flux number.

All data is pulled from fresh composite runs (no fabricated fields).
"""
from __future__ import annotations

import json

from process_bigraph import Composite
from process_bigraph.visualization import Visualization

from . import viz_style as S
from ..core import build_core

_PLOTLY = "https://cdn.plot.ly/plotly-2.27.0.min.js"


# --------------------------------------------------------------------------- #
# M6 — spatial metabolite field (animated profile + kymograph)
# --------------------------------------------------------------------------- #
def _field_over_time(core, *, n_steps, n_cells, **kw):
    """Collect the full 1-D ``conc`` field every tick → (times, [field_t])."""
    from ..composites.proto_endosymbiosis_spatial import proto_endosymbiosis_spatial as G
    sim = Composite({"state": G(core=core, n_cells=n_cells, **kw)}, core=core)
    frames, times = [], []
    for t in range(1, int(n_steps) + 1):
        sim.run(1)
        conc = sim.state.get("conc") or {}
        frames.append([float(conc.get(str(i), 0.0)) for i in range(int(n_cells))])
        times.append(t)
    return times, frames


class SpatialExchangeFieldViz(Visualization):
    """M6: render the diffusing metabolite field in space + time. The producer sits at cell 0;
    the field decays with the screening length sqrt(D/k); the consumer at distance d reads off
    whatever reaches it. Animation = the field building up; kymograph = the whole evolution."""
    config_schema = {
        "title": {"_type": "string", "_default": "Spatial exchange — the metabolite field a consumer sees at distance"},
        "n_steps": {"_type": "integer", "_default": 60},
        "n_cells": {"_type": "integer", "_default": 16},
        "consumer_distance": {"_type": "integer", "_default": 6},
        "diffusion": {"_type": "float", "_default": 0.4},
        "decay": {"_type": "float", "_default": 0.08},
    }

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        core = build_core()
        n = int(self.config["n_steps"]); nc = int(self.config["n_cells"])
        d = int(self.config["consumer_distance"])
        D = float(self.config["diffusion"]); k = float(self.config["decay"])
        times, frames = _field_over_time(core, n_steps=n, n_cells=nc,
                                         diffusion=D, decay=k, consumer_distance=d)
        xs = list(range(nc))
        ymax = max(max(f) for f in frames) * 1.08 or 1.0
        import math
        screen = math.sqrt(D / k) if k > 0 else float("inf")

        # subsample frames to keep the file light (~24 frames)
        step = max(1, len(frames) // 24)
        fidx = list(range(0, len(frames), step)) + [len(frames) - 1]
        fidx = sorted(set(fidx))

        # ---- panel A: animated profile (the "video") ----
        base = frames[fidx[0]]
        prod_marker = dict(type="scatter", x=[0], y=[base[0]], mode="markers+text",
                           marker=dict(size=13, color=S.AMBER, symbol="circle",
                                       line=dict(color="#fff", width=1.5)),
                           text=["producer"], textposition="top center",
                           textfont=dict(size=10, color=S.AMBER), hoverinfo="skip", name="producer")
        cons_marker = dict(type="scatter", x=[d], y=[base[d]], mode="markers+text",
                           marker=dict(size=13, color=S.TEAL, symbol="diamond",
                                       line=dict(color="#fff", width=1.5)),
                           text=[f"consumer (d={d})"], textposition="top center",
                           textfont=dict(size=10, color=S.TEAL), hoverinfo="skip", name="consumer")
        bars = dict(type="bar", x=xs, y=base, marker=dict(color=S.MUTED),
                    hovertemplate="cell %{x}<br>conc %{y:.3f}<extra></extra>", name="field")
        data_a = [bars, prod_marker, cons_marker]
        plotly_frames = []
        for i in fidx:
            f = frames[i]
            plotly_frames.append(dict(
                name=str(times[i]),
                data=[dict(type="bar", x=xs, y=f),
                      dict(type="scatter", x=[0], y=[f[0]]),
                      dict(type="scatter", x=[d], y=[f[d]])]))
        steps = [dict(method="animate", label=str(times[i]),
                      args=[[str(times[i])], dict(mode="immediate",
                            frame=dict(duration=0, redraw=True), transition=dict(duration=0))])
                 for i in fidx]
        layout_a = S.base_layout(
            height=300, margin=dict(l=60, r=20, t=18, b=42),
            bargap=0.12, showlegend=False,
            xaxis=dict(title="distance from producer (cells)", showgrid=False,
                       zeroline=False, tickmode="linear", dtick=2),
            yaxis=dict(title="metabolite conc", range=[0, ymax], gridcolor=S.GRID, zeroline=False),
            updatemenus=[dict(type="buttons", showactive=False, x=0.02, y=1.22, xanchor="left",
                              buttons=[dict(label="▶ play", method="animate",
                                            args=[None, dict(fromcurrent=True, frame=dict(duration=140, redraw=True),
                                                             transition=dict(duration=0))]),
                                       dict(label="❚❚ pause", method="animate",
                                            args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])])],
            sliders=[dict(active=0, x=0.16, len=0.82, y=1.16, xanchor="left",
                          currentvalue=dict(prefix="sweep ", font=dict(size=11, color=S.INK_SOFT)),
                          pad=dict(t=0, b=0), steps=steps)])
        fig_a = (f'<div id="spf_a" style="height:300px"></div>'
                 f'<script src="{_PLOTLY}"></script>'
                 f'<script>Plotly.newPlot("spf_a",{json.dumps(data_a)},{json.dumps(layout_a)},'
                 f'{{responsive:true,displayModeBar:false}}).then(function(gd){{'
                 f'Plotly.addFrames("spf_a",{json.dumps(plotly_frames)});}});</script>')

        # ---- panel B: kymograph (the "snapshots" — all of space x time at once) ----
        z = frames  # rows = time, cols = space
        data_b = [dict(type="heatmap", z=z, x=xs, y=times, colorscale="Teal",
                       colorbar=dict(title=dict(text="conc", side="right"), thickness=12, len=0.9),
                       hovertemplate="cell %{x}<br>sweep %{y}<br>conc %{z:.3f}<extra></extra>")]
        layout_b = S.base_layout(
            height=280, margin=dict(l=60, r=20, t=18, b=42), showlegend=False,
            xaxis=dict(title="distance from producer (cells)", tickmode="linear", dtick=2,
                       showgrid=False, zeroline=False),
            yaxis=dict(title="Monte-Carlo sweep", showgrid=False, zeroline=False),
            shapes=[dict(type="line", x0=d, x1=d, y0=times[0], y1=times[-1], yref="y",
                         line=dict(color=S.TEAL, width=2, dash="dash"))],
            annotations=[dict(x=d, y=times[-1], text=f"consumer d={d}", showarrow=False,
                              yanchor="bottom", font=dict(size=10, color=S.TEAL))])
        fig_b = (f'<div id="spf_b" style="height:280px"></div>'
                 f'<script>Plotly.newPlot("spf_b",{json.dumps(data_b)},{json.dumps(layout_b)},'
                 f'{{responsive:true,displayModeBar:false}});</script>')

        reaches = frames[-1][d]
        inner = (f'<div style="font:600 11px {S.FONT_STACK};color:{S.INK_SOFT};margin:2px 0 4px 2px">'
                 f'▶ FIELD BUILDING UP (press play)</div>{fig_a}'
                 f'<div style="font:600 11px {S.FONT_STACK};color:{S.INK_SOFT};margin:14px 0 4px 2px">'
                 f'SPACE × TIME KYMOGRAPH</div>{fig_b}')
        return {"html": S.frame(inner, title=self.config.get("title"), tier="reduced coupled model",
                view="Spatial", tone="neutral", max_width=820,
                caption_text=(f"The producer (cell 0) sources a metabolite that diffuses outward and is "
                              f"screened over a length &radic;(D/k)&nbsp;&asymp;&nbsp;{screen:.1f} cells, so the "
                              f"concentration decays steeply with distance. A consumer at d={d} reads only "
                              f"~{reaches:.2f} of the source level — the realised exchange is set by <b>how close "
                              f"the partner sits</b>, which is the proximity advantage M1 assumes."))}


# --------------------------------------------------------------------------- #
# S2 — community agent placement (mixed vs segregated along the pore)
# --------------------------------------------------------------------------- #
def _placement(core, placement, **kw):
    from ..composites.metabolite_exchange_community import metabolite_exchange_community as G
    sim = Composite({"state": G(core=core, coupling="shared", placement=placement, **kw)}, core=core)
    lin = sim.state.get("lineages") or {}
    rows = []
    for v in lin.values():
        pos = v.get("position") or (0.0, 0.0)
        rows.append((str(v.get("lineage_id")), float(pos[0])))
    return sorted(rows, key=lambda r: r[1])


def _nearest_complement(rows):
    """Mean distance from each agent to the nearest agent of the *other* lineage — the
    length cross-feeding metabolites must travel. Smaller = tighter metabolic coupling."""
    ds = []
    for name, x in rows:
        others = [ox for on, ox in rows if on != name]
        if others:
            ds.append(min(abs(x - ox) for ox in others))
    return sum(ds) / len(ds) if ds else float("nan")


class CommunityPlacementViz(Visualization):
    """S2: show the pore layout that makes proximity matter. In the mixed arm fixers and reducers
    interleave (short cross-feeding distance); segregated clusters them apart (long distance).
    The exchange flux advantage of the mixed arm is a direct consequence of this geometry."""
    config_schema = {
        "title": {"_type": "string", "_default": "Proximity selects for contact — the pore layout behind the flux"},
        "lineages": {"_type": "string", "_default": "fixer:4,reducer:4"},
    }

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        core = build_core()
        kw = dict(lineages=self.config["lineages"], model_proto_ecology="reaction_universe",
                  p_diacid=1.0e-8, p_monoacid=1.0e-7, k_wash=0.01, k_diffusion=0.001)
        mixed = _placement(core, "mixed", **kw)
        seg = _placement(core, "segregated", **kw)
        colors = {"fixer": S.TEAL, "reducer": S.AMBER}

        def _row_trace(rows, y, show_names):
            fx = [x for n, x in rows if n == "fixer"]
            rx = [x for n, x in rows if n == "reducer"]
            return [
                dict(type="scatter", x=fx, y=[y] * len(fx), mode="markers",
                     marker=dict(size=20, color=colors["fixer"], line=dict(color="#fff", width=1.5)),
                     name="fixer", legendgroup="fixer", showlegend=show_names,
                     hovertemplate="fixer<br>pore position %{x:.2f}<extra></extra>"),
                dict(type="scatter", x=rx, y=[y] * len(rx), mode="markers",
                     marker=dict(size=20, color=colors["reducer"], symbol="square",
                                 line=dict(color="#fff", width=1.5)),
                     name="reducer", legendgroup="reducer", showlegend=show_names,
                     hovertemplate="reducer<br>pore position %{x:.2f}<extra></extra>"),
            ]

        dm, dsg = _nearest_complement(mixed), _nearest_complement(seg)
        data = _row_trace(mixed, 1.0, True) + _row_trace(seg, 0.0, False)
        layout = S.base_layout(
            height=300, margin=dict(l=120, r=24, t=20, b=52),
            xaxis=dict(title="position along pore  (0 = inlet → 1 = trap end)", range=[-0.03, 1.03],
                       showgrid=True, gridcolor=S.GRID, zeroline=False),
            yaxis=dict(range=[-0.6, 1.6], tickmode="array", tickvals=[0, 1],
                       ticktext=[f"segregated<br><span style='font-size:10px;color:{S.SLATE}'>"
                                 f"mean gap {dsg:.2f}</span>",
                                 f"mixed<br><span style='font-size:10px;color:{S.SLATE}'>"
                                 f"mean gap {dm:.2f}</span>"],
                       showgrid=False, zeroline=False),
            legend=dict(orientation="h", y=1.18, x=0.5, xanchor="center"))
        inner = (f'<div id="plc" style="height:300px"></div>'
                 f'<script src="{_PLOTLY}"></script>'
                 f'<script>Plotly.newPlot("plc",{json.dumps(data)},{json.dumps(layout)},'
                 f'{{responsive:true,displayModeBar:false}});</script>')
        ratio = dsg / dm if dm > 0 else float("nan")
        return {"html": S.frame(inner, title=self.config.get("title"), tier="first fidelity",
                view="Spatial", tone="neutral", max_width=820,
                caption_text=(f"Same eight agents, same chemistry — only the spatial arrangement differs. "
                              f"Mixed interleaves fixers (teal) and reducers (amber) so every agent sits "
                              f"beside a complementary partner (mean gap {dm:.2f}); segregated clusters each "
                              f"type (mean gap {dsg:.2f}, ~{ratio:.1f}&times; farther). At low diffusion the "
                              f"cross-feeding flux follows that gap — <b>proximity is selected because the "
                              f"metabolite cannot travel far before it washes out</b>."))}
