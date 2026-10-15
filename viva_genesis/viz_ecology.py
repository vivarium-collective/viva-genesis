"""Phase-8 figures — biochemical ecology (og-07-alt-real-metabolite-exchange).

Both render from the persisted artifact written by
``sims/compute_community_function_map.py`` (~100 composite runs with a
libRoadRunner network inside every agent), so nothing is recomputed at page
load:

* :class:`CommunityFunctionMap` — the Decision view: where the community-only
  function emerges over (diacid permeability x pore residence), with the
  levels of every community-only product class at the canonical point across
  the arms (community / monocultures / private / generalist) and the
  emergence boundary against the range the charged-solute permeability
  literature would place a fatty-acid vesicle in.
* :class:`MetaboliteExchangeMap` — the Mechanism / World view: the agents on
  the pore cells coloured by lineage, the exchanged intermediates (the
  cross-lineage flux per species), the growth of the community's function
  union against the private and generalist arms, and og-07's gate readouts
  per arm (robustness, isolated, gain, LUCA overlap, completeness).
"""

from __future__ import annotations

import json
import math

from process_bigraph.visualization import Visualization

from .viz_uq import _resolve

from . import viz_style as S
from .viz_style import (INK as _INK, TEAL as _TEAL, AMBER as _AMBER, SLATE as _SLATE,
                        RUST as _RUST, MUTED as _MUTED, VIOLET as _VIOLET)

_GREEN = "#15803d"  # 6th categorical (not in the core palette)
_ARM_COLORS = {"community": _TEAL, "mono_fixer": _AMBER, "mono_reducer": _VIOLET, "private": _SLATE,
               "generalist": _RUST, "segregated": _GREEN}
_LINEAGE_COLORS = {"fixer": _AMBER, "reducer": _VIOLET, "generalist": _RUST, "condenser": _GREEN}
_FONT = S.FONT()
# the range the charged-solute permeability literature places fatty-acid
# vesicles in (nucleotides / ribose, ~1e-11-1e-10 m/s; proposed_inputs, pending)
_MEASURED_CHARGED_RANGE = (1.0e-11, 1.0e-10)


def _fmt(v, nd=2):
    return "n/a" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f"{v:.{nd}g}"


def _pretty(f: str) -> str:
    return f.replace("_", " ")


def community_function_figure(rep: dict, *, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    dmap, gate = rep["decision_map"], rep["gate"]
    ps, ks = list(dmap["p_diacid"]), list(dmap["k_wash"])
    cell = {(c["p_diacid"], c["k_wash"]): c for c in dmap["cells"]}
    z = [[cell[(p, k)]["max_community_only_level"] if cell[(p, k)]["n_community_only"] else 0.0 for p in ps] for k in ks]
    zlog = [[math.log10(v) if v > 0 else None for v in row] for row in z]
    text = [[f"{cell[(p, k)]['n_community_only']} fn<br>{', '.join(_pretty(f) for f in cell[(p, k)]['community_only_functions']) or '—'}"
             for p in ps] for k in ks]
    fig = make_subplots(rows=1, cols=2, column_widths=[0.55, 0.45], horizontal_spacing=0.17,
                        subplot_titles=["Where community-only function emerges",
                                        "Product classes at the canonical point, per arm"])
    fig.add_trace(go.Heatmap(
        x=[f"{p:.0e}" for p in ps], y=[f"{1 / k:.0f} s" for k in ks], z=zlog, text=text,
        hovertemplate="P(diacid) %{x} m/s<br>residence %{y}<br>level 10^%{z:.1f} M<br>%{text}<extra></extra>",
        colorscale=[[0.0, "#e2e8f0"], [1.0, _TEAL]],
        colorbar=dict(title="log₁₀ M", x=0.455, len=0.9, thickness=9,
                      title_font=dict(size=10), tickfont=dict(size=9)),
        zmin=-9.5, zmax=-6.5, showscale=True), row=1, col=1)
    # the canonical point and the measured charged-solute range
    nom = rep["meta"]["nominal"]
    fig.add_trace(go.Scatter(x=[f"{nom['p_diacid']:.0e}"], y=[f"{1 / nom['k_wash']:.0f} s"], mode="markers",
                             marker=dict(symbol="star", size=18, color=_INK, line=dict(width=1, color="white")),
                             name="canonical point", hovertemplate="canonical operating point<extra></extra>"), row=1, col=1)
    boundary = dmap.get("emergence_p_diacid_by_k_wash", {})
    bx = [f"{boundary[str(k)]:.0e}" for k in ks if boundary.get(str(k)) is not None]
    by = [f"{1 / k:.0f} s" for k in ks if boundary.get(str(k)) is not None]
    if bx:
        fig.add_trace(go.Scatter(x=bx, y=by, mode="lines+markers", line=dict(color=_RUST, width=2, dash="dot"),
                                 marker=dict(size=9, color=_RUST), name="emergence boundary",
                                 hovertemplate="emerges from P(diacid) = %{x} m/s at residence %{y}<extra></extra>"), row=1, col=1)
    lo, hi = _MEASURED_CHARGED_RANGE
    inside = [f"{p:.0e}" for p in ps if lo <= p <= hi]
    if inside:
        fig.add_vrect(x0=inside[0], x1=inside[-1], fillcolor=_MUTED, opacity=0.18, line_width=0, row=1, col=1,
                      annotation_text="measured charged-solute range (fatty-acid vesicles; proposed ref, pending)",
                      annotation_position="top left", annotation_font=dict(size=9, color=_SLATE))
    # arm levels
    fns = gate["community_only_functions"]
    arms = ["community", "mono_fixer", "mono_reducer", "private", "generalist"]
    floor = float(rep["meta"]["floor"])
    for arm in arms:
        vals = [gate["levels"][f][arm] for f in fns]
        fig.add_trace(go.Bar(
            x=[_pretty(f) for f in fns], y=[max(float(v or 0.0), 1e-13) for v in vals], name=arm.replace("_", " "),
            marker_color=_ARM_COLORS[arm],
            hovertemplate=f"<b>{arm}</b><br>%{{x}}: %{{y:.2e}} M<extra></extra>"), row=1, col=2)
    fig.add_hline(y=floor, line=dict(color=_INK, width=1, dash="dash"), row=1, col=2,
                  annotation_text="function floor (1 nM)", annotation_position="top left", annotation_font=dict(size=9))
    fig.update_yaxes(type="log", title_text="settled max concentration (M)", row=1, col=2, range=[-13, -6])
    fig.update_xaxes(title_text="diacid permeability (m/s)", row=1, col=1)
    fig.update_yaxes(title_text="pore residence 1/k_wash", row=1, col=1)
    prec = [d for f in fns for d in (gate.get("precursors") or {}).get(f, [])]
    sub = (f"community-only: {', '.join(_pretty(f) for f in fns) or 'none'} | vanish without exchange: "
           f"{len(gate['vanish_without_exchange'])}/{len(fns)} | precursor crossing between lineages: "
           + (f"{prec[0]['name']} from the {prec[0]['made_by'] and 'other'} lineage ({_fmt(prec[0]['molecules_per_tick'])} molecules/tick)" if prec else "none")
           + f" | max cell completeness {_fmt(gate['max_cell_completeness'])}"
           + (f" | community / generalist {_fmt(gate['community_over_generalist'])}" if gate.get("community_over_generalist") else ""))
    fig.update_layout(**S.base_layout(height=520, barmode="group", margin=dict(t=44, b=90),
                                      legend=dict(orientation="h", y=-0.22, x=0.0, font=dict(size=10))))
    cap = (
        "A metabolic function the mixed community produces that no single lineage does, over "
        "(diacid permeability × pore residence). The red dotted line is the emergence boundary; the "
        "shaded band is the measured charged-solute range. Right: the best product class per arm vs the "
        f"1 nM floor. <b>{sub}</b>. These are mean-field, community-level concentrations (not single-molecule "
        "lineages), so the result is a coarse-grained demonstration of cross-feeding function, not a cell."
    )
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Does cross-feeding build community-only function?"),
                   phase="Phase 8", view="Decision", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="caution")


def exchange_map_figure(rep: dict, *, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    comm = rep["arms"]["community"]
    gate = rep["gate"]
    series = rep["series"]
    og07 = rep["og07"]
    fig = make_subplots(rows=1, cols=3, column_widths=[0.38, 0.3, 0.32], horizontal_spacing=0.1,
                        subplot_titles=["Agents + cross-lineage exchange",
                                        "Functions held over time",
                                        "og-07 readouts, recomputed"])
    # --- World: agents on cells, intermediates as arrows ---------------------------------------
    lineages = {aid.rsplit("-", 1)[0]: None for aid in comm["rates_final"]}
    n_agents = len(comm["rates_final"])
    agent_ids = list(comm["rates_final"])
    xs = [(i + 0.5) / n_agents for i in range(n_agents)]
    field = comm.get("field_final") or {}
    n_cells = max(len(field), 1)
    for i, aid in enumerate(agent_ids):
        lin = aid.rsplit("-", 1)[0]
        r = comm["rates_final"][aid]
        fig.add_trace(go.Scatter(
            x=[xs[i]], y=[1.0], mode="markers+text", text=[lin[0].upper()], textposition="middle center",
            textfont=dict(color="white", size=11), marker=dict(size=30, color=_LINEAGE_COLORS.get(lin, _INK)),
            name=lin, legendgroup=lin, showlegend=(aid == next(a for a in agent_ids if a.startswith(lin))),
            hovertemplate=(f"<b>{aid}</b><br>cell {min(int(xs[i] * n_cells), n_cells - 1)}<br>CO2 fixed {_fmt(r.get('co2_fixation'))} mol/s<br>"
                           f"H2 consumed {_fmt(r.get('h2_consumption'))} mol/s<br>organic C {_fmt(r.get('total_organic_carbon'))} M<br>"
                           f"dissipation {_fmt(r.get('dissipation'))} W<extra></extra>")), row=1, col=1)
    for ck in sorted(field):
        i = int(ck[1:])
        fig.add_shape(type="rect", x0=i / n_cells, x1=(i + 1) / n_cells, y0=0.4, y1=1.6, line=dict(color=_MUTED, width=1),
                      fillcolor="#f8fafc", layer="below", row=1, col=1)
        c = field[ck]
        fig.add_annotation(x=(i + 0.5) / n_cells, y=0.5, text=f"cell {i}<br>OAA {_fmt(c.get('X_ACKA'))} M", showarrow=False,
                           font=dict(size=9, color=_SLATE), row=1, col=1)
    inter = gate.get("exchanged_intermediates") or []
    prec = [d for f in gate.get("community_only_functions", []) for d in (gate.get("precursors") or {}).get(f, [])]
    lines_ = [f"precursor ⇄ {d['name']}: {_fmt(d['molecules_per_tick'])} molecules/tick → {d['made_by']}" for d in prec[:2]]
    lines_ += [f"⇄ {d['name']}: {_fmt(d['moles_per_tick'] * 6.02214076e23)} molecules/tick" for d in inter[:3]]
    for j, txt in enumerate(lines_[:5]):
        fig.add_annotation(x=0.5, y=1.5 - 0.1 * j, text=txt, showarrow=False,
                           font=dict(size=10, color=_TEAL if txt.startswith("precursor") else _SLATE), row=1, col=1)
    fig.update_xaxes(title_text="position along the pore (inlet → trap end)", range=[0, 1], row=1, col=1)
    fig.update_yaxes(visible=False, range=[0.3, 1.7], row=1, col=1)
    # --- function union over time ------------------------------------------------------------------
    for arm, col in (("community", _TEAL), ("private", _SLATE), ("generalist", _RUST)):
        s = series.get(arm)
        if not s:
            continue
        fig.add_trace(go.Scatter(x=s["t"], y=s["n_functions_union"], mode="lines", name=f"{arm} union", line=dict(color=col, width=2),
                                 hovertemplate=f"{arm}: %{{y}} functions at t=%{{x}}<extra></extra>"), row=1, col=2)
    s = series.get("community")
    if s:
        fig.add_trace(go.Scatter(x=s["t"], y=s["robustness_gain"], mode="lines", name="community robustness gain",
                                 line=dict(color=_AMBER, width=1.5, dash="dot"), yaxis="y3",
                                 hovertemplate="robustness gain %{y:.2f} at t=%{x}<extra></extra>"), row=1, col=2)
    fig.update_xaxes(title_text="tick", row=1, col=2)
    fig.update_yaxes(title_text="product classes held", row=1, col=2)
    # --- og-07 readouts per arm ---------------------------------------------------------------------
    keys = [("metacommunity_robustness", "robustness"), ("isolated_robustness", "isolated (produced)"),
            ("robustness_gain", "gain"), ("luca_capability_overlap", "LUCA overlap"), ("mean_cell_completeness", "mean completeness"),
            ("max_cell_completeness", "max completeness")]
    for arm in ("community", "private", "mono_fixer", "mono_reducer", "generalist"):
        d = og07.get(arm)
        if not d:
            continue
        fig.add_trace(go.Bar(x=[lab for _, lab in keys], y=[float(d[k]) for k, _ in keys], name=arm.replace("_", " "),
                             marker_color=_ARM_COLORS[arm], hovertemplate=f"<b>{arm}</b> %{{x}}: %{{y:.2f}}<extra></extra>"), row=1, col=3)
    fig.update_yaxes(title_text="fraction", range=[0, 1.05], row=1, col=3)
    led = rep["ledger"]
    sub = (f"element ledger over agents + field: C residual ≤ {_fmt(led['C_residual_max'])}, N ≤ {_fmt(led['N_residual_max'])}, "
           f"P ≤ {_fmt(led['P_residual_max'])} on {led['n_runs']} runs | exchange-rule firings (canonical community): "
           + ", ".join(f"{k} {int(v)}" for k, v in (led.get("firings_by_rule_nominal_community") or {}).items()))
    fig.update_layout(**S.base_layout(height=520, barmode="group", margin=dict(t=44, b=90),
                                      legend=dict(orientation="h", y=-0.22, x=0.0, font=dict(size=10))))
    cap = (
        "Real metabolite flux between lineages on the pore. Left: agents on cells with the intermediates "
        "that cross between lineages (teal = a precursor one lineage makes for the other). Middle: product "
        "classes the community holds over time. Right: og-07's robustness / completeness readouts recomputed "
        f"from the real agents. <b>{sub}</b>."
    )
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "What crosses between lineages"),
                   phase="Phase 8", view="Mechanism", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1100)


class _ArtifactViz(Visualization):
    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string", "_default": ""},
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


class CommunityFunctionMap(_ArtifactViz):
    """Phase-8 Decision view: where a function the community has and no lineage can make emerges over
    (diacid permeability x pore residence), with its level per arm at the canonical point."""

    def update(self, state=None):
        rep = self._load()
        if rep is None:
            return {"html": "<p>community_function_map.json not found — run sims/compute_community_function_map.py first.</p>"}
        return {"html": community_function_figure(rep, title=self.config["title"])}


class MetaboliteExchangeMap(_ArtifactViz):
    """Phase-8 Mechanism / World view: agents on the pore, the intermediates crossing between lineages, the
    function union over time, and og-07's readouts recomputed from real agents."""

    def update(self, state=None):
        rep = self._load()
        if rep is None:
            return {"html": "<p>community_function_map.json not found — run sims/compute_community_function_map.py first.</p>"}
        return {"html": exchange_map_figure(rep, title=self.config["title"])}


__all__ = ["CommunityFunctionMap", "MetaboliteExchangeMap", "community_function_figure", "exchange_map_figure"]
