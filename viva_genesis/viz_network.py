"""Phase-3 figures — the open chemical network (og-02-alt-reaction-universe).

Both render from the persisted artifacts written by
``sims/compute_motif_enrichment.py`` (the universe + 24 nulls + curated class
per arm, plus the ignition map, is ~10 min of libRoadRunner compute, so nothing
is recomputed at page load):

* :class:`ReactionUniverseEnrichment` — the Decision view: per arm, the
  matched-null distribution of persistent autocatalytic motifs with the
  universe and the curated class marked (and the empirical p), beside the
  (formaldehyde x washout) ignition map of the universe's motif count.
* :class:`ReactionUniverseSubnetwork` — the Mechanism view: the persistent
  flux-carrying subnetwork of the universe in one arm, species sized by
  concentration, edges by flux, the detected autocatalytic cycle highlighted.
"""

from __future__ import annotations

import json
import math

import numpy as np
from process_bigraph.visualization import Visualization

from .viz_uq import _resolve

from . import viz_style as S
from .viz_style import INK as _INK, TEAL as _TEAL, AMBER as _AMBER, SLATE as _SLATE, RUST as _RUST, MUTED as _MUTED

_CLASS_COLORS = {"reaction_universe": _TEAL, "null_network": _SLATE, "curated_rtca": _AMBER}
_FONT = S.FONT()


def enrichment_figure(rep: dict, *, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    arms = rep["arms"]
    arm_names = list(arms)
    fig = make_subplots(
        rows=1, cols=len(arm_names) + 1, horizontal_spacing=0.08,
        column_widths=[0.25] * len(arm_names) + [1 - 0.25 * len(arm_names)],
        subplot_titles=[f"{a.replace('_', ' ')}: motifs vs {arms[a]['enrichment']['n_motifs']['n_null']} nulls"
                        for a in arm_names] + ["Where motifs ignite (universe)"])
    for c, arm in enumerate(arm_names, start=1):
        a = arms[arm]
        nulls = [float(n["n_motifs"]) for n in a["nulls"]]
        uni = float(a["universe"]["n_motifs"]); cur = float(a["curated_rtca"]["n_motifs"])
        p = a["enrichment"]["n_motifs"]["p_empirical"]
        xs = np.arange(0, int(max([uni, cur] + nulls)) + 2)
        counts = [sum(1 for v in nulls if int(v) == k) for k in xs]
        fig.add_trace(go.Bar(x=xs, y=counts, name="matched nulls", marker_color=_SLATE, opacity=0.85,
                             showlegend=(c == 1), hovertemplate="%{x} motifs: %{y} nulls<extra>null_network</extra>"),
                      row=1, col=c)
        for label, val, color in (("reaction_universe", uni, _TEAL), ("curated_rtca", cur, _AMBER)):
            fig.add_trace(go.Scatter(x=[val], y=[max(counts) * 1.08 if counts else 1], mode="markers+text",
                                     marker=dict(size=14, color=color, symbol="triangle-down",
                                                 line=dict(width=1, color=_INK)),
                                     text=[label.replace("_", " ")], textposition="top center",
                                     textfont=dict(size=10, color=_INK), name=label.replace("_", " "),
                                     showlegend=(c == 1),
                                     hovertemplate=f"{label}: {val:.0f} motif(s)<extra></extra>"), row=1, col=c)
        fig.add_annotation(xref=f"x{c} domain" if c > 1 else "x domain", yref=f"y{c} domain" if c > 1 else "y domain",
                           x=0.98, y=0.98, xanchor="right", showarrow=False,
                           text=f"p = {p:.3f}, z = {a['enrichment']['n_motifs']['z']:.1f}" if math.isfinite(a['enrichment']['n_motifs']['z']) else f"p = {p:.3f}",
                           font=dict(size=11, color=_INK))
        fig.update_xaxes(title_text="persistent autocatalytic motifs", dtick=1, row=1, col=c)
        fig.update_yaxes(title_text="null networks" if c == 1 else None, row=1, col=c)
    # ignition map
    m = rep["ignition_map"]
    z = np.array(m["universe_n_motifs"], dtype=float)
    nullz = np.array(m["null_n_motifs_mean"], dtype=float)
    col = len(arm_names) + 1
    fig.add_trace(go.Heatmap(x=[f"{v:.3g}" for v in m["k_wash"]], y=[f"{v * 1e3:.3g}" for v in m["feed_formaldehyde"]],
                             z=z, colorscale=[[0, "#f1f5f9"], [1, _TEAL]], zmin=0, zmax=max(1.0, float(z.max())),
                             colorbar=dict(title="motifs", len=0.8, x=1.0, thickness=12),
                             customdata=nullz,
                             hovertemplate="k_wash %{x} 1/s<br>CH2O feed %{y} mM<br>universe motifs %{z:.0f}"
                                           "<br>null mean %{customdata:.2f}<extra></extra>"), row=1, col=col)
    fig.update_xaxes(title_text="washout k_wash (1/s)", row=1, col=col)
    fig.update_yaxes(title_text="formaldehyde feed (mM)", row=1, col=col)
    fig.update_layout(**S.base_layout(height=460, margin=dict(l=60, r=20, t=50, b=70),
                                      legend=dict(y=-0.22), bargap=0.15))
    head = rep.get("headline", "")
    cap = (head or "Persistent autocatalytic motifs in the rule-generated reaction universe, counted against "
           "matched null networks (left) and across the feed/washout map (right): enrichment beyond chance is "
           "the signal that metabolism-like topology is selected, not assumed.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Do autocatalytic motifs emerge, and beyond chance?"),
                   phase="Phase 3", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


def subnetwork_figure(rep: dict, *, arm: str = "formose_feed", title: str = "", max_nodes: int = 40) -> str:
    import plotly.graph_objects as go
    import networkx as nx

    a = rep["arms"][arm]
    snap = a["universe"].get("snapshot") or {}
    conc = {k: float(v) for k, v in snap.get("conc", {}).items() if k.startswith("X_")}
    names = snap.get("names", {})
    rxns = snap.get("reactions", [])
    motifs = a["universe"]["motifs"].get("motifs", [])
    motif_rx = {r for m in motifs for r in m["reactions"]}
    motif_sp = {s for m in motifs for s in m["species"]}
    keep = set(sorted(conc, key=lambda s: -conc[s])[:max_nodes]) | motif_sp
    g = nx.DiGraph()
    for s in keep:
        g.add_node(s)
    edges = []
    for r in rxns:
        src, dst = (r["reactants"], r["products"]) if r["rate"] > 0 else (r["products"], r["reactants"])
        for x in src:
            for y in dst:
                if x in keep and y in keep and x != y:
                    g.add_edge(x, y)
                    edges.append((x, y, abs(r["rate"]), r["id"] in motif_rx, r["rule"], r["id"]))
    if not g.nodes:
        return f"<p>no persistent subnetwork in arm {arm}</p>"
    pos = nx.kamada_kawai_layout(g.to_undirected()) if len(g) > 1 else {next(iter(g)): (0.0, 0.0)}
    vmax = max((e[2] for e in edges), default=1.0)
    fig = go.Figure()
    for x, y, v, is_motif, rule, rid in sorted(edges, key=lambda e: e[3]):
        w = 1.0 + 4.0 * (math.log10(max(v, 1e-14)) - math.log10(max(vmax, 1e-13)) + 6) / 6
        fig.add_trace(go.Scatter(x=[pos[x][0], pos[y][0]], y=[pos[x][1], pos[y][1]], mode="lines",
                                 line=dict(width=max(w, 0.6), color=_AMBER if is_motif else _MUTED),
                                 opacity=0.95 if is_motif else 0.55, hoverinfo="text",
                                 text=f"{rid} {rule}: {names.get(x, x)} → {names.get(y, y)}<br>|v| = {v:.2e} M/s",
                                 showlegend=False))
    xs = [pos[s][0] for s in g.nodes]; ys = [pos[s][1] for s in g.nodes]
    sizes = [10 + 4 * (math.log10(max(conc.get(s, 1e-12), 1e-12)) + 12) for s in g.nodes]
    colors = [_AMBER if s in motif_sp else _TEAL for s in g.nodes]
    labels = [names.get(s, s) for s in g.nodes]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", text=labels, textposition="top center",
                             textfont=dict(size=9, color=_INK),
                             marker=dict(size=sizes, color=colors, line=dict(width=1.5, color="white")),
                             hovertemplate="%{text}<br>%{customdata:.2e} M<extra></extra>",
                             customdata=[conc.get(s, 0.0) for s in g.nodes], showlegend=False))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=10, color=_TEAL), name="persistent species"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=10, color=_AMBER), name="autocatalytic cycle (detected post hoc)"))
    cyc = ", ".join(" → ".join(names.get(s, s) for s in m["species"]) + f" (gain {m['gain']:.0f}×)" for m in motifs[:2]) or "none detected"
    fig.update_layout(**S.base_layout(height=520, margin=dict(l=20, r=20, t=50, b=40),
                                      legend=dict(y=-0.05)),
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    cap = (f"{len(conc)} species above 1e-12 M; {len(rxns)} flux-carrying reactions; cycle(s): {cyc}. "
           "Node size &prop; log concentration, edge width &prop; log flux; teal = persistent species, "
           "amber = an autocatalytic cycle detected post hoc.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or f"Persistent subnetwork of the reaction universe ({arm.replace('_', ' ')})"),
                   phase="Phase 3", view="Mechanism", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class _ArtifactViz(Visualization):
    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string", "_default": ""},
        "arm": {"_type": "string", "_default": "formose_feed"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def _load(self):
        path = _resolve(str(self.config.get("report_json", "") or ""))
        if not path:
            return None
        with open(path) as f:
            return json.load(f)


class ReactionUniverseEnrichment(_ArtifactViz):
    """Phase-3 Decision view: motif enrichment of the universe vs matched nulls
    per feed arm, with the curated class marked, and the ignition map."""

    def update(self, state=None):
        rep = self._load()
        if rep is None:
            return {"html": "<p>motif_enrichment.json not found — run sims/compute_motif_enrichment.py first.</p>"}
        return {"html": enrichment_figure(rep, title=self.config["title"])}


class ReactionUniverseSubnetwork(_ArtifactViz):
    """Phase-3 Mechanism view: the persistent flux-carrying subnetwork of the
    universe with the post-hoc-detected autocatalytic cycle highlighted."""

    def update(self, state=None):
        rep = self._load()
        if rep is None:
            return {"html": "<p>motif_enrichment.json not found — run sims/compute_motif_enrichment.py first.</p>"}
        return {"html": subnetwork_figure(rep, arm=str(self.config["arm"]), title=self.config["title"])}


__all__ = ["ReactionUniverseEnrichment", "ReactionUniverseSubnetwork", "enrichment_figure", "subnetwork_figure"]
