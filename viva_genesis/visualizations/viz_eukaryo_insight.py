"""Eukaryogenesis s-track insight figures — richer replacements for the s1/s4/s5 headline bars.

Each study's two-bar favorable-vs-control snapshot is upgraded to a figure that shows the
*mechanism*, not just the gap:

- ``S1RedundancyTrajectoryViz``: functional redundancy accruing over time in the connected
  community while the isolated control stays flat below the gate.
- ``S4InternalizationDoseViz``: the catalyst-efficiency threshold — survival is a sharp
  dose-response, so internalization pays only above a minimum pump efficiency.
- ``S5ErrorThresholdViz``: the Eigen error threshold — heritability vs per-site fidelity as a
  smooth climb that crosses the gate, against a non-heritable baseline that transmits nothing.

(s2 and s3 get spatial figures instead — see viz_endosym_spatial / the CPM lattice render.)
All curves come from fresh composite runs.
"""
from __future__ import annotations

import json

from process_bigraph import Composite
from process_bigraph.visualization import Visualization

from . import viz_style as S
from ..core import build_core

_PLOTLY = "https://cdn.plot.ly/plotly-2.27.0.min.js"


def _run_state(G, core, group, obs, *, n_steps, **kw):
    sim = Composite({"state": G(core=core, **kw)}, core=core)
    sim.run(float(n_steps))
    return float((sim.state.get(group) or {}).get(obs, 0.0))


def _run_series(G, core, group, obs, *, n_steps, **kw):
    sim = Composite({"state": G(core=core, **kw)}, core=core)
    ys = []
    for _ in range(int(n_steps)):
        sim.run(1)
        ys.append(float((sim.state.get(group) or {}).get(obs, 0.0)))
    return ys


def _plot(div, data, layout):
    return (f'<div id="{div}" style="height:360px"></div>'
            f'<script src="{_PLOTLY}"></script>'
            f'<script>Plotly.newPlot("{div}",{json.dumps(data)},{json.dumps(layout)},'
            f'{{responsive:true,displayModeBar:false}});</script>')


class S1RedundancyTrajectoryViz(Visualization):
    """S1: the connected community *develops* functional redundancy over time; the isolated
    (no-exchange) control cannot — the partner dependence is the growing gap, not a single number."""
    config_schema = {"title": {"_type": "string", "_default": "A partner-dependent advantage, accruing over time"},
                     "n_steps": {"_type": "integer", "_default": 250}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.metabolite_exchange_community import metabolite_exchange_community as G
        core = build_core(); n = int(self.config["n_steps"])
        kw = dict(lineages="fixer:4,reducer:4", model_proto_ecology="reaction_universe",
                  p_diacid=1.0e-8, p_monoacid=1.0e-7, k_wash=0.01)
        conn = _run_series(G, core, "community", "metacommunity_robustness", n_steps=n, coupling="shared", **kw)
        iso = _run_series(G, core, "community", "metacommunity_robustness", n_steps=n, coupling="private", **kw)
        x = list(range(1, n + 1))
        data = [
            dict(type="scatter", x=x, y=conn, mode="lines", name="connected (shared pore)",
                 line=dict(color=S.TEAL, width=2.6), fill="tozeroy", fillcolor="rgba(13,148,136,0.08)",
                 hovertemplate="tick %{x}<br>robustness %{y:.3f}<extra></extra>"),
            dict(type="scatter", x=x, y=iso, mode="lines", name="isolated control (private)",
                 line=dict(color=S.SLATE, width=2.2, dash="dot"),
                 hovertemplate="tick %{x}<br>robustness %{y:.3f}<extra></extra>"),
        ]
        layout = S.base_layout(
            height=360, margin=dict(l=62, r=20, t=20, b=64),
            xaxis=dict(title="community time (ticks)", gridcolor=S.GRID, zeroline=False),
            yaxis=dict(title="metacommunity robustness", range=[0, 1.02], gridcolor=S.GRID, zeroline=False),
            shapes=[dict(type="line", x0=1, x1=n, y0=0.5, y1=0.5, xref="x", yref="y",
                         line=dict(color=S.AMBER, width=1.8, dash="dash"))],
            annotations=[dict(x=1, y=0.5, xref="x", yref="y", text="gate 0.5", showarrow=False,
                              xanchor="left", yanchor="bottom", font=dict(size=10, color=S.AMBER))])
        return {"html": S.frame(_plot("s1traj", data, layout), title=self.config.get("title"),
                tier="first fidelity", view="Mechanism", tone="neutral", max_width=820,
                caption_text=("Cross-feeding fills in missing capabilities only when agents share a common "
                              "pore: the connected community climbs past the redundancy gate while the isolated "
                              "control plateaus below it. The <b>gap widens over time</b> — the advantage is the "
                              "partnership, not any single lineage."))}


class S4InternalizationDoseViz(Visualization):
    """S4: survival under a collapsing external gradient is a sharp dose-response in pump
    efficiency — internalizing gradient generation pays only above a threshold efficiency."""
    config_schema = {"title": {"_type": "string", "_default": "Internalization pays only above a pump-efficiency threshold"},
                     "n_steps": {"_type": "integer", "_default": 60}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.bioenergetic_internalization import bioenergetic_internalization as G
        core = build_core(); n = int(self.config["n_steps"])
        effs = [0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.8, 1.0]
        ys = [_run_state(G, core, "pop", "survivors", n_steps=n, catalyst_efficiency=e) for e in effs]
        # threshold = first efficiency clearing the 0.5 gate
        thr = next((e for e, y in zip(effs, ys) if y > 0.5), None)
        data = [
            dict(type="scatter", x=effs, y=ys, mode="lines+markers", name="surviving fraction",
                 line=dict(color=S.TEAL, width=2.6), marker=dict(size=7, color=S.TEAL),
                 fill="tozeroy", fillcolor="rgba(13,148,136,0.08)",
                 hovertemplate="efficiency %{x:.2f}<br>survivors %{y:.3f}<extra></extra>"),
        ]
        shapes = [dict(type="line", x0=effs[0], x1=effs[-1], y0=0.5, y1=0.5, xref="x", yref="y",
                       line=dict(color=S.AMBER, width=1.8, dash="dash"))]
        anns = [dict(x=effs[0], y=0.5, xref="x", yref="y", text="survival gate 0.5", showarrow=False,
                     xanchor="left", yanchor="bottom", font=dict(size=10, color=S.AMBER))]
        if thr is not None:
            shapes.append(dict(type="line", x0=thr, x1=thr, y0=0, y1=1.02, xref="x", yref="y",
                               line=dict(color=S.RUST, width=1.6, dash="dot")))
            anns.append(dict(x=thr, y=1.0, xref="x", yref="y", text=f"threshold &asymp; {thr:g}",
                             showarrow=False, xanchor="left", yanchor="top",
                             font=dict(size=10, color=S.RUST)))
        layout = S.base_layout(
            height=360, margin=dict(l=62, r=20, t=20, b=64), showlegend=False,
            xaxis=dict(title="catalyst (proton-pump) efficiency", gridcolor=S.GRID, zeroline=False),
            yaxis=dict(title="surviving fraction (collapsing gradient)", range=[0, 1.05],
                       gridcolor=S.GRID, zeroline=False),
            shapes=shapes, annotations=anns)
        return {"html": S.frame(_plot("s4dose", data, layout), title=self.config.get("title"),
                tier="first fidelity", view="Mechanism", tone="neutral", max_width=820,
                caption_text=("As the external gradient collapses, survival depends sharply on how efficiently "
                              "the host's own pump can internalize gradient generation: below the threshold the "
                              "membrane cost is not repaid and the population dies; above it, survival saturates. "
                              "Internalization is <b>not free — it pays only with an efficient pump</b>."))}


class S5ErrorThresholdViz(Visualization):
    """S5: heritable integration crosses the Eigen error threshold — heritability climbs with
    per-site fidelity and clears the gate, while a non-heritable mechanism transmits nothing."""
    config_schema = {"title": {"_type": "string", "_default": "Heritable integration needs high fidelity — the Eigen threshold"},
                     "n_steps": {"_type": "integer", "_default": 60}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.heredity_lineage import heredity_lineage_comparison as G
        core = build_core(); n = int(self.config["n_steps"])
        fids = [0.70, 0.75, 0.80, 0.85, 0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995, 0.999]
        tmpl = [_run_state(G, core, "herd", "heritability", n_steps=n, module="template", per_site_fidelity=f)
                for f in fids]
        nh = _run_state(G, core, "herd", "heritability", n_steps=n, module="non-heritable", per_site_fidelity=0.99)
        thr = next((f for f, y in zip(fids, tmpl) if y > 0.95), None)
        data = [
            dict(type="scatter", x=fids, y=tmpl, mode="lines+markers", name="heritable template",
                 line=dict(color=S.TEAL, width=2.6), marker=dict(size=7, color=S.TEAL),
                 hovertemplate="fidelity %{x:.3f}<br>heritability %{y:.3f}<extra></extra>"),
            dict(type="scatter", x=fids, y=[nh] * len(fids), mode="lines", name="non-heritable control",
                 line=dict(color=S.SLATE, width=2.0, dash="dot"),
                 hovertemplate="non-heritable<br>heritability %{y:.3f}<extra></extra>"),
        ]
        shapes = [dict(type="line", x0=fids[0], x1=fids[-1], y0=0.95, y1=0.95, xref="x", yref="y",
                       line=dict(color=S.AMBER, width=1.8, dash="dash"))]
        anns = [dict(x=fids[0], y=0.95, xref="x", yref="y", text="integration gate 0.95", showarrow=False,
                     xanchor="left", yanchor="bottom", font=dict(size=10, color=S.AMBER))]
        if thr is not None:
            shapes.append(dict(type="line", x0=thr, x1=thr, y0=0, y1=1.02, xref="x", yref="y",
                               line=dict(color=S.RUST, width=1.6, dash="dot")))
            anns.append(dict(x=thr, y=0.06, xref="x", yref="y", text=f"error threshold &asymp; {thr:g}",
                             showarrow=False, xanchor="right", yanchor="bottom",
                             font=dict(size=10, color=S.RUST)))
        layout = S.base_layout(
            height=360, margin=dict(l=62, r=20, t=20, b=64),
            xaxis=dict(title="per-site transmission fidelity", gridcolor=S.GRID, zeroline=False),
            yaxis=dict(title="settled heritability", range=[0, 1.04], gridcolor=S.GRID, zeroline=False),
            shapes=shapes, annotations=anns)
        return {"html": S.frame(_plot("s5eigen", data, layout), title=self.config.get("title"),
                tier="first fidelity", view="Mechanism", tone="neutral", max_width=820,
                caption_text=("A symbiont becomes a heritable organelle only when template fidelity is high "
                              "enough to beat Eigen's error catastrophe: below the error threshold the "
                              "information is lost each generation, above it heritability saturates and a new "
                              "evolutionary individual persists. A non-heritable mechanism transmits nothing at "
                              "any fidelity."))}
