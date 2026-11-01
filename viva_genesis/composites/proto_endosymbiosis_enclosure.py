"""proto_endosymbiosis_enclosure — coupled bridge model (M2: stable enclosure).

Measures ``probability_of_stable_enclosure`` for study-enclosure-mechanics, to
discriminate H2-geometry-first (P>=0.5) from H3-parasitism-or-conflict (P<0.5). See
``viva_genesis.endosymbiosis_enclosure.EnclosureProcess`` for the reduced-model rationale.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from ..endosymbiosis_enclosure import EnclosureProcess  # registered via build_core (top-level scan)


def _last(rows, key):
    return float(rows[-1].get(key, float("nan"))) if rows else float("nan")


def _settled(rows, key, frac=0.25):
    n = max(1, int(round(len(rows) * frac)))
    t = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    t = [x for x in t if x == x]
    return sum(t) / len(t) if t else float("nan")


@composite_generator(
    name="proto_endosymbiosis_enclosure",
    emitters=[{"address": "local:SQLiteEmitter",
               "paths": ["global_time", "n_attempting", "n_sealed", "n_stalled"]}],
    parameters={
        "adhesion_energy": {"type": "float", "default": 0.6, "description": "adhesion drive (seals + resists unwrap)"},
        "bending_modulus": {"type": "float", "default": 0.3, "description": "neck-closure bending barrier (cost)"},
        "perturbation": {"type": "float", "default": 0.2, "description": "unwrapping stress on sealed attempts"},
        "seal_rate": {"type": "float", "default": 0.3, "description": "base attempting->sealed rate"},
        "unwrap_rate": {"type": "float", "default": 0.3, "description": "base sealed->stalled rate"},
        "retry_rate": {"type": "float", "default": 0.05, "description": "stalled->attempting rate"},
        "sharpness": {"type": "float", "default": 6.0, "description": "sigmoid sharpness k"},
        "n_attempts": {"type": "float", "default": 100.0, "description": "ensemble size"},
        "seed": {"type": "integer", "default": 1, "description": "random seed"},
    },
    description="Coupled bridge model M2: stable-enclosure probability from an ensemble of "
                "enclosure attempts under adhesion vs bending barrier vs perturbation.",
)
def proto_endosymbiosis_enclosure(core=None, *, adhesion_energy=0.6, bending_modulus=0.3,
                                  perturbation=0.2, seal_rate=0.3, unwrap_rate=0.3,
                                  retry_rate=0.05, sharpness=6.0, n_attempts=100.0, seed=1):
    if core is None:
        core = build_core()
    if "EnclosureProcess" not in core.link_registry:
        core.register_link("EnclosureProcess", EnclosureProcess)
    n0 = float(n_attempts)
    return {
        "enclosure": {
            "_type": "process", "address": "local:EnclosureProcess", "interval": 1.0,
            "config": {"adhesion_energy": float(adhesion_energy), "bending_modulus": float(bending_modulus),
                       "perturbation": float(perturbation), "seal_rate": float(seal_rate),
                       "unwrap_rate": float(unwrap_rate), "retry_rate": float(retry_rate),
                       "sharpness": float(sharpness)},
            "inputs": {"n_attempting": ["n_attempting"], "n_sealed": ["n_sealed"], "n_stalled": ["n_stalled"]},
            "outputs": {"n_attempting": ["n_attempting"], "n_sealed": ["n_sealed"], "n_stalled": ["n_stalled"]},
        },
        "n_attempting": n0, "n_sealed": 0.0, "n_stalled": 0.0,
    }


def probability_of_stable_enclosure(rows) -> float:
    """Settled fraction of the ensemble that is stably enclosed (sealed and persisting).
    >=0.5 ⇒ stable enclosure is the majority outcome (H2-geometry-first); <0.5 ⇒ enclosure
    fails or doesn't persist (H3-parasitism-or-conflict)."""
    import math
    sealed = _settled(rows, "n_sealed")
    att = _settled(rows, "n_attempting")
    stall = _settled(rows, "n_stalled")
    total = sealed + att + stall
    if not (total > 0) or math.isnan(total):
        return float("nan")
    return sealed / total


def final_sealed_fraction(rows) -> float:
    sealed = _last(rows, "n_sealed")
    total = _last(rows, "n_sealed") + _last(rows, "n_attempting") + _last(rows, "n_stalled")
    return sealed / total if total > 0 else float("nan")
