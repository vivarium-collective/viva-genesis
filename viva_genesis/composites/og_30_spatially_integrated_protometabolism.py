"""Study 30 — Spatially Integrated Protometabolism (network in a pore vs controls).

Can the full chemical network operate in a pore despite fractionation and washout?
Reuses study-16's ``open_chemical_network`` (real libRoadRunner reaction universe +
autocatalysis detector + k_wash washout) and couples it to the real FiPy
thermophoretic trap (``ThermophoreticTrapProcess``): the trap concentrates the
dilute precursor feed by an ``enrichment_factor``, ``PoreEnrichedFeedProcess``
scales the base feed by it, and the enriched pore-local feed drives the network.

Decision test: productive flux (net_carbon_flux) in the concentrating pore must
EXCEED the matched nonconcentrating control — set ``concentrating=False`` to run
that control arm (feed held at base, enrichment forced to 1) with everything else
equal. Outputs: co-localization (enrichment), spatial reaction flux
(net_carbon_flux), residence (residence_time) and persistence.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .open_chemical_network import open_chemical_network


@composite_generator(
    name="og_30_spatially_integrated_protometabolism",
    methods=["FiPy thermophoretic trap (Soret concentration)", "libRoadRunner reaction universe",
             "pore-enriched feed coupling", "matched nonconcentrating control"],
    fidelity="real",
    description=(
        "Study 30: the reaction network operating IN A PORE. The real FiPy thermophoretic "
        "trap concentrates the precursor feed (enrichment_factor); the enriched pore-local "
        "feed drives open_chemical_network's real reaction universe. concentrating=False runs "
        "the matched nonconcentrating control (feed at base, everything else equal) so the "
        "decision test — productive flux in the pore exceeds the control — is a direct "
        "comparison. Reports co-localization, spatial reaction flux, residence, persistence."
    ),
    parameters={
        "concentrating": {"type": "boolean", "default": True,
                          "description": "Pore (True) vs matched nonconcentrating control (False)"},
        "base_CO2": {"type": "float", "default": 1.0e-3,
                     "description": "Bulk precursor CO2 before pore concentration (molar)"},
        "base_H2": {"type": "float", "default": 1.0e-3,
                    "description": "Bulk precursor H2 before pore concentration (molar)"},
        "temperature": {"type": "float", "default": 333.15,
                        "description": "Pore temperature (K)"},
        "flow_velocity": {"type": "float", "default": 1.0e-4,
                          "description": "Convective flow through the pore (m/s); 0 = no-trap control"},
        "porosity": {"type": "float", "default": 0.3,
                     "description": "Pore openness (0-1); ~1 = open-pore (wash-through) control"},
        "delta_T": {"type": "float", "default": 30.0,
                    "description": "Thermal gradient across the pore (K) driving the Soret trap"},
        "k_wash": {"type": "float", "default": 0.05,
                   "description": "CSTR washout / dilution rate (1/s)"},
        "max_carbons": {"type": "integer", "default": 4,
                        "description": "Carbon cap of the reaction universe"},
    },
    default_n_steps=120,
    preferred_time="6 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["flux/net_carbon_flux", "flux/autocatalytic_gain",
                         "trap/enrichment_factor", "pore/effective_enrichment",
                         "trap/residence_time", "feed/CO2", "ledger/ledger_ok"]}],
)
def og_30_spatially_integrated_protometabolism(
        core=None, *, concentrating=True, base_CO2=1.0e-3, base_H2=1.0e-3,
        temperature=333.15, flow_velocity=1.0e-4, porosity=0.3, delta_T=30.0,
        k_wash=0.05, max_carbons=4):
    if core is None:
        core = build_core()

    # Reuse the real reaction-universe network (+ autocatalysis detector + ledger).
    doc = open_chemical_network(core, model_proto_metabolism="reaction_universe",
                                k_wash=k_wash, max_carbons=max_carbons)

    # The network's carbon + H2 feed now comes from the pore-enriched feed store.
    doc["network"]["inputs"]["feed_CO2"] = ["feed", "CO2"]
    doc["network"]["inputs"]["feed_H2"] = ["feed", "H2"]

    # Real FiPy thermophoretic trap: pore conditions -> enrichment_factor.
    doc["trap_process"] = {
        "_type": "process",
        "address": "local:ThermophoreticTrapProcess",
        "config": {"delta_T": float(delta_T)},
        "interval": 1.0,
        "inputs": {"temperature": ["env", "temperature"],
                   "flow_velocity": ["env", "flow_velocity"],
                   "porosity": ["env", "porosity"]},
        "outputs": {"enrichment_factor": ["trap", "enrichment_factor"],
                    "residence_time": ["trap", "residence_time"],
                    "accumulation_peclet": ["trap", "accumulation_peclet"]},
    }

    # Scale the base feed by the enrichment (or hold at base for the control).
    doc["feed_adapter"] = {
        "_type": "process",
        "address": "local:PoreEnrichedFeedProcess",
        "config": {"base_CO2": float(base_CO2), "base_H2": float(base_H2),
                   "concentrating": bool(concentrating)},
        "interval": 1.0,
        "inputs": {"enrichment_factor": ["trap", "enrichment_factor"]},
        "outputs": {"CO2": ["feed", "CO2"], "H2": ["feed", "H2"],
                    "effective_enrichment": ["pore", "effective_enrichment"]},
    }

    doc["env"] = {"temperature": float(temperature), "flow_velocity": float(flow_velocity),
                  "porosity": float(porosity)}
    doc["trap"] = {"enrichment_factor": 1.0, "residence_time": 0.0, "accumulation_peclet": 0.0}
    doc["pore"] = {"effective_enrichment": 1.0}

    # Extend the emitter with the spatial-coupling observables.
    extra_types = {"enrichment_factor": "float", "effective_enrichment": "float",
                   "residence_time": "float", "feed_CO2": "float"}
    extra_wires = {"enrichment_factor": ["trap", "enrichment_factor"],
                   "effective_enrichment": ["pore", "effective_enrichment"],
                   "residence_time": ["trap", "residence_time"],
                   "feed_CO2": ["feed", "CO2"]}
    doc["emitter"]["config"]["emit"].update(extra_types)
    doc["emitter"]["inputs"].update(extra_wires)

    return doc
