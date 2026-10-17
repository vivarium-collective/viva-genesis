"""Purpose-built visualizations for the priority-spine studies og-27/29/30.

Each class drives ITS OWN real composite (built via ``build_core()`` from the
registry) and plots that composite's ACTUAL emitted observables — it does not
reuse og-00/02/03's composite-specific classes (those hardcode their own
composite + observable names). Figures follow the shared ``viz_style`` system,
re-run live with the study, and honor ``config.title`` / ``config.caption`` so a
study's authored figure title + caption flow straight through to the chrome.

- ``OgCoupledInterfaceViz`` (og-27): the evolving mineral-water interface — the
  supply it delivers (temperature, pH, H2 flux) and how mineral growth throttles
  it (porosity closing, catalytic accessibility passivating, carbonate
  saturation index driving precipitation).
- ``OgEndogenousAutocatalysisViz`` (og-29): net carbon flux + autocatalytic gain,
  and the Gate-A matched-null comparison (favorable vs ``matched_null=True`` at
  identical input fluxes).
- ``OgSpatialProtometabolismViz`` (og-30): thermophoretic enrichment + residence,
  and productive net carbon flux pore (``concentrating=True``) vs the matched
  well-mixed control (``concentrating=False``).
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from process_bigraph.visualization import Visualization

from . import viz_style as S
from .viz_style import INK, TEAL, AMBER, SLATE, RUST, VIOLET


def _col(rows, k):
    return [r[k] for r in rows if k in r]


def _run(gen, core, n_steps, **kw):
    doc = gen(core, **kw)
    sim = Composite({"state": doc}, core=core)
    sim.run(float(n_steps))
    return gather_emitter_results(sim)[("emitter",)]


class OgCoupledInterfaceViz(Visualization):
    """og-27 — the evolving geochemical interface: supply + self-throttling.

    One real run of ``og_27_coupled_geochemical_reaction_interface`` (PHREEQC +
    FiPy + mineral-surface dynamics); plots the delivered supply and the
    mineral-evolution observables that show the interface depleting.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "The interface evolves — and throttles its own supply"},
        "caption": {"_type": "string", "_default": ""},
        "n_steps": {"_type": "integer", "_default": 80},
        "flow_velocity": {"_type": "float", "_default": 1.0e-3},
        "olivine_rate": {"_type": "float", "_default": 0.15},
        "nx": {"_type": "integer", "_default": 40},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.og_27_coupled_geochemical_reaction_interface import (
            og_27_coupled_geochemical_reaction_interface as gen,
        )
        core = build_core()
        rows = _run(gen, core, self.config["n_steps"],
                    flow_velocity=float(self.config["flow_velocity"]),
                    olivine_rate=float(self.config["olivine_rate"]),
                    nx=int(self.config["nx"]))
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        from plotly.subplots import make_subplots
        from ..composites.og_27_coupled_geochemical_reaction_interface import (
            og_27_coupled_geochemical_reaction_interface as gen,
        )
        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)], gen)
        temp_c = [v - 273.15 for v in _col(rows, "temperature")]
        fig = make_subplots(
            rows=2, cols=3, vertical_spacing=0.17, horizontal_spacing=0.09,
            subplot_titles=(
                "Temperature (°C)", "pH", "H₂ source flux (mol/s)",
                "Porosity (closing)", "Catalytic accessibility (passivating)",
                "Carbonate saturation index + precipitation",
            ),
        )
        fig.add_scatter(x=t, y=temp_c, mode="lines", line=dict(color=AMBER, width=2.5), row=1, col=1)
        fig.add_scatter(x=t, y=_col(rows, "pH"), mode="lines", line=dict(color=TEAL, width=2.5), row=1, col=2)
        fig.add_scatter(x=t, y=_col(rows, "H2_flux"), mode="lines", line=dict(color=INK, width=2), row=1, col=3)
        fig.add_scatter(x=t, y=_col(rows, "porosity"), mode="lines", line=dict(color=SLATE, width=2.5), row=2, col=1)
        fig.add_scatter(x=t, y=_col(rows, "catalytic_accessibility"), mode="lines",
                        line=dict(color=VIOLET, width=2.5), row=2, col=2)
        fig.add_scatter(x=t, y=_col(rows, "saturation_index"), mode="lines",
                        line=dict(color=INK, width=2), name="saturation index", row=2, col=3)
        fig.add_scatter(x=t, y=_col(rows, "mineral_precipitation"), mode="lines",
                        line=dict(color=RUST, width=2, dash="dot"), name="precipitation", row=2, col=3)
        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor=S.GRID)
        fig.update_yaxes(showgrid=True, gridcolor=S.GRID)
        fig.update_layout(**S.base_layout(
            height=620, showlegend=True,
            legend=dict(orientation="h", y=-0.08, x=0.66, font=dict(size=10)),
            margin=dict(l=60, r=30, t=46, b=60)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "The interface evolves"),
            phase="Study 27", view="Mechanism", tier="mechanistic_prediction",
            caption_prefix="How to read",
            caption_text=(self.config.get("caption") or (
                "Porosity closing, catalytic accessibility passivating, and carbonate saturation index "
                "driving precipitation over the mineral-evolution timescale, alongside the temperature, "
                "pH and H₂ flux the interface still delivers. Plainly: as minerals grow and clog the "
                "wall, the supply it can hand downstream falls — the interface is depleting, not perpetual.")))


class OgEndogenousAutocatalysisViz(Visualization):
    """og-29 — endogenous autocatalysis + the Gate-A matched-null control.

    Runs ``og_29_endogenous_autocatalysis`` favorably and again with
    ``matched_null=True`` (identical input fluxes, autocatalytic topology
    removed); plots net carbon flux, autocatalytic gain, and the Gate-A margin.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Net carbon flux, autocatalytic gain, and the Gate-A null"},
        "caption": {"_type": "string", "_default": ""},
        "n_steps": {"_type": "integer", "_default": 120},
        "supply_H2": {"_type": "float", "_default": 1.0e-3},
        "supply_CO2": {"_type": "float", "_default": 2.0e-3},
        "k_wash": {"_type": "float", "_default": 0.05},
        "max_carbons": {"_type": "integer", "_default": 4},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.og_29_endogenous_autocatalysis import (
            og_29_endogenous_autocatalysis as gen,
        )
        core = build_core()
        kw = dict(supply_H2=float(self.config["supply_H2"]), supply_CO2=float(self.config["supply_CO2"]),
                  k_wash=float(self.config["k_wash"]), max_carbons=int(self.config["max_carbons"]))
        fav = _run(gen, core, self.config["n_steps"], matched_null=False, **kw)
        null = _run(gen, build_core(), self.config["n_steps"], matched_null=True, **kw)
        return {"html": self._figure(fav, null)}

    def _figure(self, fav, null) -> str:
        from plotly.subplots import make_subplots
        from ..composites.og_29_endogenous_autocatalysis import (
            og_29_endogenous_autocatalysis as gen,
        )
        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(fav)], gen)
        fig = make_subplots(
            rows=1, cols=3, horizontal_spacing=0.085,
            subplot_titles=("Net carbon flux", "Autocatalytic gain", "Gate A — vs matched null (final)"),
        )
        fig.add_scatter(x=t, y=_col(fav, "net_carbon_flux"), mode="lines",
                        line=dict(color=TEAL, width=2.5), name="net carbon flux", row=1, col=1)
        fig.add_scatter(x=t, y=_col(fav, "autocatalytic_gain"), mode="lines",
                        line=dict(color=INK, width=2.5), name="autocatalytic gain", row=1, col=2)

        def _final(rows, k):
            vals = _col(rows, k)
            return vals[-1] if vals else 0.0
        metrics = ["autocatalytic_gain", "net_carbon_flux"]
        labels = ["autocatalytic gain", "net carbon flux"]
        fig.add_bar(x=labels, y=[_final(fav, m) for m in metrics], marker_color=TEAL,
                    name="favorable", row=1, col=3)
        fig.add_bar(x=labels, y=[_final(null, m) for m in metrics], marker_color=SLATE,
                    name="matched null", row=1, col=3)
        fig.update_xaxes(title_text=tlabel, row=1, col=1)
        fig.update_xaxes(title_text=tlabel, row=1, col=2)
        fig.update_xaxes(showgrid=True, gridcolor=S.GRID)
        fig.update_yaxes(showgrid=True, gridcolor=S.GRID)
        fig.update_layout(**S.base_layout(
            height=400, showlegend=True, barmode="group",
            legend=dict(orientation="h", y=-0.14, x=0.5, xanchor="center", font=dict(size=10)),
            margin=dict(l=55, r=25, t=46, b=70)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Endogenous autocatalysis vs the matched null"),
            phase="Study 29", view="Mechanism", tier="null_control",
            caption_prefix="How to read",
            caption_text=(self.config.get("caption") or (
                "Steady net carbon fixation and the autocatalytic amplification factor of the vent-fed "
                "network, set against a matched null run at identical input fluxes with the autocatalytic "
                "coupling removed. Plainly: real autocatalysis has to beat a look-alike control fed exactly "
                "the same — this shows whether it does, or whether the apparent growth was just the feed.")))


class OgSpatialProtometabolismViz(Visualization):
    """og-30 — thermophoretic enrichment + productive flux pore vs control.

    Runs ``og_30_spatially_integrated_protometabolism`` in the pore
    (``concentrating=True``) and as a matched well-mixed control
    (``concentrating=False``); plots enrichment, residence, and the flux margin.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Enrichment and productive flux — pore vs control"},
        "caption": {"_type": "string", "_default": ""},
        "n_steps": {"_type": "integer", "_default": 120},
        "base_CO2": {"_type": "float", "_default": 1.0e-3},
        "base_H2": {"_type": "float", "_default": 1.0e-3},
        "k_wash": {"_type": "float", "_default": 0.05},
        "max_carbons": {"_type": "integer", "_default": 4},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.og_30_spatially_integrated_protometabolism import (
            og_30_spatially_integrated_protometabolism as gen,
        )
        kw = dict(base_CO2=float(self.config["base_CO2"]), base_H2=float(self.config["base_H2"]),
                  k_wash=float(self.config["k_wash"]), max_carbons=int(self.config["max_carbons"]))
        pore = _run(gen, build_core(), self.config["n_steps"], concentrating=True, **kw)
        ctrl = _run(gen, build_core(), self.config["n_steps"], concentrating=False, **kw)
        return {"html": self._figure(pore, ctrl)}

    def _figure(self, pore, ctrl) -> str:
        from plotly.subplots import make_subplots
        from ..composites.og_30_spatially_integrated_protometabolism import (
            og_30_spatially_integrated_protometabolism as gen,
        )
        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(pore)], gen)
        fig = make_subplots(
            rows=1, cols=3, horizontal_spacing=0.085,
            subplot_titles=("Thermophoretic enrichment factor", "Residence time",
                            "Net carbon flux — pore vs control"),
        )
        fig.add_scatter(x=t, y=_col(pore, "enrichment_factor"), mode="lines",
                        line=dict(color=AMBER, width=2.5), name="enrichment factor", row=1, col=1)
        fig.add_scatter(x=t, y=_col(pore, "residence_time"), mode="lines",
                        line=dict(color=SLATE, width=2.5), name="residence time", row=1, col=2)
        fig.add_scatter(x=t, y=_col(pore, "net_carbon_flux"), mode="lines",
                        line=dict(color=TEAL, width=2.5), name="pore (concentrating)", row=1, col=3)
        fig.add_scatter(x=t, y=_col(ctrl, "net_carbon_flux"), mode="lines",
                        line=dict(color=SLATE, width=2, dash="dash"), name="well-mixed control", row=1, col=3)
        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor=S.GRID)
        fig.update_yaxes(showgrid=True, gridcolor=S.GRID)
        fig.update_layout(**S.base_layout(
            height=400, showlegend=True,
            legend=dict(orientation="h", y=-0.14, x=0.5, xanchor="center", font=dict(size=10)),
            margin=dict(l=55, r=25, t=46, b=70)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Productive flux — pore vs well-mixed control"),
            phase="Study 30", view="Mechanism", tier="null_control",
            caption_prefix="How to read",
            caption_text=(self.config.get("caption") or (
                "Where reactive transport and thermophoresis concentrate reactants along the pore, how "
                "long they reside, and the net productive carbon flux in the structured pore against a "
                "matched well-mixed control at identical feeds. Plainly: does the pore actually help the "
                "chemistry, or would a stirred pot do just as well?")))
