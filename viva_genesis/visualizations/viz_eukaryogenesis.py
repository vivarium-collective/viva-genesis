"""Eukaryogenesis (From Symbiosis to Complexity) — one headline visualization per bridge study.

Each viz runs its study's calibrated arms from a FRESH composite run (no persisted artifact
needed) and renders the discriminating comparison as a bar chart against the gate threshold:
the favorable arm clears the gate, the control(s) fail. This is the headline result of each study
— a mechanistically plausible route and a well-characterized failure route — made visible.
"""
from __future__ import annotations

import plotly.graph_objects as go
from process_bigraph import Composite
from process_bigraph.visualization import Visualization

from . import viz_style as S
from .viz_style import AMBER as _AMBER
from .viz_style import SLATE as _SLATE
from .viz_style import TEAL as _TEAL


def _bar(arms, threshold, ylabel, *, gate_label, logy=False):
    """arms: list of (label, value, is_favorable). Favorable arms teal, controls slate; a dashed
    amber line marks the gate threshold."""
    labels = [a[0] for a in arms]
    vals = [a[1] for a in arms]
    colors = [_TEAL if a[2] else _SLATE for a in arms]
    fig = go.Figure(go.Bar(x=labels, y=vals, marker_color=colors,
                           text=[f"{v:.3g}" for v in vals], textposition="outside"))
    fig.add_hline(y=threshold, line=dict(color=_AMBER, width=2, dash="dash"),
                  annotation_text=gate_label, annotation_position="top left")
    fig.update_layout(**S.base_layout(height=420, width=720, margin=dict(l=70, r=30, t=46, b=70)))
    fig.update_yaxes(title=ylabel, type="log" if logy else "linear")
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


def _run_state(generator, core, group, obs, *, n_steps, **kw):
    sim = Composite({"state": generator(core=core, **kw)}, core=core)
    sim.run(float(n_steps))
    return float((sim.state.get(group) or {}).get(obs, 0.0))


class S1MetabolicPartnershipViz(Visualization):
    """S1: the connected cross-feeding community develops functional redundancy (>0.5) that the
    isolated (no-exchange) control does not — a partner-dependent advantage."""
    config_schema = {"title": {"_type": "string", "_default": "S1 — a partner-dependent advantage"},
                     "n_steps": {"_type": "integer", "_default": 250}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.metabolite_exchange_community import (
            metabolite_exchange_community as G,
        )
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"])
        kw = dict(lineages="fixer:4,reducer:4", model_proto_ecology="reaction_universe",
                  p_diacid=1.0e-8, p_monoacid=1.0e-7, k_wash=0.01)
        conn = _run_state(G, core, "community", "metacommunity_robustness", n_steps=n, coupling="shared", **kw)
        iso = _run_state(G, core, "community", "metacommunity_robustness", n_steps=n, coupling="private", **kw)
        inner = _bar([("connected (shared)", conn, conn > 0.5), ("isolated control (private)", iso, iso > 0.5)],
                     0.5, "settled metacommunity robustness", gate_label="gate > 0.5")
        return {"html": S.frame(inner, title=self.config.get("title") or "S1", tier="first fidelity",
                                caption_text=("The connected community develops functional redundancy "
                                              "(cross-feeding fills in capabilities) while the isolated control "
                                              "cannot — the partner dependence IS the gap between the arms."))}


class S2EcologyProximityViz(Visualization):
    """S2: at low diffusion a proximate (mixed) community sustains cross-lineage flux a distant
    (segregated) one loses — selection for proximity."""
    config_schema = {"title": {"_type": "string", "_default": "S2 — proximity selects for contact"},
                     "n_steps": {"_type": "integer", "_default": 250}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.metabolite_exchange_community import (
            metabolite_exchange_community as G,
        )
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"])
        kw = dict(lineages="fixer:4,reducer:4", model_proto_ecology="reaction_universe",
                  p_diacid=1.0e-8, p_monoacid=1.0e-7, k_wash=0.01, k_diffusion=0.001)
        mixed = _run_state(G, core, "exchange", "cross_lineage_flux_total", n_steps=n, coupling="shared", placement="mixed", **kw)
        seg = _run_state(G, core, "exchange", "cross_lineage_flux_total", n_steps=n, coupling="shared", placement="segregated", **kw)
        inner = _bar([("proximate (mixed)", mixed, mixed > 1e-22), ("distant control (segregated)", seg, seg > 1e-22)],
                     1e-22, "cross-lineage flux (mol/tick)", gate_label="gate > 1e-22", logy=True)
        return {"html": S.frame(inner, title=self.config.get("title") or "S2", tier="first fidelity",
                                caption_text=("At low diffusion the proximate community sustains ~20x the "
                                              "cross-feeding flux of the distant one; the advantage vanishes "
                                              "well-mixed — proximity selection is a spatial-structure effect."))}


class S3EnclosureViz(Visualization):
    """S3: classical engulfment and inside-out wrapping reach stable enclosure; a no-enclosure
    and a weak-adhesion control do not."""
    config_schema = {"title": {"_type": "string", "_default": "S3 — enclosure is geometrically feasible"},
                     "n_steps": {"_type": "integer", "_default": 30}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.protrusion_enclosure import protrusion_enclosure as G
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"])
        def p(**kw): return _run_state(G, core, "enc", "enclosure_probability", n_steps=n, **kw)
        arms = [("classical engulfment", p(topology="classical_engulfment"), True),
                ("inside-out wrapping", p(topology="inside_out"), True),
                ("no-enclosure control", p(topology="no_enclosure"), False),
                ("weak-adhesion control", p(adhesion_energy_kT=300.0), False)]
        arms = [(lbl, v, v > 0.5) for lbl, v, _ in arms]
        inner = _bar(arms, 0.5, "enclosure probability", gate_label="gate > 0.5")
        return {"html": S.frame(inner, title=self.config.get("title") or "S3", tier="first fidelity",
                                caption_text=("At least one topology reaches stable enclosure over a majority "
                                              "of the partner-size range; controls fail. Physical enclosure is a "
                                              "separate hurdle from metabolic benefit."))}


class S4EnergeticCouplingViz(Visualization):
    """S4: with an efficient pump the population internalizes gradient generation and survives;
    a weak pump collapses — internalization pays only in a restricted regime."""
    config_schema = {"title": {"_type": "string", "_default": "S4 — internalization pays only with an efficient pump"},
                     "n_steps": {"_type": "integer", "_default": 60}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.bioenergetic_internalization import (
            bioenergetic_internalization as G,
        )
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"])
        fav = _run_state(G, core, "pop", "survivors", n_steps=n, catalyst_efficiency=1.0)
        weak = _run_state(G, core, "pop", "survivors", n_steps=n, catalyst_efficiency=0.3)
        inner = _bar([("efficient pump", fav, fav > 0.5), ("weak-pump control", weak, weak > 0.5)],
                     0.5, "surviving fraction (declining gradient)", gate_label="gate > 0.5")
        return {"html": S.frame(inner, title=self.config.get("title") or "S4", tier="first fidelity",
                                caption_text=("An efficient pump internalizes gradient generation and persists "
                                              "as the external gradient collapses; a weak pump cannot pay the "
                                              "Sojo membrane cost and collapses."))}


class S5HeritabilityViz(Visualization):
    """S5: high-fidelity template inheritance crosses the Eigen error threshold and persists; a
    low-fidelity template collapses and a non-heritable control transmits nothing."""
    config_schema = {"title": {"_type": "string", "_default": "S5 — heritable integration needs high fidelity"},
                     "n_steps": {"_type": "integer", "_default": 60}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.heredity_lineage import heredity_lineage_comparison as G
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"])
        hi = _run_state(G, core, "herd", "heritability", n_steps=n, module="template", per_site_fidelity=0.99)
        lo = _run_state(G, core, "herd", "heritability", n_steps=n, module="template", per_site_fidelity=0.80)
        nh = _run_state(G, core, "herd", "heritability", n_steps=n, module="non-heritable", per_site_fidelity=0.99)
        inner = _bar([("high-fidelity template", hi, hi > 0.95), ("low-fidelity (Eigen collapse)", lo, lo > 0.95),
                      ("non-heritable control", nh, nh > 0.95)],
                     0.95, "settled heritability", gate_label="gate > 0.95")
        return {"html": S.frame(inner, title=self.config.get("title") or "S5", tier="first fidelity",
                                caption_text=("Heritable integration — a new evolutionary individual — emerges "
                                              "only above the fidelity threshold; a low-fidelity template hits the "
                                              "Eigen error catastrophe and a non-heritable mechanism transmits nothing."))}
