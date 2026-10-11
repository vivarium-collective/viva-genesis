"""Workspace visualizations for viva-genesis (live in the workbench Visualizations tab).

A native ``Visualization`` subclass runs the study's own composite via
``build_core()`` and returns ``{"html": <plotly html>}`` — it re-runs with the
study and auto-registers through ``build_core()`` (it is a Step subclass, so the
package walk picks it up).
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from process_bigraph.visualization import Visualization


class VentReactorTimeseries(Visualization):
    """Campaign-0 vent-reactor trajectory: temperature, pH, source fluxes and
    porosity over time, with the Lost City acceptance window shaded.

    Reduced-reproduction model (not PHREEQC/FiPy) — see ``viva_genesis.composites``.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign 0 — vent reactor baseline"},
        "n_steps": {"_type": "integer", "_default": 120},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from .core import build_core
        from .composites.campaign0 import vent_reactor_baseline

        core = build_core()
        sim = Composite({"state": vent_reactor_baseline(core)}, core=core)
        sim.run(float(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        t = [r.get("global_time", i) for i, r in enumerate(rows)]
        temp_c = [r["temperature"] - 273.15 for r in rows]
        ph = [r["pH"] for r in rows]
        h2f = [r["H2_flux"] for r in rows]
        alkf = [r["alkalinity_flux"] for r in rows]
        por = [r["porosity"] for r in rows]

        ink, teal, amber, slate = "#1e293b", "#0d9488", "#d97706", "#64748b"
        fig = make_subplots(
            rows=2, cols=2, vertical_spacing=0.16, horizontal_spacing=0.1,
            subplot_titles=("Temperature (°C)", "pH", "Source fluxes (mol/s)", "Porosity"),
        )
        # Temperature + Lost City window 40–91 °C.
        fig.add_hrect(y0=40, y1=91, line_width=0, fillcolor=teal, opacity=0.08, row=1, col=1)
        fig.add_scatter(x=t, y=temp_c, mode="lines", line=dict(color=amber, width=2.5),
                        name="T (°C)", row=1, col=1)
        # pH + window 9.0–10.8.
        fig.add_hrect(y0=9.0, y1=10.8, line_width=0, fillcolor=teal, opacity=0.08, row=1, col=2)
        fig.add_scatter(x=t, y=ph, mode="lines", line=dict(color=teal, width=2.5),
                        name="pH", row=1, col=2)
        # Fluxes.
        fig.add_scatter(x=t, y=h2f, mode="lines", line=dict(color=ink, width=2),
                        name="H₂ flux", row=2, col=1)
        fig.add_scatter(x=t, y=alkf, mode="lines", line=dict(color=slate, width=2, dash="dot"),
                        name="alkalinity flux", row=2, col=1)
        # Porosity.
        fig.add_scatter(x=t, y=por, mode="lines", line=dict(color=slate, width=2.5),
                        name="porosity", row=2, col=2)

        fig.update_xaxes(title_text="time", showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(
            title=dict(text=self.config.get("title") or "Campaign 0 — vent reactor baseline",
                       font=dict(size=16, color=ink)),
            template="plotly_white", height=560, showlegend=False,
            margin=dict(l=60, r=30, t=70, b=50), font=dict(color=ink),
        )
        return fig.to_html(full_html=True, include_plotlyjs="cdn", config={"displayModeBar": False})
