"""Study og-rtca-autocatalysis — is the CANONICAL reductive-TCA cycle viable and
self-amplifying under vent conditions? (Gate A, branched-skeleton v2.)

og-29 refuted *formose-type* autocatalysis (linear C≤6) with mechanism. rTCA is
the other candidate, and its branched C6 intermediates (citrate / isocitrate /
cis-aconitate) are outside the linear-skeleton universe — so this study runs the
**curated mechanistic** rTCA network
(:func:`viva_genesis.protometabolism.rtca.build_rtca_universe`) on the same real
libRoadRunner engine, feeds and ledger as the rest of Phase 3.

**Guardrail (read before quoting a result).** A curated rTCA network CANNOT test
whether autocatalysis *emerges* — the cycle is hand-coded, present by
construction (that was the formose/rule-generated question, refuted). It tests
(a) **feasibility** — does the known cycle turn over and self-amplify under vent
feeds? and (b) **topology-specificity** — does its wiring self-amplify beyond a
degree-preserving matched null? A positive means "the canonical rTCA cycle IS
viable + self-amplifying under vent conditions," never "autocatalysis emerges".
Its autocatalysis is *topological* (the citrate→OAA+acetate lyase branch, every
step 1:1, no coefficient-2 reaction), so the coefficient-gated
``autocatalytic_gain`` detector reads 0 by construction — the study is graded by
the coefficient-independent functional discriminator
(:mod:`viva_genesis.protometabolism.functional_autocatalysis`), not by that gain.

This composite is the single-network baseline (a vent-fed run of the rTCA
reactor, with a ``matched_null`` toggle and a labelled ``carboxylation_drive_kj``
counterfactual); the full seed-dependence / ignition-sweep discriminator across
both arms lives in ``sims/compute_rtca_discriminator.py``.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .open_chemical_network import _SPECIES_PORTS, _LEDGER_PORTS, _EMIT_PATHS, _WIRES

_FEED_CO2, _FEED_H2 = 2.0e-3, 1.0e-3


@composite_generator(
    name="og_rtca_autocatalysis",
    methods=["libRoadRunner/Tellurium SBML ODE", "curated mechanistic reductive-TCA network",
             "eQuilibrator component-contribution dG'", "functional (seed-dependence) autocatalysis discriminator",
             "degree-preserving matched null"],
    fidelity="real",
    description=(
        "Curated MECHANISTIC reductive-TCA cycle (9 elementary steps incl. the citrate lyase "
        "branch; branched C6 intermediates citrate/isocitrate/cis-aconitate with eQuilibrator dG'; "
        "acetate as the acetyl-CoA surrogate; fumarate lumped) on the real libRoadRunner engine under "
        "vent CO2/H2 feed + washout. Its autocatalysis is topological (no coefficient-2 reaction), so "
        "the coefficient-gated autocatalytic_gain reads 0 by construction; feasibility + topology-"
        "specificity are graded by the coefficient-independent functional discriminator. matched_null "
        "swaps the degree-preserving null; carboxylation_drive_kj is a labelled stronger-reductant "
        "counterfactual (0 = real vent H2) that separates topology from thermodynamics."
    ),
    parameters={
        "supply_H2": {"type": "float", "default": _FEED_H2,
                      "description": "Vent H2 supply (molar) [27->rtca handoff]"},
        "supply_CO2": {"type": "float", "default": _FEED_CO2,
                       "description": "Vent inorganic-carbon supply (molar) [27->rtca handoff]"},
        "k_wash": {"type": "float", "default": 0.02,
                   "description": "CSTR washout / dilution rate (1/s) — the critical-dilution knob"},
        "matched_null": {"type": "boolean", "default": False,
                         "description": "Topology-specificity arm: degree-preserving null on the same feed"},
        "null_seed": {"type": "integer", "default": 0, "description": "Null-network draw (matched_null only)"},
        "carboxylation_drive_kj": {"type": "float", "default": 0.0,
                                   "description": "Labelled counterfactual: kJ/mol subtracted from each reductive "
                                                  "carboxylation dG' (stronger reductant than H2). 0 = real vent."},
    },
    default_n_steps=200,
    preferred_time="12 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def og_rtca_autocatalysis(core=None, *, supply_H2=_FEED_H2, supply_CO2=_FEED_CO2, k_wash=0.02,
                          matched_null=False, null_seed=0, carboxylation_drive_kj=0.0):
    if core is None:
        core = build_core()
    address = "local:RTCANullProcess" if matched_null else "local:RTCANetworkProcess"
    config = {"k_wash": float(k_wash), "carboxylation_drive_kj": float(carboxylation_drive_kj)}
    if matched_null:
        config["null_seed"] = int(null_seed)
    inputs = {"feed_CO2": ["feed", "CO2"], "feed_H2": ["feed", "H2"], "feed_pyruvate": ["feed", "pyruvate"],
              "feed_formaldehyde": ["feed", "formaldehyde"], "feed_formate": ["feed", "formate"],
              "feed_acetate": ["feed", "acetate"]}
    outputs = {**{p: ["flux", p] for p in ("net_carbon_flux", "autocatalytic_gain", "network_connected")},
               **{p: ["net", p] for p in _SPECIES_PORTS + ("total_organic_carbon",)},
               **{p: ["stats", p] for p in ("n_persistent_species", "n_autocatalytic_motifs",
                                            "autocatalytic_core_size", "catalyst_saturation")},
               **{p: ["witness", p] for p in ("dissipation", "element_residual", "carbon_residual")}}
    return {
        "network": {"_type": "process", "address": address, "config": config, "interval": 1.0,
                    "inputs": inputs, "outputs": outputs},
        "network_ledger": {
            "_type": "process", "address": "local:NetworkLedgerProcess", "config": {}, "interval": 1.0,
            "inputs": {"element_residual": ["witness", "element_residual"],
                       "carbon_residual": ["witness", "carbon_residual"],
                       "dissipation": ["witness", "dissipation"],
                       "total_organic_carbon": ["net", "total_organic_carbon"]},
            "outputs": {p: ["ledger", p] for p in _LEDGER_PORTS}},
        "feed": {"CO2": float(supply_CO2), "H2": float(supply_H2), "pyruvate": 0.0,
                 "formaldehyde": 0.0, "formate": 0.0, "acetate": 0.0},
        "flux": {"net_carbon_flux": 0.0, "autocatalytic_gain": 0.0, "network_connected": 0.0},
        "net": {**{p: 0.0 for p in _SPECIES_PORTS}, "total_organic_carbon": 0.0},
        "stats": {"n_persistent_species": 0.0, "n_autocatalytic_motifs": 0.0,
                  "autocatalytic_core_size": 0.0, "catalyst_saturation": 0.0},
        "witness": {"dissipation": 0.0, "element_residual": 0.0, "carbon_residual": 0.0},
        "ledger": {"element_residual_max": 0.0, "carbon_residual_max": 0.0, "dissipation_min": 0.0,
                   "dissipated_energy": 0.0, "free_energy_directionality": 1.0, "ledger_ok": 1.0},
        "emitter": {"_type": "step", "address": "local:RAMEmitter",
                    "config": {"emit": {k: "float" for k in _WIRES}},
                    "inputs": {k: list(v) for k, v in _WIRES.items()}},
    }
