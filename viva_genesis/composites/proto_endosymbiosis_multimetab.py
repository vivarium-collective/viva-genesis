"""proto_endosymbiosis_multimetab — coupled bridge model (M7: bidirectional stoichiometry).

Measures ``mutualistic_exchange_benefit`` — the Liebig-limited minimum of the two reciprocally
exchanged metabolite fluxes — for study-bidirectional-syntrophy. See
``viva_genesis.endosymbiosis_multimetab.MultiMetaboliteExchangeProcess``. Comparing contact
vs distal gives the (steeper) proximity dependence of obligate mutualism; comparing symmetric
vs asymmetric production exposes its stoichiometric fragility.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from ..endosymbiosis_multimetab import MultiMetaboliteExchangeProcess  # registered via build_core


def _settled(rows, key, frac=0.2):
    n = max(1, int(round(len(rows) * frac)))
    t = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    t = [x for x in t if x == x]
    return sum(t) / len(t) if t else float("nan")


@composite_generator(
    name="proto_endosymbiosis_multimetab",
    emitters=[{"address": "local:SQLiteEmitter",
               "paths": ["global_time", "symbiont_a_conc", "host_b_conc"]}],
    parameters={
        "n_cells": {"type": "integer", "default": 16, "description": "1-D grid length"},
        "diffusion": {"type": "float", "default": 0.4, "description": "diffusion coefficient D"},
        "decay": {"type": "float", "default": 0.08, "description": "decay rate k"},
        "production_a": {"type": "float", "default": 1.0, "description": "host output of metabolite A"},
        "production_b": {"type": "float", "default": 1.0, "description": "symbiont output of metabolite B"},
        "uptake": {"type": "float", "default": 0.2, "description": "uptake rate at each consumer"},
        "symbiont_distance": {"type": "integer", "default": 1, "description": "symbiont cell distance from host"},
        "seed": {"type": "integer", "default": 1, "description": "random seed"},
    },
    description="Coupled bridge model M7: obligate bidirectional (two-metabolite, Liebig) "
                "syntrophy — mutualistic exchange benefit vs distance and production symmetry.",
)
def proto_endosymbiosis_multimetab(core=None, *, n_cells=16, diffusion=0.4, decay=0.08,
                                   production_a=1.0, production_b=1.0, uptake=0.2,
                                   symbiont_distance=1, seed=1):
    if core is None:
        core = build_core()
    if "MultiMetaboliteExchangeProcess" not in core.link_registry:
        core.register_link("MultiMetaboliteExchangeProcess", MultiMetaboliteExchangeProcess)
    n = int(n_cells)
    return {
        "exchange": {
            "_type": "process", "address": "local:MultiMetaboliteExchangeProcess", "interval": 1.0,
            "config": {"n_cells": n, "diffusion": float(diffusion), "decay": float(decay),
                       "production_a": float(production_a), "production_b": float(production_b),
                       "uptake": float(uptake), "symbiont_distance": int(symbiont_distance)},
            "inputs": {"conc_a": ["conc_a"], "conc_b": ["conc_b"],
                       "symbiont_a_conc": ["symbiont_a_conc"], "host_b_conc": ["host_b_conc"]},
            "outputs": {"conc_a": ["conc_a"], "conc_b": ["conc_b"],
                        "symbiont_a_conc": ["symbiont_a_conc"], "host_b_conc": ["host_b_conc"]},
        },
        "conc_a": {str(i): 0.0 for i in range(n)},
        "conc_b": {str(i): 0.0 for i in range(n)},
        "symbiont_a_conc": 0.0, "host_b_conc": 0.0,
    }


def mutualistic_exchange_benefit(rows) -> float:
    """Liebig-limited realised mutualistic benefit = min(A reaching symbiont, B reaching host).
    Steeply proximity-dependent (the minimum of two screened fluxes) and capped by the scarcer
    partner — the signature of obligate bidirectional syntrophy."""
    import math
    sa = _settled(rows, "symbiont_a_conc")
    hb = _settled(rows, "host_b_conc")
    if math.isnan(sa) or math.isnan(hb):
        return float("nan")
    return min(sa, hb)
