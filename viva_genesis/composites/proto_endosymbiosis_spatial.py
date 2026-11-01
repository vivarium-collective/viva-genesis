"""proto_endosymbiosis_spatial — coupled bridge model (M6: spatial exchange).

Measures the realised metabolite-exchange level at a consumer as a function of its distance
from the producer, to test M1's lumped premise that contact scales exchange access. See
``viva_genesis.endosymbiosis_spatial.DiffusiveExchangeProcess``. The discriminating observable
is ``realised_exchange_level`` (steady-state consumer concentration); comparing a contact arm
to a distal arm gives the proximity advantage that M1 assumes.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from ..endosymbiosis_spatial import DiffusiveExchangeProcess  # registered via build_core (top-level scan)


def _settled(rows, key, frac=0.2):
    n = max(1, int(round(len(rows) * frac)))
    t = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    t = [x for x in t if x == x]
    return sum(t) / len(t) if t else float("nan")


@composite_generator(
    name="proto_endosymbiosis_spatial",
    emitters=[{"address": "local:SQLiteEmitter",
               "paths": ["global_time", "consumer_conc"]}],
    parameters={
        "n_cells": {"type": "integer", "default": 16, "description": "1-D grid length"},
        "diffusion": {"type": "float", "default": 0.4, "description": "diffusion coefficient D"},
        "decay": {"type": "float", "default": 0.08, "description": "decay rate k (screening length sqrt(D/k))"},
        "production": {"type": "float", "default": 1.0, "description": "producer source flux"},
        "uptake": {"type": "float", "default": 0.2, "description": "consumer uptake rate"},
        "consumer_distance": {"type": "integer", "default": 1, "description": "consumer cell distance from producer"},
        "seed": {"type": "integer", "default": 1, "description": "random seed"},
    },
    description="Coupled bridge model M6: spatial metabolite exchange — realised exchange "
                "level vs producer-consumer distance, testing M1's contact-scales-access premise.",
)
def proto_endosymbiosis_spatial(core=None, *, n_cells=16, diffusion=0.4, decay=0.08,
                                production=1.0, uptake=0.2, consumer_distance=1, seed=1):
    if core is None:
        core = build_core()
    if "DiffusiveExchangeProcess" not in core.link_registry:
        core.register_link("DiffusiveExchangeProcess", DiffusiveExchangeProcess)
    n = int(n_cells)
    return {
        "exchange": {
            "_type": "process", "address": "local:DiffusiveExchangeProcess", "interval": 1.0,
            "config": {"n_cells": n, "diffusion": float(diffusion), "decay": float(decay),
                       "production": float(production), "uptake": float(uptake),
                       "consumer_distance": int(consumer_distance)},
            "inputs": {"conc": ["conc"], "consumer_conc": ["consumer_conc"]},
            "outputs": {"conc": ["conc"], "consumer_conc": ["consumer_conc"]},
        },
        "conc": {str(i): 0.0 for i in range(n)},
        "consumer_conc": 0.0,
    }


def realised_exchange_level(rows) -> float:
    """Steady-state metabolite level reaching the consumer (realised exchange benefit).
    Compared across contact vs distal arms it gives the proximity advantage M1 assumes."""
    import math
    v = _settled(rows, "consumer_conc")
    return v if (v == v and not math.isinf(v)) else float("nan")
