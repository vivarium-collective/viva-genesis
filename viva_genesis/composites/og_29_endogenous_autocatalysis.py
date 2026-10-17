"""Study 29 — Endogenous Autocatalysis (can VENT-FED chemistry self-amplify?).

Study 16's ``open_chemical_network`` already has the science — the real
libRoadRunner reaction-universe engine, the flux-carrying-cycle autocatalysis
detector (``autocatalytic_gain`` > 1), net carbon fixation, the ``k_wash``
critical-dilution knob, and a degree-preserving ``null_network`` matched null.
What study 29 adds is the word *endogenous*: the network is fed from the UPSTREAM
geochemical supply (the 27->29 handoff — H2 + inorganic carbon the evolving vent
interface produces), not a prescribed external feed. So this composite REUSES
``open_chemical_network`` and re-points its carbon/H2 feed to a ``supply`` store a
sibling (or the composed og-27 world) writes, and exposes a ``matched_null``
toggle that swaps in the degree-preserving null on the SAME supply — the Gate A
(27+28+29) comparison arm with chemical input fluxes held equal.

Decision test: detect genuine balanced autocatalysis on the endogenous supply, or
identify the missing precursor/mechanism; the autocatalysis must beat the matched
null at equal supply (a clean no-amplification result is reported, not tuned away).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .open_chemical_network import open_chemical_network


@composite_generator(
    name="og_29_endogenous_autocatalysis",
    methods=["libRoadRunner reaction-universe engine", "flux-cycle autocatalysis detection",
             "critical-dilution sweep", "degree-preserving matched null (Gate A arm)"],
    fidelity="real",
    description=(
        "Study 29: is vent-fed chemistry self-amplifying? Reuses open_chemical_network's real "
        "reaction-universe engine + autocatalysis detector, but feeds the network from the "
        "ENDOGENOUS 27->29 supply (H2 + inorganic carbon from the evolving geochemical "
        "interface) rather than a prescribed feed. matched_null swaps the degree-preserving "
        "null on the same supply for the Gate A comparison (chemical input fluxes held equal). "
        "Reports amplification (autocatalytic_gain), net carbon fixation, intermediate turnover "
        "and the critical dilution (k_wash) at which the loop washes out."
    ),
    parameters={
        # The 27->29 endogenous supply bundle (defaults are the geochemical
        # supply levels; a composed og-27 world / sibling can write these).
        "supply_H2": {"type": "float", "default": 1.0e-3,
                      "description": "Endogenous H2 supply from the vent interface (molar) [27->29 handoff]"},
        "supply_CO2": {"type": "float", "default": 2.0e-3,
                       "description": "Endogenous inorganic-carbon supply (molar) [27->29 handoff]"},
        "k_wash": {"type": "float", "default": 0.05,
                   "description": "CSTR washout / dilution rate (1/s) — the critical-dilution knob"},
        "max_carbons": {"type": "integer", "default": 4,
                        "description": "Carbon cap of the generated reaction universe"},
        "matched_null": {"type": "boolean", "default": False,
                         "description": "Gate A arm: run the degree-preserving null on the SAME supply"},
        "null_seed": {"type": "integer", "default": 0,
                      "description": "Null-network draw (matched_null only)"},
    },
    default_n_steps=120,
    preferred_time="6 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["flux/net_carbon_flux", "flux/autocatalytic_gain", "flux/network_connected",
                         "supply/H2", "supply/CO2", "ledger/ledger_ok"]}],
)
def og_29_endogenous_autocatalysis(core=None, *, supply_H2=1.0e-3, supply_CO2=2.0e-3,
                                   k_wash=0.05, max_carbons=4, matched_null=False, null_seed=0):
    if core is None:
        core = build_core()

    model = "null_network" if matched_null else "reaction_universe"
    # Reuse study-16's full real engine + autocatalysis detector + ledger.
    doc = open_chemical_network(core, model_proto_metabolism=model,
                                k_wash=k_wash, max_carbons=max_carbons, null_seed=null_seed)

    # Make it ENDOGENOUS: feed the network's carbon + H2 from the upstream supply
    # store (the 27->29 handoff), not the prescribed open-network feed constants.
    doc["network"]["inputs"]["feed_CO2"] = ["supply", "CO2"]
    doc["network"]["inputs"]["feed_H2"] = ["supply", "H2"]
    doc["supply"] = {"H2": float(supply_H2), "CO2": float(supply_CO2)}

    # Surface the supply in the emitter so the endogenous feed is on the record.
    doc["emitter"]["config"]["emit"]["supply_H2"] = "float"
    doc["emitter"]["config"]["emit"]["supply_CO2"] = "float"
    doc["emitter"]["inputs"]["supply_H2"] = ["supply", "H2"]
    doc["emitter"]["inputs"]["supply_CO2"] = ["supply", "CO2"]

    return doc
