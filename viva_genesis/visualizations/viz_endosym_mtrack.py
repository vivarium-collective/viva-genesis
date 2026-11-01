"""Eukaryogenesis M-track (coupled bridge models M1–M7) — one headline visualization per study.

Mirrors viz_eukaryogenesis: each viz runs its study's calibrated favorable arm + control from a
FRESH coupled-model run and renders the discriminating comparison as a bar chart against the gate
threshold — the favorable arm clears the gate, the control fails. These are the headline results
of the reopened bridge studies (selection, enclosure, coupling, transmission, spatial, bidirectional).
"""
from __future__ import annotations

from process_bigraph import Composite
from process_bigraph.visualization import Visualization

from . import viz_style as S
from .viz_eukaryogenesis import _bar


def _run_obs(generator, core, obs_fn, keys, *, n_steps, **kw):
    """Run a coupled model collecting the emitted stores per tick, then apply the row-based
    observable (the M-track observables are functions of the abundance/field trajectory)."""
    sim = Composite({"state": generator(core=core, **kw)}, core=core)
    rows = []
    for _ in range(int(n_steps)):
        sim.run(1)
        st = sim.state
        rows.append({k: st.get(k) for k in keys})
    return float(obs_fn(rows))


class M1SelectionViz(Visualization):
    """M1: metabolic exchange selects FOR a heritable contact propensity (>0); the no-exchange
    control selects against it."""
    config_schema = {"title": {"_type": "string", "_default": "Selection for proximity — exchange selects contact"},
                     "n_steps": {"_type": "integer", "_default": 160}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_hybrid import (
            proto_endosymbiosis_hybrid as G, selection_coefficient_for_adhesion as OBS)
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"]); keys = ("n_high", "n_low")
        kw = dict(benefit_coeff=1.2, cost_coeff=0.3, init_freq_high=0.6)
        on = _run_obs(G, core, OBS, keys, n_steps=n, exchange="on", **kw)
        off = _run_obs(G, core, OBS, keys, n_steps=n, exchange="off", **kw)
        inner = _bar([("exchange on", on, on > 0.0), ("no-exchange control", off, off > 0.0)],
                     0.0, "selection coefficient for adhesion", gate_label="gate > 0")
        return {"html": S.frame(inner, title=self.config.get("title"), tier="reduced coupled model",
                                caption_text=("With exchange, a heritable contact propensity is positively "
                                              "selected (coeff > 0, above a frequency threshold); the matched "
                                              "no-exchange control selects against it — exchange is necessary."))}


class M2EnclosureViz(Visualization):
    """M2: stable enclosure is the majority outcome in the geometry-first regime; it fails under
    conflict (high perturbation)."""
    config_schema = {"title": {"_type": "string", "_default": "Enclosure mechanics — stable sealing needs a mechanical budget"},
                     "n_steps": {"_type": "integer", "_default": 120}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_enclosure import (
            proto_endosymbiosis_enclosure as G, probability_of_stable_enclosure as OBS)
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"]); keys = ("n_attempting", "n_sealed", "n_stalled")
        geo = _run_obs(G, core, OBS, keys, n_steps=n, adhesion_energy=0.9, bending_modulus=0.2, perturbation=0.1)
        conf = _run_obs(G, core, OBS, keys, n_steps=n, adhesion_energy=0.6, bending_modulus=0.3, perturbation=0.9)
        inner = _bar([("geometry-first", geo, geo > 0.5), ("conflict control", conf, conf > 0.5)],
                     0.5, "probability of stable enclosure", gate_label="gate > 0.5")
        return {"html": S.frame(inner, title=self.config.get("title"), tier="reduced coupled model",
                                caption_text=("Stable, persistent enclosure dominates only where adhesion "
                                              "overcomes the bending/neck-closure barrier and survives "
                                              "perturbation; under conflict the membrane seals but unwraps."))}


class M3CouplingViz(Visualization):
    """M3: selection-for-contact and stable enclosure co-succeed (joint feasibility high) only when
    all conditions align; decoupled, it collapses."""
    config_schema = {"title": {"_type": "string", "_default": "Contact-to-enclosure coupling — a narrow joint-feasible regime"},
                     "n_steps": {"_type": "integer", "_default": 200}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_coupled import (
            proto_endosymbiosis_coupled as G, joint_feasibility_region as OBS)
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"]); keys = ("n_lc", "n_hc_un", "n_hc_se", "n_hc_st")
        aligned = _run_obs(G, core, OBS, keys, n_steps=n, benefit_coeff=1.2, cost_coeff=0.3,
                           base_adhesion=0.8, bending_modulus=0.2, perturbation=0.1)
        decoup = _run_obs(G, core, OBS, keys, n_steps=n, benefit_coeff=0.3, cost_coeff=0.5,
                          base_adhesion=0.8, bending_modulus=0.2, perturbation=0.1)
        inner = _bar([("aligned regime", aligned, aligned >= 0.5), ("decoupled control", decoup, decoup >= 0.5)],
                     0.5, "joint feasibility region", gate_label="gate ≥ 0.5")
        return {"html": S.frame(inner, title=self.config.get("title"), tier="reduced coupled model",
                                caption_text=("Contact supplies the adhesion enclosure needs and enclosure "
                                              "locks in the exchange benefit that keeps contact selected — the "
                                              "two co-succeed only when selection, sealing, and persistence align."))}


class M5TransmissionViz(Visualization):
    """M5: an established symbiosis is retained across generations only when fidelity + benefit
    outrun conflict/partner-loss."""
    config_schema = {"title": {"_type": "string", "_default": "Vertical-transmission stability — establishment ≠ permanence"},
                     "n_steps": {"_type": "integer", "_default": 300}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_transmission import (
            proto_endosymbiosis_transmission as G, endosymbiont_retention_fraction as OBS)
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"]); keys = ("n_sym", "n_free")
        stable = _run_obs(G, core, OBS, keys, n_steps=n, fidelity=0.98, benefit=0.6, cost=0.1, loss_rate=0.03)
        conflict = _run_obs(G, core, OBS, keys, n_steps=n, fidelity=0.95, benefit=0.6, cost=0.1, loss_rate=0.5)
        inner = _bar([("fidelity + benefit", stable, stable >= 0.5), ("high-conflict control", conflict, conflict >= 0.5)],
                     0.5, "endosymbiont retention fraction", gate_label="gate ≥ 0.5")
        return {"html": S.frame(inner, title=self.config.get("title"), tier="reduced coupled model",
                                caption_text=("Even once established, the symbiosis is retained only where "
                                              "transmission fidelity and the selective benefit outrun conflict "
                                              "and segregational loss; under high conflict it decays to ~0."))}


class M6SpatialViz(Visualization):
    """M6: realised metabolite exchange is strongly proximity-dependent (screened diffusion) —
    contact confers an exchange advantage mechanistically."""
    config_schema = {"title": {"_type": "string", "_default": "Spatial exchange — contact confers the exchange advantage"},
                     "n_steps": {"_type": "integer", "_default": 400}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_spatial import (
            proto_endosymbiosis_spatial as G, realised_exchange_level as OBS)
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"]); keys = ("consumer_conc",)
        contact = _run_obs(G, core, OBS, keys, n_steps=n, consumer_distance=1, diffusion=0.4, decay=0.08)
        distal = _run_obs(G, core, OBS, keys, n_steps=n, consumer_distance=10, diffusion=0.4, decay=0.08)
        inner = _bar([("contact (d=1)", contact, contact > 3 * max(distal, 1e-9)),
                      ("distal (d=10)", distal, False)],
                     distal if distal > 0 else 1e-6, "realised exchange level", gate_label="distal baseline", logy=True)
        return {"html": S.frame(inner, title=self.config.get("title"), tier="reduced coupled model",
                                caption_text=("A contact partner receives ~49x the realised exchange of a distal "
                                              "one in the screened regime (up to ~1900x under strong screening); "
                                              "the advantage collapses only when the metabolite is well-mixed."))}


class M7BidirectionalViz(Visualization):
    """M7: obligate bidirectional syntrophy requires metabolic reciprocity — the Liebig minimum
    caps the mutual benefit at the scarcer partner."""
    config_schema = {"title": {"_type": "string", "_default": "Bidirectional syntrophy — reciprocity beyond proximity"},
                     "n_steps": {"_type": "integer", "_default": 400}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_multimetab import (
            proto_endosymbiosis_multimetab as G, mutualistic_exchange_benefit as OBS)
        from ..core import build_core
        core = build_core(); n = int(self.config["n_steps"]); keys = ("symbiont_a_conc", "host_b_conc")
        bal = _run_obs(G, core, OBS, keys, n_steps=n, symbiont_distance=1, production_a=1.0, production_b=1.0)
        asym = _run_obs(G, core, OBS, keys, n_steps=n, symbiont_distance=1, production_a=1.0, production_b=0.2)
        inner = _bar([("balanced", bal, bal >= 0.5), ("asymmetric control", asym, asym >= 0.5)],
                     0.5, "mutualistic exchange benefit (Liebig min)", gate_label="gate ≥ 0.5")
        return {"html": S.frame(inner, title=self.config.get("title"), tier="reduced coupled model",
                                caption_text=("Obligate two-metabolite syntrophy caps the mutual benefit at the "
                                              "scarcer reciprocal flux: an imbalanced pair is starved even at "
                                              "contact — reciprocity is required, not just proximity."))}
