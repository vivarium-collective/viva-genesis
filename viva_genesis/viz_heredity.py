"""Phase-7 figures — competing heredity (og-06-alt-information-per-cost).

Both render from the persisted artifact written by
``sims/compute_information_frontier.py`` (~200 exact-SSA composite runs), so
nothing is recomputed at page load:

* :class:`HeredityInformationFrontier` — the Decision view: every heredity
  class as a point on (energy per offspring, realised heritable bits) with its
  unattached control, the Pareto front, and bits per joule / per precursor.
* :class:`HeredityAttachmentMap` — the Mechanism view: where the
  ``HeredityAttachmentStep`` attaches each class across the matched budget
  scale, and the fidelity transition of the template-type classes against the
  Eigen floor.
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
_CLASS_COLORS = {"rna_like": _RUST, "hybrid": _VIOLET, "peptide": _AMBER, "compositional": _TEAL,
                 "network": _GREEN, "mineral_state": _SLATE}
_FONT = S.FONT()


def _fmt(v, nd=2):
    return "n/a" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f"{v:.{nd}g}"


def frontier_figure(rep: dict, *, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    classes = rep["classes"]
    names = list(classes)
    pareto = set(rep["frontier"].get("pareto", []))
    fig = make_subplots(rows=1, cols=2, column_widths=[0.6, 0.4], horizontal_spacing=0.1,
                        subplot_titles=["Heritable bits vs energy per offspring (attached ● / control ○)",
                                        "Information per cost"])
    for n in names:
        a, c = classes[n]["attached"], classes[n]["control"]
        col = _CLASS_COLORS.get(n, _INK)
        e = max(a["energy_per_offspring"], 1e-22)
        fig.add_trace(go.Scatter(
            x=[e], y=[a["heritable_bits"]], mode="markers+text", name=n.replace("_", " "),
            text=[n.replace("_", " ") + (" ★" if n in pareto else "")], textposition="top center",
            textfont=dict(size=10, color=col),
            error_y=dict(type="data", array=[a.get("heritable_bits_sd", 0.0)], visible=True, color=col),
            marker=dict(size=14 if n in pareto else 10, color=col, symbol="circle",
                        line=dict(width=2 if n in pareto else 1, color=_INK if n in pareto else col)),
            hovertemplate=(f"<b>{n}</b><br>bits %{{y:.3f}} (converged: {a['mi_converged_all']})<br>"
                           f"energy / offspring %{{x:.2e}} J<br>precursors / offspring {a['precursors_per_offspring']:.1f}<br>"
                           f"capacity {a['information_capacity']:.1f} bits; fidelity {a['fidelity']:.2f}<extra></extra>")),
            row=1, col=1)
        fig.add_trace(go.Scatter(
            x=[max(c["energy_per_offspring"], 1e-22)], y=[c["heritable_bits"]], mode="markers", showlegend=False,
            marker=dict(size=9, color="white", symbol="circle-open", line=dict(width=1.5, color=col)),
            hovertemplate=f"<b>{n} (unattached control)</b><br>bits %{{y:.3f}}<br>energy / offspring %{{x:.2e}} J<extra></extra>"),
            row=1, col=1)
    # the pareto front as a staircase (bits up, energy down)
    pts = sorted([(classes[n]["attached"]["energy_per_offspring"], classes[n]["attached"]["heritable_bits"]) for n in pareto])
    if len(pts) >= 2:
        fig.add_trace(go.Scatter(x=[max(p[0], 1e-22) for p in pts], y=[p[1] for p in pts], mode="lines", showlegend=False,
                                 line=dict(color=_MUTED, dash="dot", width=1.5), hoverinfo="skip"), row=1, col=1)
    bpj = rep["frontier"]["bits_per_joule"]
    order = sorted(names, key=lambda n: -(bpj[n] if (bpj[n] is not None and math.isfinite(bpj[n])) else -1))
    fig.add_trace(go.Bar(x=[n.replace("_", " ") for n in order],
                         y=[max(bpj[n], 1e-3) if bpj[n] is not None else 1e-3 for n in order],
                         marker_color=[_CLASS_COLORS.get(n, _INK) for n in order], showlegend=False,
                         hovertemplate="%{x}: %{y:.2e} bits / J<extra></extra>", name="bits per joule"),
                  row=1, col=2)
    fig.update_xaxes(type="log", title_text="energy per offspring (J; quanta + precursor equivalents)", row=1, col=1)
    fig.update_yaxes(title_text="realised heritable bits (MI net of null)", row=1, col=1)
    fig.update_yaxes(type="log", title_text="bits per joule", row=1, col=2)
    g = rep["gates"]
    fig.update_layout(**S.base_layout(height=520, margin=dict(l=20, r=20, t=50, b=60),
                                      legend=dict(y=-0.18)))
    cap = (f"{g['n_classes_ancestry_predicts']}/{len(names)} classes pass ancestry-predicts-phenotype "
           f"(converged MI &ge; {rep['meta']['pass_rule']['min_bits']} bit and &ge; {rep['meta']['pass_rule']['min_delta_vs_control']} bit above control); "
           f"Pareto front &starf; = {', '.join(sorted(pareto)) or 'none'}; bits/J spans {_fmt(g['frontier_span_decades'])} decades. "
           f"Among certified classes the best non-RNA class ({g['best_nonrna_class']}) carries {_fmt(g['nonrna_bits_fraction'])}&times; the RNA-like bits per offspring "
           f"and {g.get('best_nonrna_bits_per_joule_class')} carries {_fmt(g.get('nonrna_bits_per_joule_fraction'))}&times; its bits per joule &mdash; heredity need not be RNA.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The information-per-cost frontier of competing heredity"),
                   phase="Phase 7", view="Decision", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


def attachment_figure(rep: dict, *, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    amap = rep["attachment_map"]
    fmap = rep["fidelity_transition"]
    names = list(amap["per_class"])
    scales = amap["budget_scales"]
    fig = make_subplots(rows=1, cols=2, column_widths=[0.45, 0.55], horizontal_spacing=0.12,
                        subplot_titles=["Attached fraction vs matched budget (step deciding)",
                                        "Fidelity transition: bits vs copy fidelity (templated classes)"])
    z = [[r["attached_fraction"] for r in amap["per_class"][n]["rows"]] for n in names]
    text = [[f"{r['attached_fraction']:.2f}<br>{r['heritable_bits']:.2f} bit" for r in amap["per_class"][n]["rows"]] for n in names]
    fig.add_trace(go.Heatmap(z=z, x=[f"×{s:g}" for s in scales], y=[n.replace("_", " ") for n in names],
                             colorscale=[[0, "#f1f5f9"], [1, _TEAL]], zmin=0, zmax=1, text=text, texttemplate="%{text}",
                             textfont=dict(size=9), showscale=False,
                             hovertemplate="%{y} at budget %{x}: attached %{z:.2f}<extra></extra>"), row=1, col=1)
    for cls, d in fmap["per_class"].items():
        knob = d["knob"]
        xs = [r[knob] for r in d["rows"]]
        col = _CLASS_COLORS.get(cls, _INK)
        fig.add_trace(go.Scatter(x=xs, y=[r["heritable_bits"] for r in d["rows"]], mode="lines+markers",
                                 name=f"{cls.replace('_', ' ')} ({knob})", line=dict(color=col),
                                 marker=dict(size=[12 if r["attached_fraction"] > 0.5 else 6 for r in d["rows"]],
                                             symbol=["circle" if r["attached_fraction"] > 0.5 else "circle-open" for r in d["rows"]],
                                             color=col),
                                 hovertemplate=f"{cls} {knob}=%{{x}}<br>bits %{{y:.3f}}<extra></extra>"), row=1, col=2)
    fig.add_hline(y=fmap["best_nontemplated_bits"], line=dict(color=_MUTED, dash="dot"), row=1, col=2,
                  annotation_text="best non-templated class (attached)", annotation_position="bottom right",
                  annotation_font=dict(size=10, color=_SLATE))
    fig.update_xaxes(title_text="matched budget (feeds and power × nominal)", row=1, col=1)
    fig.update_xaxes(title_text="copy fidelity knob (q, q_p; p_m for mineral — reversed sense)", row=1, col=2)
    fig.update_yaxes(title_text="realised heritable bits", row=1, col=2)
    fig.update_layout(**S.base_layout(height=520, margin=dict(l=20, r=20, t=50, b=60),
                                      legend=dict(y=-0.2)))
    g = rep["gates"]
    note = (f"Filled markers: the step attaches (&ge; 50 % of ticks); open: refused (budget or Eigen floor). "
            f"Mean attached-fraction span low&rarr;high budget over attachable classes: {_fmt(g['attachment_budget_span'])}; "
            f"rna_like overtakes the organic non-templated classes (compositional / network) from q = {g['templated_takeover_fidelity']} "
            f"and the mineral class from q = {g['templated_takeover_vs_mineral']}.")
    inner = (fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False}))
    return S.frame(inner, title=(title or "Conditional attachment and the transition to templated heredity"),
                   phase="Phase 7", view="Mechanism", tier="conceptual_demonstration",
                   caption_text=note, caption_prefix="How to read", tone="neutral")


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


class HeredityInformationFrontier(_ArtifactViz):
    """Phase-7 Decision view: heritable bits vs energy per offspring per class, with controls and the Pareto front."""

    def update(self, state=None):
        rep = self._load()
        if rep is None:
            return {"html": "<p>information_frontier.json not found — run sims/compute_information_frontier.py first.</p>"}
        return {"html": frontier_figure(rep, title=self.config["title"])}


class HeredityAttachmentMap(_ArtifactViz):
    """Phase-7 Mechanism view: conditional attachment across the budget scale and the fidelity transition."""

    def update(self, state=None):
        rep = self._load()
        if rep is None:
            return {"html": "<p>information_frontier.json not found — run sims/compute_information_frontier.py first.</p>"}
        return {"html": attachment_figure(rep, title=self.config["title"])}


__all__ = ["HeredityInformationFrontier", "HeredityAttachmentMap", "frontier_figure", "attachment_figure"]
