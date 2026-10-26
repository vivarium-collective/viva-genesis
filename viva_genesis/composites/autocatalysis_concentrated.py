"""og-autocatalysis-a2 (Gate-A2 keystone) UNDER thermophoretic pore concentration.

The endogenous-autocatalysis test (``og_29_endogenous_autocatalysis``) was
REFUTED by its matched-null arm: the rule-generated vent-fed network (favorable)
fixes carbon but its self-amplification is NOT separable from a degree-preserving
matched null fed the *identical* input fluxes — at the x20 ignition point the
favorable net carbon flux (5.69e-4) and the null (5.70e-4) are indistinguishable
and the coefficient-gated ``autocatalytic_gain`` is 0 for both. That is the
refutation metric: the **amplification margin over the matched null** (favorable −
null), which read ~0 → feed-driven accumulation, not autocatalysis.

A sibling study showed that for a DIFFERENT refuted coupling (self-maintenance)
connecting the vent pore's SPATIAL CONCENTRATION — the real FiPy Baaske
thermophoretic trap (``ThermophoreticTrapProcess``) — to the loop re-cast the
refutation. This composite applies the same connect-and-close move to
autocatalysis: the trap solves the pore's accumulation column and emits an
``enrichment_factor``; ``PoreEnrichedFeedProcess`` scales the dilute vent CO2/H2
feed by that factor (capped at ``max_enrichment``); and the SAME enriched supply
feeds BOTH the favorable network and its degree-preserving matched null (``input
fluxes held equal`` is preserved — concentration is applied identically to both
arms). ``concentrating=False`` forces the factor to 1 — the matched
non-concentrating control.

The honest question this isolates: autocatalysis is intrinsically non-linear
(rate ∝ [catalyst]·[substrate]), so if the favorable topology is genuinely
self-amplifying it should pull AHEAD of the linear matched null as the feed is
concentrated (a GROWING margin); if production is purely feed-driven, raising the
feed scales both arms equally and the margin stays ~0 — the refutation is about
topology/thermodynamics, not dilution, and spatial concentration cannot rescue
it. The matched null is the discriminator either way.

NEW file (investigation hardening task #4). Does not edit any shared __init__,
study.yaml, investigation.yaml, or transport/__init__.py. The trap and
pore-enriched-feed Process classes are auto-registered by ``build_core`` (they
live in ``viva_genesis.transport`` and are re-exported from its ``__init__``).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .og_29_endogenous_autocatalysis import og_29_endogenous_autocatalysis


@composite_generator(
    name="autocatalysis_concentrated",
    methods=["libRoadRunner reaction-universe engine", "flux-cycle autocatalysis detection",
             "degree-preserving matched null (Gate-A2 arm)",
             "real FiPy Baaske thermophoretic trap (enrichment read from the solved column)",
             "pore-concentrated vent feed (no built-in gain; applied identically to both arms)"],
    fidelity="real",
    description=(
        "Connects the vent pore's spatial-concentration step to the Gate-A2 endogenous-autocatalysis "
        "test. The real FiPy ThermophoreticTrapProcess solves the Baaske accumulation column and emits "
        "an enrichment_factor; PoreEnrichedFeedProcess scales the dilute CO2/H2 vent supply by that "
        "factor (capped at max_enrichment) and writes the pore-local supply the reaction network reads. "
        "The SAME concentrated supply feeds the favorable network (reaction_universe) and, with "
        "matched_null=True, the degree-preserving matched null — so the matched-null comparison keeps "
        "input fluxes held equal under concentration. concentrating=False is the non-concentrating "
        "control (enrichment 1). Tests whether the amplification margin over the matched null (the "
        "metric that refuted og-29) becomes positive under spatial concentration, or whether "
        "feed-driven accumulation still scales both arms equally."
    ),
    parameters={
        "matched_null": {"type": "boolean", "default": False,
                         "description": "Gate-A2 arm: run the degree-preserving null on the SAME (concentrated) supply"},
        "concentrating": {"type": "boolean", "default": True,
                          "description": "Pore concentration on; False is the matched non-concentrating control (enrichment 1)"},
        "base_CO2": {"type": "float", "default": 1.4e-3,
                     "description": "Dilute (bulk) inorganic-carbon feed before pore concentration (M) [Phase-1 posterior]"},
        "base_H2": {"type": "float", "default": 1.08e-2,
                    "description": "Dilute (bulk) H2 feed before pore concentration (M) [Phase-1 posterior]"},
        "max_enrichment": {"type": "float", "default": 50.0,
                           "description": "Cap on the applied enrichment (keeps the concentrated feed physical); the "
                                          "default trap geometry saturates the cap, so this is the effective "
                                          "concentration factor (concentrating=True)"},
        "k_wash": {"type": "float", "default": 0.05,
                   "description": "CSTR washout / dilution rate (1/s)"},
        "max_carbons": {"type": "integer", "default": 6,
                        "description": "Carbon cap of the generated reaction universe (6 = the formose-arm C6 ignition regime)"},
        "null_seed": {"type": "integer", "default": 0,
                      "description": "Null-network draw (matched_null only)"},
        "delta_T": {"type": "float", "default": 30.0,
                    "description": "Cross-pore temperature difference (K); Baaske-favorable ~30"},
        "pore_length": {"type": "float", "default": 5.0e-3,
                        "description": "Accumulation-column length (m); enrichment exponential in this"},
        "pore_flow": {"type": "float", "default": 1.0e-4,
                      "description": "Buoyant convective flow in the pore (m/s)"},
        "porosity": {"type": "float", "default": 0.3,
                     "description": "Pore porosity/openness (0-1; lower = more confinement = more trapping)"},
        "soret_coeff": {"type": "float", "default": 0.10,
                        "description": "Amphiphile/solute Soret coefficient (1/K)"},
    },
    default_n_steps=120,
    preferred_time="24 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["flux/net_carbon_flux", "flux/autocatalytic_gain", "flux/network_connected",
                         "supply/CO2", "supply/H2", "supply/effective_enrichment",
                         "pore/enrichment_factor", "stats/n_autocatalytic_motifs"]}],
)
def autocatalysis_concentrated(core=None, *, matched_null=False, concentrating=True,
                               base_CO2=1.4e-3, base_H2=1.08e-2, max_enrichment=50.0,
                               k_wash=0.05, max_carbons=6, null_seed=0,
                               delta_T=30.0, pore_length=5.0e-3, pore_flow=1.0e-4,
                               porosity=0.3, soret_coeff=0.10):
    if core is None:
        core = build_core()

    # Reuse the Gate-A2 endogenous-autocatalysis network (favorable or matched
    # null), which already reads its carbon/H2 feed from a ``supply`` store.
    doc = og_29_endogenous_autocatalysis(
        core, supply_H2=base_H2, supply_CO2=base_CO2, k_wash=k_wash,
        max_carbons=max_carbons, matched_null=matched_null, null_seed=null_seed)

    # The network reads feed_CO2/feed_H2 from ["supply", "CO2"/"H2"]. Re-cast the
    # supply as the OUTPUT of a pore-enrichment chain rather than static floats:
    # the real FiPy trap solves the accumulation column -> enrichment_factor, and
    # PoreEnrichedFeedProcess scales the dilute base feed by it into the supply.
    doc["supply"]["effective_enrichment"] = 1.0
    doc["pore"] = {"temperature": 333.15, "flow_velocity": float(pore_flow), "porosity": float(porosity),
                   "enrichment_factor": 1.0, "residence_time": 0.0, "accumulation_peclet": 0.0,
                   "flux_divergence_residual": 0.0}

    doc["trap"] = {
        "_type": "process",
        "address": "local:ThermophoreticTrapProcess",
        "config": {"pore_length": float(pore_length), "delta_T": float(delta_T),
                   "soret_coeff": float(soret_coeff)},
        "interval": 1.0,
        "inputs": {"temperature": ["pore", "temperature"], "flow_velocity": ["pore", "flow_velocity"],
                   "porosity": ["pore", "porosity"]},
        "outputs": {"enrichment_factor": ["pore", "enrichment_factor"],
                    "residence_time": ["pore", "residence_time"],
                    "accumulation_peclet": ["pore", "accumulation_peclet"],
                    "flux_divergence_residual": ["pore", "flux_divergence_residual"]},
    }
    doc["concentrate"] = {
        "_type": "process",
        "address": "local:PoreEnrichedFeedProcess",
        "config": {"base_CO2": float(base_CO2), "base_H2": float(base_H2),
                   "concentrating": bool(concentrating), "max_enrichment": float(max_enrichment)},
        "interval": 1.0,
        "inputs": {"enrichment_factor": ["pore", "enrichment_factor"]},
        "outputs": {"CO2": ["supply", "CO2"], "H2": ["supply", "H2"],
                    "effective_enrichment": ["supply", "effective_enrichment"]},
    }

    # Surface the concentration on the record.
    doc["emitter"]["config"]["emit"]["effective_enrichment"] = "float"
    doc["emitter"]["config"]["emit"]["enrichment_factor"] = "float"
    doc["emitter"]["inputs"]["effective_enrichment"] = ["supply", "effective_enrichment"]
    doc["emitter"]["inputs"]["enrichment_factor"] = ["pore", "enrichment_factor"]
    return doc
