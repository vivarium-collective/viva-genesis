"""proto_endosymbiosis_coupled — coupled bridge model (M3: joint feasibility).

Measures ``joint_feasibility_region`` for study-contact-to-enclosure-coupling: the fraction
of the lineage ensemble that reaches BOTH high contact AND stable enclosure, under the
reinforcing coupling between selection-for-contact (M1) and enclosure stability (M2). See
``viva_genesis.endosymbiosis_coupled.CoupledTransitionProcess`` for the coupling rationale.
A positive feasible fraction in some regime ⇒ the coupled transition is possible (there
exists a self-reinforcing contact+enclosure regime); ~0 everywhere ⇒ the mechanisms are
mutually exclusive along this path.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from ..endosymbiosis_coupled import CoupledTransitionProcess  # registered via build_core (top-level scan)


def _settled(rows, key, frac=0.25):
    n = max(1, int(round(len(rows) * frac)))
    t = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    t = [x for x in t if x == x]
    return sum(t) / len(t) if t else float("nan")


@composite_generator(
    name="proto_endosymbiosis_coupled",
    emitters=[{"address": "local:SQLiteEmitter",
               "paths": ["global_time", "n_lc", "n_hc_un", "n_hc_se", "n_hc_st"]}],
    parameters={
        "benefit_coeff": {"type": "float", "default": 1.2, "description": "max freq-dependent exchange benefit"},
        "cost_coeff": {"type": "float", "default": 0.3, "description": "adhesion cost"},
        "base_adhesion": {"type": "float", "default": 0.8, "description": "adhesion of a high-contact lineage"},
        "bending_modulus": {"type": "float", "default": 0.2, "description": "enclosure neck-closure barrier"},
        "perturbation": {"type": "float", "default": 0.1, "description": "unwrapping stress"},
        "seal_rate": {"type": "float", "default": 0.3, "description": "base hc_un->hc_se rate"},
        "unwrap_rate": {"type": "float", "default": 0.3, "description": "base hc_se->hc_un rate"},
        "selection_strength": {"type": "float", "default": 1.0, "description": "replicator step scaling"},
        "sharpness": {"type": "float", "default": 6.0, "description": "sigmoid sharpness k"},
        "n_lineages": {"type": "float", "default": 100.0, "description": "ensemble size"},
        "init_freq_high": {"type": "float", "default": 0.3, "description": "initial high-contact frequency"},
        "seed": {"type": "integer", "default": 1, "description": "random seed"},
    },
    description="Coupled bridge model M3: joint feasibility of selection-for-contact and "
                "stable enclosure under their reinforcing coupling.",
)
def proto_endosymbiosis_coupled(core=None, *, benefit_coeff=1.2, cost_coeff=0.3, base_adhesion=0.8,
                                bending_modulus=0.2, perturbation=0.1, seal_rate=0.3, unwrap_rate=0.3,
                                selection_strength=1.0, sharpness=6.0, n_lineages=100.0,
                                init_freq_high=0.3, seed=1):
    if core is None:
        core = build_core()
    if "CoupledTransitionProcess" not in core.link_registry:
        core.register_link("CoupledTransitionProcess", CoupledTransitionProcess)
    n0, f0 = float(n_lineages), float(init_freq_high)
    return {
        "coupled": {
            "_type": "process", "address": "local:CoupledTransitionProcess", "interval": 1.0,
            "config": {"benefit_coeff": float(benefit_coeff), "cost_coeff": float(cost_coeff),
                       "base_adhesion": float(base_adhesion), "bending_modulus": float(bending_modulus),
                       "perturbation": float(perturbation), "seal_rate": float(seal_rate),
                       "unwrap_rate": float(unwrap_rate), "selection_strength": float(selection_strength),
                       "sharpness": float(sharpness)},
            "inputs": {"n_lc": ["n_lc"], "n_hc_un": ["n_hc_un"], "n_hc_se": ["n_hc_se"], "n_hc_st": ["n_hc_st"]},
            "outputs": {"n_lc": ["n_lc"], "n_hc_un": ["n_hc_un"], "n_hc_se": ["n_hc_se"], "n_hc_st": ["n_hc_st"]},
        },
        "n_lc": n0 * (1.0 - f0), "n_hc_un": n0 * f0, "n_hc_se": 0.0, "n_hc_st": 0.0,
    }


def joint_feasibility_region(rows) -> float:
    """Settled fraction of lineages that are BOTH high-contact AND stably sealed (hc_se).
    >0 ⇒ selection-for-contact and stable enclosure co-succeed (coupled transition feasible);
    ~0 ⇒ the two mechanisms do not co-occur in this regime."""
    import math
    hc_se = _settled(rows, "n_hc_se")
    total = hc_se + _settled(rows, "n_hc_un") + _settled(rows, "n_hc_st") + _settled(rows, "n_lc")
    if not (total > 0) or math.isnan(total):
        return float("nan")
    return hc_se / total


def final_contact_frequency(rows) -> float:
    hc = _settled(rows, "n_hc_un") + _settled(rows, "n_hc_se") + _settled(rows, "n_hc_st")
    total = hc + _settled(rows, "n_lc")
    return hc / total if total > 0 else float("nan")
