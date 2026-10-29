"""Endosymbiosis-transition figures — the discriminating result per transition step.

One self-contained Plotly figure per study, run directly from the study's composite
so the figure is the model's own output, not a redrawn claim:

* s2 — cross-lineage flux vs diffusion, proximate vs distant (the 22x proximity
  advantage that collapses when well-mixed);
* s5 — heritability vs vertical-transmission fidelity (the Eigen error catastrophe);
* s4 — internalization survivors vs pump efficiency (the benefit / collapse boundary).

Each ``render_*`` runs the composite over a parameter sweep and writes the HTML.
``render_all`` drops the three into their studies' ``viz/`` dirs.
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite

from .core import build_core

_TEAL, _AMBER, _GREY, _RED = "#2f6f8f", "#e0a53f", "#cbd5e1", "#b4442f"


def _leaf(state: dict, path: str):
    d = state
    for k in path.split("/"):
        d = d.get(k, {}) if isinstance(d, dict) else {}
    return d if not isinstance(d, dict) else None


def _run(core, composite_fn, steps, **params):
    spec = composite_fn(core, **params)
    c = Composite({"state": spec}, core=core)
    c.run(steps)
    return c.state


def _html(div_id: str, fig_data, layout, legend: str = "", maxw: int = 820) -> str:
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<script src='https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js'></script>"
            "</head><body style='font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0'>"
            f"<div id='{div_id}' style='width:100%;max-width:{maxw}px;margin:0 auto'></div>"
            f"<div style='text-align:center;font-size:12px;color:#334155;margin:4px'>{legend}</div>"
            f"<script>Plotly.newPlot('{div_id}',{json.dumps(fig_data)},{json.dumps(layout)},"
            "{responsive:true,displayModeBar:false});</script></body></html>")


def _chip(color, text):
    return (f"<span style='display:inline-block;width:12px;height:12px;background:{color};"
            f"margin:0 4px 0 14px;vertical-align:middle;border:1px solid #cbd5e1'></span>{text}")


def render_s2_proximity(out_path, steps: int = 250):
    from .composites.metabolite_exchange_community import metabolite_exchange_community
    core = build_core()
    base = dict(lineages="fixer:4,reducer:4", model_proto_ecology="reaction_universe",
                p_diacid=1e-8, p_monoacid=1e-7, k_wash=0.01)
    diffs = [0.001, 0.003, 0.01, 0.03, 0.1]
    series = {}
    for place in ("mixed", "segregated"):
        ys = []
        for kd in diffs:
            st = _run(core, metabolite_exchange_community, steps, coupling="shared",
                      placement=place, k_diffusion=kd, **base)
            ys.append(float(_leaf(st, "exchange/cross_lineage_flux_total") or 0.0))
        series[place] = ys
    fig = [
        {"type": "scatter", "x": diffs, "y": series["mixed"], "mode": "lines+markers",
         "name": "proximate (mixed)", "line": {"color": _TEAL, "width": 3}},
        {"type": "scatter", "x": diffs, "y": series["segregated"], "mode": "lines+markers",
         "name": "distant (segregated)", "line": {"color": _AMBER, "width": 3}},
    ]
    layout = {
        "title": {"text": "<b>Proximity sustains exchange — only where structure holds (s2)</b><br>"
                  "<span style='font-size:12px;color:#64748b'>cross-lineage flux vs diffusion; the "
                  "proximate advantage (22x at low diffusion) collapses when well-mixed (~1.3x)</span>"},
        "xaxis": {"title": "diffusion rate k_diffusion (1/s)", "type": "log"},
        "yaxis": {"title": "settled cross-lineage flux (mol/tick)", "rangemode": "tozero"},
        "paper_bgcolor": "white", "plot_bgcolor": "white",
        "legend": {"x": 0.98, "y": 0.98, "xanchor": "right"}, "margin": {"l": 80, "r": 30, "t": 70, "b": 60},
    }
    Path(out_path).write_text(_html("s2", fig, layout))
    return out_path


def render_s5_catastrophe(out_path, steps: int = 60):
    from .composites.heredity_lineage import heredity_lineage_comparison
    core = build_core()
    fids = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.99]
    herit = []
    for f in fids:
        st = _run(core, heredity_lineage_comparison, steps, module="template", per_site_fidelity=f)
        herit.append(float(_leaf(st, "herd/heritability") or 0.0))
    fig = [
        {"type": "scatter", "x": fids, "y": herit, "mode": "lines+markers",
         "line": {"color": _TEAL, "width": 3}, "marker": {"size": 8}, "name": "heritability"},
        {"type": "scatter", "x": [min(fids), max(fids)], "y": [0.5, 0.5], "mode": "lines",
         "line": {"color": _RED, "width": 1.5, "dash": "dash"}, "name": "stable-integration threshold"},
    ]
    layout = {
        "title": {"text": "<b>The Eigen error catastrophe (s5)</b><br>"
                  "<span style='font-size:12px;color:#64748b'>realized heritability vs per-site "
                  "transmission fidelity; below the threshold the lineage collapses to 0</span>"},
        "xaxis": {"title": "per-site vertical-transmission fidelity"},
        "yaxis": {"title": "settled heritability", "range": [-0.03, 1.03]},
        "paper_bgcolor": "white", "plot_bgcolor": "white", "showlegend": False,
        "margin": {"l": 70, "r": 30, "t": 70, "b": 60},
    }
    Path(out_path).write_text(_html("s5", fig, layout))
    return out_path


def render_s4_internalization(out_path, steps: int = 60):
    from .composites.bioenergetic_internalization import bioenergetic_internalization
    core = build_core()
    effs = [0.3, 0.45, 0.6, 0.75, 0.9, 1.0]
    surv, fit = [], []
    for e in effs:
        st = _run(core, bioenergetic_internalization, steps, catalyst_efficiency=e)
        surv.append(float(_leaf(st, "pop/survivors") or 0.0))
        fit.append(float(_leaf(st, "pop/lineage_fitness") or 0.0))
    fig = [
        {"type": "scatter", "x": effs, "y": surv, "mode": "lines+markers", "name": "survivors",
         "line": {"color": _TEAL, "width": 3}, "marker": {"size": 8}},
        {"type": "scatter", "x": effs, "y": fit, "mode": "lines+markers", "name": "lineage fitness",
         "line": {"color": _AMBER, "width": 2, "dash": "dot"}},
    ]
    layout = {
        "title": {"text": "<b>Internalization pays only with an efficient pump (s4)</b><br>"
                  "<span style='font-size:12px;color:#64748b'>settled survivors vs catalyst (pump) "
                  "efficiency; below the boundary the population cannot pay the membrane cost</span>"},
        "xaxis": {"title": "catalyst (proton-pump) efficiency"},
        "yaxis": {"title": "settled value", "range": [-0.03, 1.03]},
        "paper_bgcolor": "white", "plot_bgcolor": "white",
        "legend": {"x": 0.02, "y": 0.98}, "margin": {"l": 70, "r": 30, "t": 70, "b": 60},
    }
    Path(out_path).write_text(_html("s4", fig, layout))
    return out_path


def render_all(ws_root):
    """Generate the three figures into their studies' viz/ dirs. Returns the paths."""
    ws = Path(ws_root)
    jobs = [
        ("s2-ecology-to-proximity", "proximity-diffusion.html", render_s2_proximity),
        ("s5-symbiont-to-organelle", "eigen-catastrophe.html", render_s5_catastrophe),
        ("s4-compartmental-energetic-coupling", "internalization-boundary.html", render_s4_internalization),
    ]
    out = []
    for slug, fname, fn in jobs:
        d = ws / "workspace" / "studies" / slug / "viz"
        d.mkdir(parents=True, exist_ok=True)
        out.append(fn(str(d / fname)))
    return out
