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


class OgReactionAtlasCoverageViz(Visualization):
    """og-28 — prebiotic reaction atlas coverage by confidence tier.

    Runs ``og_28_prebiotic_reaction_atlas`` (the atlas-builder composite) and
    reports its coverage from the composite's real coverage emit: how many
    reactions are accepted at each confidence tier (measured / inferred /
    hypothetical), accepted vs proposed-and-held, the carbon species connected,
    and the zero-leakage gate — unbalanced / unsourced records are HELD OUT of
    the accepted set, never admitted. (Counts, not a trajectory, so the final
    emitted row is the atlas state.)
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Reaction atlas coverage by confidence tier"},
        "caption": {"_type": "string", "_default": ""},
        "n_steps": {"_type": "integer", "_default": 3},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.og_28_prebiotic_reaction_atlas import (
            og_28_prebiotic_reaction_atlas as gen,
        )
        core = build_core()
        rows = _run(gen, core, self.config["n_steps"])
        return {"html": self._figure(rows[-1] if rows else {})}

    def _figure(self, last) -> str:
        from plotly.subplots import make_subplots

        def g(k):
            return float(last.get(k, 0) or 0)

        covered = int(g("carbon_species_covered"))
        fig = make_subplots(
            rows=1, cols=3, horizontal_spacing=0.09,
            subplot_titles=("Accepted reactions by tier", "Accepted vs proposed",
                            "Zero-leakage gate"),
        )
        fig.add_bar(x=["measured", "inferred", "hypothetical"],
                    y=[g("n_measured"), g("n_inferred"), g("n_hypothetical")],
                    marker_color=[TEAL, AMBER, SLATE], showlegend=False, row=1, col=1)
        fig.add_bar(x=["accepted", "proposed (held)"], y=[g("n_accepted"), g("n_proposed")],
                    marker_color=[TEAL, SLATE], showlegend=False, row=1, col=2)
        fig.add_bar(x=["admitted unbalanced", "held out"],
                    y=[g("accepted_balance_violations"), g("balance_violations_held")],
                    marker_color=[RUST, SLATE], showlegend=False, row=1, col=3)
        fig.add_annotation(text=f"C-species connected: {covered}", showarrow=False,
                           xref="paper", yref="paper", x=0.0, y=1.14, font=dict(size=11, color=INK))
        fig.update_yaxes(showgrid=True, gridcolor=S.GRID)
        fig.update_layout(**S.base_layout(height=400, showlegend=False,
                                          margin=dict(l=50, r=25, t=60, b=50)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Reaction atlas coverage by confidence tier"),
            phase="Study 28", view="Decision", tier="conceptual_demonstration",
            caption_prefix="How to read",
            caption_text=(self.config.get("caption") or (
                "The candidate-reaction network connecting C1–C3 products to functional chemistry, counted "
                "by confidence tier — measured, inferred, hypothetical — with accepted vs proposed-and-held, "
                "and the zero-leakage gate: unbalanced / unsourced reactions are held out of the accepted "
                "set (admitted-unbalanced reads 0). Plainly: the chemistry we can defensibly connect, how "
                "sure we are of each step, and proof that nothing unbalanced slipped in.")))


class OgMembraneCohesionViz(Visualization):
    """og-31 — Martini bilayer cohesion: potential energy settling negative.

    Runs ``og_31_protometabolism_to_amphiphiles`` (the REAL OpenMMMartiniProcess
    on a generated POPE bilayer under minimize + NVT); plots the potential energy
    settling to a stable negative value (the cohesion / assembly signal) and the
    area per lipid. The real run needs the ``membrane`` extra (viva-openmm +
    OpenMM); where it is absent the figure DEGRADES CLEANLY to an explanatory
    panel rather than erroring, so the viz stays valid + discoverable everywhere.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Bilayer cohesion — potential energy settling negative"},
        "caption": {"_type": "string", "_default": ""},
        "n_steps": {"_type": "integer", "_default": 8},
        "nx": {"_type": "integer", "_default": 4},
        "ny": {"_type": "integer", "_default": 4},
        "platform": {"_type": "string", "_default": "CPU"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        try:
            from ..core import build_core
            from ..composites.og_31_protometabolism_to_amphiphiles import (
                og_31_protometabolism_to_amphiphiles as gen,
            )
            core = build_core()
            rows = _run(gen, core, self.config["n_steps"],
                        nx=int(self.config["nx"]), ny=int(self.config["ny"]),
                        platform=str(self.config["platform"]))
        except (ImportError, ModuleNotFoundError) as e:
            return {"html": self._unavailable(e)}
        except Exception as e:  # OpenMM platform / viva-openmm runtime gaps degrade too
            if "openmm" in str(e).lower():
                return {"html": self._unavailable(e)}
            raise
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        from plotly.subplots import make_subplots
        from ..composites.og_31_protometabolism_to_amphiphiles import (
            og_31_protometabolism_to_amphiphiles as gen,
        )
        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)], gen)
        apl = _col(rows, "area_per_lipid")
        fig = make_subplots(
            rows=1, cols=2, horizontal_spacing=0.11,
            subplot_titles=("Potential energy (settling negative)", "Area per lipid"),
        )
        fig.add_scatter(x=t, y=_col(rows, "potential_energy"), mode="lines",
                        line=dict(color=TEAL, width=2.5), name="potential energy", row=1, col=1)
        fig.add_hline(y=0.0, line=dict(color=SLATE, width=1, dash="dot"), row=1, col=1)
        fig.add_scatter(x=t, y=apl, mode="lines", line=dict(color=AMBER, width=2.5),
                        name="area per lipid (nm²)", row=1, col=2)
        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor=S.GRID)
        fig.update_yaxes(showgrid=True, gridcolor=S.GRID)
        fig.update_layout(**S.base_layout(
            height=400, showlegend=True,
            legend=dict(orientation="h", y=-0.16, x=0.5, xanchor="center", font=dict(size=10)),
            margin=dict(l=60, r=25, t=46, b=70)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Bilayer cohesion — potential energy settling negative"),
            phase="Study 31", view="Mechanism", tier="mechanistic_prediction",
            caption_prefix="How to read",
            caption_text=(self.config.get("caption") or (
                "Potential energy settling to a stable negative value as the real Martini coarse-grained "
                "POPE bilayer assembles under minimize + NVT, with the equilibrium area per lipid alongside. "
                "Plainly: the membrane snaps into a stable sheet instead of dispersing, and the lipids settle "
                "at the spacing real membranes show.")))

    def _unavailable(self, err) -> str:
        note = (
            '<div style="padding:28px 22px;border:1px dashed ' + S.HAIR + ';border-radius:8px;'
            'background:' + S.PANEL + ';color:' + S.INK_SOFT + ';font-size:13px;line-height:1.5">'
            "This figure renders a <b>real</b> Martini coarse-grained bilayer run "
            "(og_31 → OpenMMMartiniProcess). It requires the <code>membrane</code> extra "
            "(<code>viva-openmm</code> + OpenMM), which is not installed in this environment, so the "
            "live run was skipped rather than faked. Install the extra (a <code>/viva-catalog</code> / "
            "<code>pip install &#39;viva-genesis[membrane]&#39;</code> step) to render the potential-energy "
            "cohesion curve + area-per-lipid from the actual MD."
            f'<div style="margin-top:8px;color:{S.MUTED};font-size:11px">({type(err).__name__}: {str(err)[:140]})</div>'
            "</div>"
        )
        return S.frame(
            note, title=(self.config.get("title") or "Bilayer cohesion — membrane extra required"),
            phase="Study 31", view="Mechanism", tier="mechanistic_prediction", tone="caution",
            caption_prefix="Note",
            caption_text=(
                "The real-run path is guarded: where OpenMM is present this panel is the live PE-settling + "
                "area-per-lipid figure; where it is absent it degrades to this note instead of erroring."))


class OgRtcaAutocatalysisViz(Visualization):
    """og-rtca — branched reductive-TCA: refuted at vent, topology-capable beyond it.

    Reads the committed functional-discriminator artifact
    (``artifacts/rtca_discriminator.json``) — no re-run; that JSON is the
    deterministic study result — and plots the honest negative: (1) the
    self-amplification growth rate across the whole vent feed sweep (x1–x50), zero
    at every feed, so the seeded cycle washes out under vent H2; and (2) that same
    growth rate for real vent vs a LABELLED beyond-vent counterfactual (stronger
    reductant + lower dilution) vs the counterfactual's matched null — the cycle
    ignites only beyond vent, and topology-specifically (the null stays off). So
    the vent negative is a redox / residence-time limitation, not a limitation of
    the rTCA wiring. The coefficient detector reads gain 0 by construction
    (topological autocatalysis, no doubling reaction), which is why a
    coefficient-free functional discriminator is used.
    """

    config_schema = {
        "title": {"_type": "string",
                  "_default": "Reductive-TCA autocatalysis — refuted at vent, topology-capable beyond it"},
        "caption": {"_type": "string", "_default": ""},
        "artifact_json": {"_type": "string",
                          "_default": "workspace/studies/og-rtca-autocatalysis/artifacts/rtca_discriminator.json"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import json
        import os

        path = str(self.config["artifact_json"])
        if not os.path.isabs(path) and not os.path.exists(path):
            alt = os.path.join(os.getcwd(), path)
            if os.path.exists(alt):
                path = alt
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return {"html": self._figure(d)}

    @staticmethod
    def _mu(block) -> float:
        try:
            return float(((block or {}).get("favorable") or {}).get("growth", {}).get("mu_max") or 0.0)
        except Exception:
            return 0.0

    def _figure(self, d) -> str:
        from plotly.subplots import make_subplots

        vent = d.get("vent") or {}
        levels = list(vent.keys())  # x1, x5, x20, x50
        mu_vent = [self._mu(vent[lv]) for lv in levels]
        feed_lab = [f"{lv}<br>(H2 {vent[lv]['feeds']['feed_H2']:g})" for lv in levels]

        pl = (d.get("counterfactual") or {}).get("permissive_limit") or {}
        vent_rep = vent.get("x20") or (vent[levels[-1]] if levels else {})
        cmp_mu = [
            self._mu(vent_rep),
            self._mu(pl),
            float((pl.get("matched_null") or {}).get("growth", {}).get("mu_max") or 0.0),
        ]
        cmp_lab = ["real vent", "permissive<br>counterfactual", "matched null"]
        cmp_col = [SLATE, TEAL, RUST]

        fig = make_subplots(
            rows=1, cols=2, horizontal_spacing=0.135,
            subplot_titles=("Self-amplification across the vent feed sweep",
                            "Topology capable + specific (beyond-vent counterfactual)"))
        fig.add_bar(x=feed_lab, y=mu_vent, marker_color=RUST, showlegend=False, row=1, col=1)
        fig.add_bar(x=cmp_lab, y=cmp_mu, marker_color=cmp_col, showlegend=False, row=1, col=2)
        fig.update_yaxes(title_text="growth rate μ_max (1/s)", showgrid=True,
                         gridcolor=S.GRID, rangemode="tozero")
        fig.update_xaxes(showgrid=False)
        fig.update_layout(**S.base_layout(height=400, showlegend=False,
                                          margin=dict(l=72, r=25, t=54, b=66)))

        return S.frame(
            fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False}),
            title=(self.config.get("title") or "Reductive-TCA autocatalysis — refuted at vent"),
            subtitle=("Vent feasibility refuted — the seeded cycle does not self-amplify at any vent feed; "
                      "it ignites only in a labelled beyond-vent counterfactual, and topology-specifically."),
            phase="Gate A · A2", view="Decision", tier="null_control", tone="caution",
            caption_prefix="How to read",
            caption_text=(self.config.get("caption") or (
                "Left: the self-amplification growth rate across the real-vent feed sweep (x1–x50) — "
                "zero at every feed, so the seeded reductive-TCA cycle washes out and never closes under vent "
                "H2 (the honest negative). Right: the same growth rate for real vent, a labelled "
                "stronger-reductant + lower-dilution counterfactual, and that counterfactual's matched null — "
                "the cycle self-amplifies only beyond vent, and only with its own wiring (the null stays off). "
                "Plainly: the rTCA wiring is capable; the vent redox environment is what refutes it, not the "
                "cycle's topology.")))


# --------------------------------------------------------------------------- #
# og-29 ADDITIVE Decision view — the x1–x50 feed-sweep autocatalysis discriminator.
# Added ALONGSIDE the #98 render set (does not modify it). Reads the committed
# autocatalysis_discriminator.json — no re-run.
# --------------------------------------------------------------------------- #
class OgAutocatalysisDiscriminatorViz(Visualization):
    """og-29 — endogenous autocatalysis refuted (formose-type), the honest negative.

    Reads the committed functional discriminator (``artifacts/autocatalysis_discriminator.json``):
    across the x1–x50 vent-feed sweep the net carbon flux is FEED-DRIVEN (climbs with the feed,
    the network connecting at the x20 ignition point) while the autocatalytic GAIN stays flat at
    ZERO at every feed — carbon is fixed, but production is feed-driven, not self-amplified. So
    autocatalysis is refuted on a coefficient-free functional discriminator (the coefficient
    detector reads 0 by construction for a topological cycle with no doubling reaction)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Autocatalysis discriminator — feed-driven flux, zero self-amplification"},
        "artifact_json": {"_type": "string",
                          "_default": "workspace/studies/og-29-endogenous-autocatalysis/artifacts/autocatalysis_discriminator.json"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import json
        import os
        path = str(self.config["artifact_json"])
        if not os.path.isabs(path) and not os.path.exists(path):
            alt = os.path.join(os.getcwd(), path)
            if os.path.exists(alt):
                path = alt
        if not os.path.exists(path):
            return {"html": S.frame(f'<p style="padding:18px;color:{SLATE}">autocatalysis_discriminator.json not found.</p>',
                                    title="Artifact not available", tone="caution", max_width=900)}
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return {"html": self._figure(d)}

    def _figure(self, d) -> str:
        from plotly.subplots import make_subplots

        fs = d["favorable_sweep"]
        levels = list(fs.keys())                       # x1, x5, x20, x50
        xmul = [float(lv.lstrip("x")) for lv in levels]
        flux = [float(fs[lv]["net_carbon_flux"]) for lv in levels]
        gain = [float(fs[lv]["autocatalytic_gain"]) for lv in levels]
        conn = [float(fs[lv].get("network_connected", 0.0)) for lv in levels]
        hd = d.get("headline", {})
        ign = str(hd.get("ignition_point", "x20")).split()[0]
        ign_x = float(ign.lstrip("x")) if ign.lstrip("x").replace(".", "").isdigit() else 20.0

        fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.13,
                            subplot_titles=("Net carbon flux is FEED-DRIVEN",
                                            "Autocatalytic gain is ZERO at every feed"))
        # P1 — flux climbs with feed; mark the x20 ignition (network connects)
        fig.add_scatter(x=xmul, y=flux, mode="lines+markers", line=dict(color=SLATE, width=2),
                        marker=dict(color=[TEAL if c >= 0.5 else SLATE for c in conn], size=9),
                        name="net carbon flux", row=1, col=1, showlegend=False)
        fig.add_vline(x=ign_x, line=dict(color=AMBER, width=2, dash="dot"), row=1, col=1)
        fig.add_annotation(x=ign_x, y=max(flux), xref="x1", yref="y1", yshift=8, showarrow=False,
                           text=f"ignition {ign} (network connects)", font=S.FONT(10, S.AMBER))
        fig.update_xaxes(title_text="vent feed level (× posterior)", type="log", row=1, col=1)
        fig.update_yaxes(title_text=S.quantity_label("net_carbon_flux", unit="mol/s"), type="log", row=1, col=1)
        # P2 — gain flat at zero: the honest negative
        fig.add_bar(x=[f"×{int(m)}" for m in xmul], y=gain, marker_color=RUST, row=1, col=2,
                    text=[f"{g:.2f}" for g in gain], textposition="outside", showlegend=False)
        fig.add_annotation(x=0.5, y=0.6, xref="x2 domain", yref="y2 domain", showarrow=False,
                           text="autocatalytic gain = 0<br>at every feed → feed-driven,<br>NOT self-amplified",
                           font=S.FONT(11, RUST), align="center")
        fig.update_yaxes(title_text=S.quantity_label("autocatalytic_gain", unit="dimensionless, ratio"),
                         range=[-0.1, 1.0], row=1, col=2)

        fig.update_layout(S.base_layout(height=420))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        cap = (
            f"<b>Left (feed-driven flux):</b> across the vent-feed sweep (x1–x50) the net carbon flux climbs from "
            f"{flux[0]:.1e} to {flux[-1]:.1e} mol/s and the six-carbon network connects at the {ign} ignition point "
            f"(teal marker) — carbon IS fixed, driven by the feed. <b>Right (zero self-amplification):</b> the "
            f"autocatalytic gain is flat at 0 at EVERY feed (RUST) — production is feed-driven, not self-amplified. "
            f"So endogenous autocatalysis is <b>{hd.get('verdict', 'refuted (formose-type)')}</b> on a coefficient-free "
            f"functional discriminator. (The canonical formose doubling r409, 2 glycolaldehyde→threose, is "
            f"condensation-favoured — ΔG° ≈ −16.4 kJ/mol — so its splitting direction carries no net flux.) This is the "
            f"off-spine A2 branch: refuted, not a spine prerequisite; the spine advances on persistence (A1), not "
            f"self-amplification."
        )
        return S.frame(inner, title=(self.config["title"]),
                       phase="Gate A2", view="Decision", tier="mechanistic_prediction",
                       caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1120)


# --------------------------------------------------------------------------- #
# og-rtca ADDITIVE Mechanism view — WHY the branched reductive-TCA cycle washes
# out at the vent (the uphill reductive carboxylations) and why its TOPOLOGY is
# nonetheless autocatalysis-capable under a stronger reductant. Added ALONGSIDE
# the #98 OgRtcaAutocatalysisViz discriminator-bars class (does not modify it).
# --------------------------------------------------------------------------- #
class OgRtcaMechanismViz(Visualization):
    """og-rtca — the mechanism behind the honest negative: the reductive carboxylations are
    uphill under vent H2, so the seeded cycle washes out; but the TOPOLOGY is autocatalysis-
    capable under a stronger reductant (ferredoxin, not H2), and topology-specifically (the
    matched null stays off). Reads the committed rtca_discriminator.json for the vent vs
    permissive-limit growth; the reductive-carboxylation free energies are LABELLED literature
    values (Fuchs/Buckel rTCA thermodynamics), annotated as the mechanism, not a model output."""

    # literature reductive-carboxylation free energies (uphill under H2) — labelled, not model output
    _CARBOX = [("acetyl-CoA → pyruvate", 31.0), ("succinate → α-ketoglutarate", 18.0)]

    config_schema = {
        "title": {"_type": "string", "_default": "Reductive-TCA mechanism — uphill at the vent, topology-capable beyond it"},
        "artifact_json": {"_type": "string",
                          "_default": "workspace/studies/og-rtca-autocatalysis/artifacts/rtca_discriminator.json"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    @staticmethod
    def _mu(block) -> float:
        return float(((block or {}).get("favorable") or {}).get("growth", {}).get("mu_max") or 0.0)

    @staticmethod
    def _mu_null(block) -> float:
        return float(((block or {}).get("matched_null") or {}).get("growth", {}).get("mu_max") or 0.0)

    def update(self, state=None):
        import json
        import os
        path = str(self.config["artifact_json"])
        if not os.path.isabs(path) and not os.path.exists(path):
            alt = os.path.join(os.getcwd(), path)
            if os.path.exists(alt):
                path = alt
        if not os.path.exists(path):
            return {"html": S.frame(f'<p style="padding:18px;color:{SLATE}">rtca_discriminator.json not found.</p>',
                                    title="Artifact not available", tone="caution", max_width=900)}
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return {"html": self._figure(d)}

    def _figure(self, d) -> str:
        from plotly.subplots import make_subplots

        vent = d.get("vent") or {}
        vent_rep = vent.get("x20") or (list(vent.values())[-1] if vent else {})
        pl = (d.get("counterfactual") or {}).get("permissive_limit") or {}
        mu_vent = self._mu(vent_rep); mu_perm = self._mu(pl); mu_null = self._mu_null(pl)

        fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.14,
                            subplot_titles=("Reductive carboxylations are UPHILL (vent H2)",
                                            "Topology IS autocatalysis-capable (beyond vent)"))
        # P1 — the thermodynamic barrier: +ΔG carboxylations under vent H2
        names = [c[0] for c in self._CARBOX]; dG = [c[1] for c in self._CARBOX]
        fig.add_bar(x=names, y=dG, marker_color=RUST, row=1, col=1, showlegend=False,
                    text=[f"+{g:g}" for g in dG], textposition="outside")
        fig.add_hline(y=0.0, line=dict(color=SLATE, width=1), row=1, col=1)
        fig.add_annotation(x=0.5, y=0.92, xref="x domain", yref="y domain", showarrow=False,
                           text="uphill under H2 → the seeded cycle washes out<br>(ferredoxin, not H2, is the real reductant)",
                           font=S.FONT(10, RUST), align="center")
        fig.update_yaxes(title_text="reductive-carboxylation ΔG° (kJ/mol, literature)", row=1, col=1)
        # P2 — vent vs permissive counterfactual vs matched null (topology-specific ignition)
        fig.add_bar(x=["real vent", "permissive<br>counterfactual", "matched<br>null"],
                    y=[mu_vent, mu_perm, mu_null], marker_color=[RUST, TEAL, SLATE], row=1, col=2, showlegend=False,
                    text=[f"{mu_vent:.1e}", f"{mu_perm:.1e}", f"{mu_null:.1e}"], textposition="outside")
        fig.update_yaxes(title_text="self-amplification growth rate μ_max (1/step)", row=1, col=2)

        fig.update_layout(S.base_layout(height=420))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        cap = (
            f"<b>Left (Mechanism):</b> the branched reductive-TCA cycle's reductive carboxylations run UPHILL under "
            f"vent H2 — acetyl-CoA→pyruvate ΔG° ≈ +31 kJ/mol and succinate→α-ketoglutarate ≈ +18 kJ/mol (labelled "
            f"literature values) — so the seeded cycle cannot self-amplify and washes out (μ_max = {mu_vent:.1e} at the "
            f"x20 ignition point). The real reductant is ferredoxin, not H2 — exactly why biological rTCA uses it. "
            f"<b>Right (counterfactual):</b> under a stronger reductant / lower dilution (a LABELLED beyond-vent "
            f"counterfactual, NOT a vent-feasibility claim) the SAME topology ignites exponentially "
            f"(μ_max = {mu_perm:.1e}, TEAL) while its matched null stays off ({mu_null:.1e}, SLATE) — so the cycle is "
            f"topology-specifically autocatalysis-capable. <b>Conclusion:</b> the vent negative ("
            f"{d.get('verdict', 'honest-negative')}) is a redox-environment / thermodynamic limitation, not a flaw in "
            f"the rTCA wiring — the off-spine A2 branch, refuted at the vent but noted as a basis for a beyond-vent follow-up."
        )
        return S.frame(inner, title=(self.config["title"]),
                       phase="Gate A2", view="Mechanism", tier="mechanistic_prediction",
                       caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1120)
