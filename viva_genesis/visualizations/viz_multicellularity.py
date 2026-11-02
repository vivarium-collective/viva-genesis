"""Multicellularity (VG-MULTI-001) — one insight figure per run study (S01–S03).

The first cycle ran the A/B/C discrimination on the reduced ``cell_collective`` mean-field model
but shipped no figures. These render each study's recorded finding from a fresh composite run:

- ``FormationPersistenceViz`` (S01): group fraction building to a persistent life cycle with
  clonal adhesion, vs a no-adhesion null that never forms groups.
- ``EcologicalSelectionViz`` (S02): the fitness decomposition behind the advantage — ecological
  selection lifts group fitness above unicell fitness; adhesion alone does not.
- ``TransportSizeOptimumViz`` (S03): the advantage vs mean group size is non-monotonic —
  oxygen/transport bounds it to an intermediate size optimum below the interior-starvation limit.

All curves/points come from fresh ``cell_collective`` runs (no fabricated data); the swept
parameters and arms match the values recorded in each study's finding.
"""
from __future__ import annotations

import json

from process_bigraph import Composite
from process_bigraph.visualization import Visualization

from . import viz_style as S
from ..core import build_core

_PLOTLY = "https://cdn.plot.ly/plotly-2.27.0.min.js"


def _rows(core, keys, *, n_steps, **kw):
    from ..composites.cell_collective import cell_collective as G
    sim = Composite({"state": G(core=core, **kw)}, core=core)
    out = []
    for _ in range(int(n_steps)):
        sim.run(1)
        out.append({k: float(sim.state.get(k, 0.0)) for k in keys})
    return out


def _settled(rows, key, frac=0.25):
    m = max(1, int(len(rows) * frac))
    v = [r[key] for r in rows[-m:]]
    return sum(v) / len(v)


def _plot(div, data, layout, height=360):
    return (f'<div id="{div}" style="height:{height}px"></div>'
            f'<script src="{_PLOTLY}"></script>'
            f'<script>Plotly.newPlot("{div}",{json.dumps(data)},{json.dumps(layout)},'
            f'{{responsive:true,displayModeBar:false}});</script>')


class FormationPersistenceViz(Visualization):
    """S01: clonal incomplete separation with reversible adhesion builds a persistent group
    life cycle (group fraction → ~0.67); a no-adhesion null never forms groups (→ ~0.01)."""
    config_schema = {"title": {"_type": "string", "_default": "Clonal adhesion builds a persistent group life cycle"},
                     "n_steps": {"_type": "integer", "_default": 200}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        core = build_core(); n = int(self.config["n_steps"])
        on = _rows(core, ("group_fraction",), n_steps=n,
                   adhesion=0.8, fragmentation=0.2, predation_size_reward=0.02, transport_penalty=0.02)
        null = _rows(core, ("group_fraction",), n_steps=n,
                     adhesion=0.02, fragmentation=0.8, predation_size_reward=0.8, transport_penalty=0.02)
        x = list(range(1, n + 1))
        data = [
            dict(type="scatter", x=x, y=[r["group_fraction"] for r in on], mode="lines",
                 name="clonal adhesion on", line=dict(color=S.TEAL, width=2.6),
                 fill="tozeroy", fillcolor="rgba(13,148,136,0.08)",
                 hovertemplate="tick %{x}<br>group fraction %{y:.3f}<extra></extra>"),
            dict(type="scatter", x=x, y=[r["group_fraction"] for r in null], mode="lines",
                 name="no-adhesion null", line=dict(color=S.SLATE, width=2.2, dash="dot"),
                 hovertemplate="tick %{x}<br>group fraction %{y:.3f}<extra></extra>"),
        ]
        layout = S.base_layout(
            height=360, margin=dict(l=62, r=20, t=20, b=64),
            xaxis=dict(title="time (ticks)", gridcolor=S.GRID, zeroline=False),
            yaxis=dict(title="fraction of population in persistent groups", range=[0, 1.02],
                       gridcolor=S.GRID, zeroline=False),
            shapes=[dict(type="line", x0=1, x1=n, y0=0.5, y1=0.5, xref="x", yref="y",
                         line=dict(color=S.AMBER, width=1.8, dash="dash"))],
            annotations=[dict(x=1, y=0.5, xref="x", yref="y", text="persistence gate 0.5",
                              showarrow=False, xanchor="left", yanchor="bottom",
                              font=dict(size=10, color=S.AMBER))])
        return {"html": S.frame(_plot("mc_s01", data, layout), title=self.config.get("title"),
                tier="first fidelity", view="Mechanism", tone="neutral", max_width=820,
                caption_text=("With reversible clonal adhesion the population settles into a persistent "
                              "group life cycle (group fraction ≈ 0.67, above the gate); with adhesion off and "
                              "fragmentation high no groups persist (≈ 0.01). This establishes <b>formation</b> "
                              "only — it says nothing yet about whether groups are fitter."))}


class EcologicalSelectionViz(Visualization):
    """S02: adhesion alone leaves group fitness ≈ unicell fitness (no advantage); adding
    size-dependent predation/settling lifts group fitness above unicell — the advantage is
    ecological, not a property of adhesion per se."""
    config_schema = {"title": {"_type": "string", "_default": "Ecological selection — not adhesion — makes groups fitter"},
                     "n_steps": {"_type": "integer", "_default": 160}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        core = build_core(); n = int(self.config["n_steps"])
        arms = [
            ("adhesion only (A)", dict(adhesion=0.8, fragmentation=0.2, predation_size_reward=0.02, transport_penalty=0.02)),
            ("+ size-dependent\npredation/settling (B)", dict(adhesion=0.8, fragmentation=0.2, predation_size_reward=0.8, transport_penalty=0.02)),
        ]
        labels, uni, grp, adv = [], [], [], []
        for lbl, kw in arms:
            r = _rows(core, ("unicell_fitness", "group_fitness", "group_fitness_advantage"), n_steps=n, **kw)
            labels.append(lbl)
            uni.append(_settled(r, "unicell_fitness"))
            grp.append(_settled(r, "group_fitness"))
            adv.append(_settled(r, "group_fitness_advantage"))
        data = [
            dict(type="bar", x=labels, y=uni, name="unicell fitness", marker_color=S.SLATE,
                 hovertemplate="%{x}<br>unicell %{y:.3f}<extra></extra>"),
            dict(type="bar", x=labels, y=grp, name="group fitness", marker_color=S.TEAL,
                 hovertemplate="%{x}<br>group %{y:.3f}<extra></extra>"),
        ]
        anns = []
        for i, (lbl, a) in enumerate(zip(labels, adv)):
            anns.append(dict(x=lbl, y=max(uni[i], grp[i]) + 0.03, text=f"advantage {a:+.2f}",
                             showarrow=False, font=dict(size=11, color=(S.TEAL if a > 0.01 else S.SLATE)),
                             xanchor="center"))
        layout = S.base_layout(
            height=360, margin=dict(l=62, r=20, t=20, b=70), barmode="group", bargap=0.35,
            xaxis=dict(title="", tickfont=dict(size=11)),
            yaxis=dict(title="settled fitness", rangemode="tozero", gridcolor=S.GRID, zeroline=False),
            annotations=anns, legend=dict(orientation="h", y=1.14, x=0.5, xanchor="center"))
        return {"html": S.frame(_plot("mc_s02", data, layout), title=self.config.get("title"),
                tier="first fidelity", view="Mechanism", tone="neutral", max_width=820,
                caption_text=("Unicell fitness is identical in both arms. Adhesion alone leaves group fitness "
                              "level with it (advantage ≈ 0); only size-dependent predation/settling lifts group "
                              "fitness above unicell (advantage ≈ +0.15). The group-level advantage is <b>conferred "
                              "by ecological selection, not by adhesion itself</b> (supports H1 for the advantage)."))}


class TransportSizeOptimumViz(Visualization):
    """S03: with oxygen-limited growth the group fitness advantage is non-monotonic in size —
    positive for small/intermediate groups, negative once groups exceed the interior-starvation
    limit, so transport bounds the advantage to an optimal intermediate size."""
    config_schema = {"title": {"_type": "string", "_default": "Transport bounds the advantage to an intermediate size optimum"},
                     "n_steps": {"_type": "integer", "_default": 160}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        core = build_core(); n = int(self.config["n_steps"])
        # scan mean group size via adhesion, with oxygen-limited growth ON (C regime)
        adhes = [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 0.9]
        sizes, advs = [], []
        for a in adhes:
            r = _rows(core, ("mean_group_size", "group_fitness_advantage"), n_steps=n,
                      adhesion=a, fragmentation=0.3, predation_size_reward=0.8, transport_penalty=0.8)
            sizes.append(_settled(r, "mean_group_size"))
            advs.append(_settled(r, "group_fitness_advantage"))
        # colour points by sign
        colors = [S.TEAL if v > 0 else S.RUST for v in advs]
        o2_limit = 6.0
        peak_i = max(range(len(advs)), key=lambda i: advs[i])
        data = [
            dict(type="scatter", x=sizes, y=advs, mode="lines+markers",
                 line=dict(color=S.INK_SOFT, width=2), marker=dict(size=10, color=colors,
                 line=dict(color="#fff", width=1)), name="advantage",
                 hovertemplate="size %{x:.2f}<br>advantage %{y:+.3f}<extra></extra>"),
        ]
        shapes = [
            dict(type="line", x0=min(sizes), x1=max(sizes), y0=0, y1=0, xref="x", yref="y",
                 line=dict(color=S.SLATE, width=1.4)),
            dict(type="line", x0=o2_limit, x1=o2_limit, y0=min(advs) - 0.03, y1=max(advs) + 0.03,
                 xref="x", yref="y", line=dict(color=S.AMBER, width=1.8, dash="dash")),
        ]
        anns = [
            dict(x=o2_limit, y=max(advs) + 0.02, text="oxygen size limit", showarrow=False,
                 xanchor="left", yanchor="bottom", font=dict(size=10, color=S.AMBER)),
            dict(x=sizes[peak_i], y=advs[peak_i], text=f"optimum<br>size {sizes[peak_i]:.1f}, adv {advs[peak_i]:+.2f}",
                 showarrow=True, arrowhead=0, ax=38, ay=-30, font=dict(size=10, color=S.TEAL)),
        ]
        layout = S.base_layout(
            height=360, margin=dict(l=62, r=20, t=20, b=64), showlegend=False,
            xaxis=dict(title="settled mean group size (cells)", gridcolor=S.GRID, zeroline=False),
            yaxis=dict(title="group fitness advantage", gridcolor=S.GRID, zeroline=False),
            shapes=shapes, annotations=anns)
        return {"html": S.frame(_plot("mc_s03", data, layout), title=self.config.get("title"),
                tier="first fidelity", view="Mechanism", tone="neutral", max_width=820,
                caption_text=("Scanning group size (via adhesion) under oxygen-limited growth, the advantage is "
                              "<b>non-monotonic</b>: positive for small/intermediate groups (peak ≈ +0.12 at size "
                              "≈ 3.7), then negative once groups outgrow the interior-starvation limit (≈ -0.21 at "
                              "size ≈ 17). Transport bounds multicellularity to an intermediate size (supports C3)."))}
