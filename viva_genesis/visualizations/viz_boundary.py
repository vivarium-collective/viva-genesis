"""Minimal functional visualizations for the Phase-5 -alt studies.

Kept deliberately FUNCTIONAL/MINIMAL — genesis-viz owns the shared visual
language and will harmonize these into it. Each renders the headline readout of
its study directly from a fresh composite run (no persisted artifact needed).
"""
from __future__ import annotations

from process_bigraph.visualization import Visualization

from . import viz_style as S
from .viz_style import INK as _INK, TEAL as _TEAL, AMBER as _AMBER, SLATE as _SLATE


def _rows(generator, core, **kwargs):
    from process_bigraph import Composite, gather_emitter_results
    n = kwargs.pop("n_steps", 40)   # pop BEFORE building the composite (not a generator kwarg)
    sim = Composite({"state": generator(core, **kwargs)}, core=core)
    sim.run(float(n))
    return gather_emitter_results(sim)[("emitter",)]


class EndogenousBoundaryViz(Visualization):
    """og-04-alt: the agents count over time in the favorable (endogenous
    synthesis) arm vs the synthesis-ablated control — the boundary forms from
    chemistry, and does not without it."""

    config_schema = {
        "title": {"_type": "string", "_default": "Boundary forms from chemistry"},
        "n_steps": {"_type": "integer", "_default": 40},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go
        from ..core import build_core
        from ..composites.endogenous_boundary import endogenous_boundary

        n = int(self.config["n_steps"])
        fav = _rows(endogenous_boundary, build_core(), k_synth=5e-2, n_steps=n)
        abl = _rows(endogenous_boundary, build_core(), k_synth=1e-12, n_steps=n)

        def _series(rows, key):
            return [float(r.get(key, 0.0)) for r in rows]

        t = list(range(len(fav)))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t, y=_series(fav, "n_agents"), mode="lines",
                                 name="favorable (endogenous synthesis)",
                                 line=dict(color=_TEAL, width=2.5)))
        fig.add_trace(go.Scatter(x=list(range(len(abl))), y=_series(abl, "n_agents"),
                                 mode="lines", name="synthesis ablated (control)",
                                 line=dict(color=_SLATE, width=2, dash="dash")))
        fig.update_layout(**S.base_layout(height=420, width=720, margin=dict(l=60, r=30, t=40, b=50)),
                          xaxis_title="step", yaxis_title="individuals in the agents map (n_agents)")
        cap = ("The individuals count (n_agents) climbs in the favorable arm, where endogenous amphiphile "
               "synthesis builds the boundary, but stays flat when synthesis is ablated (dashed). The "
               "boundary forms from the chemistry, and does not without it &mdash; that favorable-vs-ablated "
               "contrast is the result.")
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return {"html": S.frame(inner, title=(self.config.get("title") or "Boundary forms from chemistry"),
                                phase="Phase 5", view="Mechanism", tier="mechanistic_prediction",
                                caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=760)}


class PhysicalReproductionViz(Visualization):
    """og-growth-alt: the lineage — population and deepest generation over time —
    with the total volume held constant (daughter volumes sum to the mother)."""

    config_schema = {
        "title": {"_type": "string", "_default": "A multi-generation lineage in the agents map"},
        "n_steps": {"_type": "integer", "_default": 30},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        from ..core import build_core
        from ..composites.physical_reproduction import physical_reproduction

        rows = _rows(physical_reproduction, build_core(), growth_per_step=0.4,
                     n_steps=int(self.config["n_steps"]))
        t = list(range(len(rows)))

        def s(key):
            return [float(r.get(key, 0.0)) for r in rows]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=t, y=s("n_agents"), mode="lines", name="population (n_agents)",
                                 line=dict(color=_TEAL, width=2.5)), secondary_y=False)
        fig.add_trace(go.Scatter(x=t, y=s("max_generation"), mode="lines", name="deepest generation",
                                 line=dict(color=_AMBER, width=2.5)), secondary_y=True)
        fig.update_layout(**S.base_layout(height=420, width=720, margin=dict(l=60, r=60, t=40, b=50)),
                          xaxis_title="step")
        fig.update_yaxes(title_text="population", secondary_y=False)
        fig.update_yaxes(title_text="generation", secondary_y=True)
        cap = ("Population (n_agents) and the deepest generation both climb as individuals grow and divide; "
               "total volume is conserved across each division (daughter volumes sum to the mother), so this "
               "is physical reproduction of a lineage, not spawning.")
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return {"html": S.frame(inner, title=(self.config.get("title") or "A multi-generation lineage in the agents map"),
                                phase="Phase 5", view="Mechanism", tier="mechanistic_prediction",
                                caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=760)}
