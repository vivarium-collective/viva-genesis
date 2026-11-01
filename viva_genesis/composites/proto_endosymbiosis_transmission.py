"""proto_endosymbiosis_transmission — coupled bridge model (M5: evolutionary stability).

Measures ``endosymbiont_retention_fraction`` for study-vertical-transmission-stability: the
settled fraction of host lineages still bearing a functional symbiont after many generations,
under vertical transmission + conflict/partner-loss + selection. See
``viva_genesis.endosymbiosis_transmission.VerticalTransmissionProcess`` for the rationale.
High retention ⇒ the established endosymbiosis is evolutionarily stable (heritable); ~0 ⇒ it
decays even after it establishes (unstable).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from ..endosymbiosis_transmission import VerticalTransmissionProcess  # registered via build_core (top-level scan)


def _settled(rows, key, frac=0.25):
    n = max(1, int(round(len(rows) * frac)))
    t = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    t = [x for x in t if x == x]
    return sum(t) / len(t) if t else float("nan")


@composite_generator(
    name="proto_endosymbiosis_transmission",
    emitters=[{"address": "local:SQLiteEmitter",
               "paths": ["global_time", "n_sym", "n_free"]}],
    parameters={
        "benefit": {"type": "float", "default": 0.6, "description": "net exchange benefit of bearing a symbiont"},
        "cost": {"type": "float", "default": 0.1, "description": "maintenance cost of the symbiont"},
        "fidelity": {"type": "float", "default": 0.95, "description": "P(daughter inherits symbiont) at division"},
        "loss_rate": {"type": "float", "default": 0.05, "description": "conflict / partner-loss rate (sym->free)"},
        "reacquire_rate": {"type": "float", "default": 0.01, "description": "horizontal re-acquisition (free->sym)"},
        "base_growth": {"type": "float", "default": 0.3, "description": "selection timescale (turnover rate)"},
        "init_freq_sym": {"type": "float", "default": 0.5, "description": "initial symbiont-bearing fraction"},
        "n_initial": {"type": "float", "default": 200.0, "description": "initial population size"},
        "seed": {"type": "integer", "default": 1, "description": "random seed"},
    },
    description="Coupled bridge model M5: evolutionary stability of an established "
                "endosymbiosis under vertical transmission, conflict, and selection.",
)
def proto_endosymbiosis_transmission(core=None, *, benefit=0.6, cost=0.1, fidelity=0.95,
                                     loss_rate=0.05, reacquire_rate=0.01, base_growth=0.3,
                                     init_freq_sym=0.5, n_initial=200.0, seed=1):
    if core is None:
        core = build_core()
    if "VerticalTransmissionProcess" not in core.link_registry:
        core.register_link("VerticalTransmissionProcess", VerticalTransmissionProcess)
    n0, f0 = float(n_initial), float(init_freq_sym)
    return {
        "heredity": {
            "_type": "process", "address": "local:VerticalTransmissionProcess", "interval": 1.0,
            "config": {"benefit": float(benefit), "cost": float(cost), "fidelity": float(fidelity),
                       "loss_rate": float(loss_rate), "reacquire_rate": float(reacquire_rate),
                       "base_growth": float(base_growth)},
            "inputs": {"n_sym": ["n_sym"], "n_free": ["n_free"]},
            "outputs": {"n_sym": ["n_sym"], "n_free": ["n_free"]},
        },
        "n_sym": n0 * f0, "n_free": n0 * (1.0 - f0),
    }


def endosymbiont_retention_fraction(rows) -> float:
    """Settled fraction of lineages still bearing a functional symbiont. >=0.5 ⇒ the
    established endosymbiosis is evolutionarily stable (heritable); ~0 ⇒ it decays."""
    import math
    sym = _settled(rows, "n_sym")
    total = sym + _settled(rows, "n_free")
    if not (total > 0) or math.isnan(total):
        return float("nan")
    return sym / total
