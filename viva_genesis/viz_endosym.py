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


def render_s1_redundancy(out_path, steps: int = 600, block: int = 30):
    from .composites.metabolite_exchange_community import metabolite_exchange_community
    core = build_core()
    base = dict(lineages="fixer:4,reducer:4", model_proto_ecology="reaction_universe",
                p_diacid=1e-8, p_monoacid=1e-7, k_wash=0.01)
    traj = {}
    for cup, label, color in (("shared", "connected community", _TEAL),
                              ("private", "isolated control", _AMBER)):
        spec = metabolite_exchange_community(core, coupling=cup, placement="mixed", **base)
        c = Composite({"state": spec}, core=core)
        xs = [0]; ys = [float(_leaf(c.state, "community/metacommunity_robustness") or 0.0)]
        for s in range(block, steps + 1, block):
            c.run(block)
            xs.append(s); ys.append(float(_leaf(c.state, "community/metacommunity_robustness") or 0.0))
        traj[label] = (xs, ys, color)
    fig = [{"type": "scatter", "x": x, "y": y, "mode": "lines", "name": lab,
            "line": {"color": col, "width": 3}} for lab, (x, y, col) in traj.items()]
    fig.append({"type": "scatter", "x": [0, steps], "y": [0.5, 0.5], "mode": "lines",
                "line": {"color": _RED, "width": 1.5, "dash": "dash"}, "name": "redundancy threshold"})
    layout = {
        "title": {"text": "<b>A connected community develops redundancy; an isolated one does not (s1)</b><br>"
                  "<span style='font-size:12px;color:#64748b'>metacommunity robustness over time; the "
                  "connected cross-feeding community crosses the threshold (~200 steps), the isolated control does not</span>"},
        "xaxis": {"title": "simulation steps"},
        "yaxis": {"title": "metacommunity robustness", "range": [0.3, 0.65]},
        "paper_bgcolor": "white", "plot_bgcolor": "white",
        "legend": {"x": 0.98, "y": 0.02, "xanchor": "right", "yanchor": "bottom"},
        "margin": {"l": 70, "r": 30, "t": 70, "b": 60},
    }
    Path(out_path).write_text(_html("s1", fig, layout))
    return out_path


# Headline per step (from the recorded runs) + verdict colour for the overview.
_STEPS = [
    ("S1", "Metabolic partnership", "connected 0.54 &gt; isolated 0.46", "supported", _TEAL),
    ("S2", "Ecology → proximity", "22× flux advantage at low diffusion", "supported", _TEAL),
    ("S3", "Protrusions → enclosure", "classical 0.27 · inside-out 0.83", "topology-gated", _AMBER),
    ("S4", "Compartmental coupling", "survivors 1.0 (efficient) · 0.0 (weak)", "supported*", _TEAL),
    ("S5", "Symbiont → organelle", "heritable above the Eigen threshold", "supported", _TEAL),
]


def render_transition_overview(out_path):
    """The five-step endosymbiosis transition on one page — each step's headline
    result and verdict, as a left-to-right ladder (styled HTML, no Plotly)."""
    cards = []
    for tag, name, headline, verdict, color in _STEPS:
        cards.append(
            f"<div style='flex:1;min-width:150px;background:#fff;border:1px solid #e2e8f0;"
            f"border-top:4px solid {color};border-radius:10px;padding:12px 12px 14px;"
            f"box-shadow:0 1px 3px rgba(0,0,0,.06)'>"
            f"<div style='font-size:11px;letter-spacing:.06em;color:#94a3b8;font-weight:700'>{tag}</div>"
            f"<div style='font-size:14px;font-weight:700;color:#1e293b;margin:2px 0 8px'>{name}</div>"
            f"<div style='font-size:12.5px;color:#334155;line-height:1.35'>{headline}</div>"
            f"<div style='margin-top:10px'><span style='font-size:11px;font-weight:700;color:{color};"
            f"background:{color}22;border-radius:999px;padding:2px 9px'>{verdict}</span></div></div>")
    # interleave arrows between cards
    inter = []
    for i, card in enumerate(cards):
        inter.append(card)
        if i < len(cards) - 1:
            inter.append("<div style='font-size:26px;color:#94a3b8;align-self:center'>→</div>")
    ladder = ("<div style='display:flex;gap:4px;align-items:stretch;flex-wrap:nowrap;overflow-x:auto;"
              "max-width:1180px;margin:0 auto;padding:4px 12px 12px'>" + "".join(inter) + "</div>")
    html = ("<!doctype html><html><head><meta charset='utf-8'></head>"
            "<body style='font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f8fafc'>"
            "<div style='max-width:1180px;margin:0 auto;padding:18px 12px 6px'>"
            "<div style='font-size:19px;font-weight:800;color:#0f172a'>The Endosymbiotic Transition — five steps</div>"
            "<div style='font-size:13px;color:#64748b;margin:4px 0 14px'>from a metabolic partnership to a "
            "heritable organelle; each step's headline result from its own simulation, and whether it is "
            "empirically supported or still open.</div></div>"
            + ladder +
            "<div style='max-width:1180px;margin:10px auto 0;padding:0 12px;font-size:11.5px;color:#94a3b8'>"
            "supported* = conditional (holds only in the favourable regime); topology-gated = depends on an "
            "open decision (classical external engulfment vs inside-out invagination).</div>"
            "</body></html>")
    Path(out_path).write_text(html)
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


def _figure_registry():
    """figure-name -> render fn, derived from render_all's job list."""
    import inspect
    import re
    src = inspect.getsource(render_all)
    names = re.findall(r'\("[^"]+",\s*"([^"]+)\.html",\s*(\w+)\)', src)
    return {fig: globals()[fn] for fig, fn in names}


def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    reg = _figure_registry()
    if len(argv) != 2 or argv[0] not in reg:
        print(f"usage: python -m viva_genesis.viz_endosym <figure> <output-path>\n"
              f"unknown or missing figure {argv[:1]!r}; known: {', '.join(sorted(reg))}",
              file=sys.stderr)
        return 2
    Path(argv[1]).parent.mkdir(parents=True, exist_ok=True)
    reg[argv[0]](argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
