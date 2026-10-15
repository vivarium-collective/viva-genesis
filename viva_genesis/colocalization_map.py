"""Co-localization phase map for the multisolute pore (Phase 4 / §4.5, §6).

The decisive Stage-III question as a Decision surface: over the pore's control
space -- advective Peclet x Soret strength -- does the chemically-necessary
prebiotic MIXTURE co-localize (all eight solutes concentrate together, a
positive concentrating mechanism) or fractionate (different solutes concentrate
to DIFFERENT DEGREES set by their Soret coefficient, so low-S_T solutes such as
ammonium lag the strong thermophoretic precursors -- a fatal incompatibility)?
The fractionation is Soret-driven; adsorption and degradation are kinetically
minor over a single pore transit (the resolved-FEM mobile fraction stays
~0.93-1.0 even at high adsorption), so they are not the primary driver.

This drives the reduced surrogate (``MultisolutePoreSurrogateProcess``,
calibrated to the viva-fenics FEM reference to ~7 % on enrichment) over the grid
so a full Decision map is cheap; the FEM reference
(``fenics_multisolute_3d``) is reserved for World-view points + an audit subset
(run under pixi), exactly the plan §4.6 split. ``model_localization`` is a
categorical axis, so the same grid re-runs per model class and
``viva_genesis.uq.ensemble`` can separate parameter uncertainty from model-
structure uncertainty on it.

Co-localization is summarised per cell by ``coloc_index`` = min/max of the
per-species dissolved enrichment: ``1`` = every solute concentrates equally
(co-localized), ``-> 0`` = one solute is pulled out while others concentrate
(fractionation). ``frac_concentrated`` is the share of solutes that concentrate
above feed at all, and ``max_enrichment`` the strongest single-species factor --
together they read as: strong + uniform = co-localized trap; strong + non-uniform
= fractionating; weak = the pore does not concentrate the mixture at this regime.
"""
from __future__ import annotations

import numpy as np

from .core import build_core
from .multisolute_localization import _default_species_params
from .sweep import sweep_grid


def _scaled_species(soret_scale):
    sp = _default_species_params()
    for p in sp.values():
        p["soret"] = float(p["soret"]) * float(soret_scale)
    return sp


def multisolute_pore_doc(core=None, *, peclet=8.0, soret_scale=1.0,
                         model_localization="multisolute_surrogate"):
    """Module-level generator for the co-localization sweep: a single
    localization model node (selected on the ``localization`` face) driving the
    eight-solute mixture (its Soret strengths scaled by ``soret_scale``) at the
    given advective ``peclet``, wired to a RAM emitter that emits the per-species
    enrichment map."""
    if core is None:
        core = build_core()
    from . import models
    address = models.resolve_checked(core, "localization", model_localization)
    return {
        "pore": {
            "_type": "process", "address": address,
            "config": {"peclet": float(peclet),
                       "species_params": _scaled_species(soret_scale)},
            "inputs": {},
            "outputs": {"enrichment": ["stores", "enrichment"],
                        "flux_divergence_residual": ["stores", "flux"]},
        },
        "stores": {"enrichment": {}, "flux": 0.0},
        "emitter": {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {"enrichment": "tree", "flux": "float"}},
            "inputs": {"enrichment": ["stores", "enrichment"], "flux": ["stores", "flux"]},
        },
    }


# --- module-level reducers (operate on the emitter row list) ----------------

def _last_enrichment(rows):
    for r in reversed(rows):
        e = r.get("enrichment")
        if e:
            return {k: float(v) for k, v in e.items()}
    return {}


def coloc_index(rows):
    """min/max of per-species enrichment: 1 = co-localized, -> 0 = fractionating."""
    e = _last_enrichment(rows)
    if not e:
        return float("nan")
    vals = list(e.values())
    mx = max(vals)
    return (min(vals) / mx) if mx > 0 else float("nan")


def mean_enrichment(rows):
    e = _last_enrichment(rows)
    return float(np.mean(list(e.values()))) if e else float("nan")


def max_enrichment(rows):
    e = _last_enrichment(rows)
    return float(max(e.values())) if e else float("nan")


def frac_concentrated(rows):
    """Share of solutes that concentrate above feed (>1.05)."""
    e = _last_enrichment(rows)
    if not e:
        return float("nan")
    return float(np.mean([1.0 if v > 1.05 else 0.0 for v in e.values()]))


def colocalization_verdict(coloc, max_enr, *, strong=1.1, uniform=0.7):
    """Map (coloc_index, max_enrichment) to a verdict string."""
    if not np.isfinite(coloc) or not np.isfinite(max_enr):
        return "undefined"
    if max_enr < strong:
        return "weak"                       # the pore barely concentrates here
    return "co-localized" if coloc >= uniform else "fractionating"


def colocalization_map(*, peclets=(1.0, 2.0, 4.0, 8.0, 16.0, 32.0),
                       soret_scales=(0.5, 1.0, 2.0, 4.0, 8.0),
                       model_localization="multisolute_surrogate",
                       n_jobs=1):
    """Sweep (peclet x soret_scale) and return the co-localization SweepResult.

    ``model_localization`` selects the localization model class (default the
    reduced surrogate; pass ``"fenics_multisolute_3d"`` to run the FEM reference
    under pixi, or make it an axis for a structure comparison). The surrogate is
    analytic-steady, so one step per cell suffices."""
    axes = {"peclet": list(peclets), "soret_scale": list(soret_scales)}
    res = sweep_grid(
        multisolute_pore_doc, axes,
        reduce={"coloc_index": coloc_index, "mean_enrichment": mean_enrichment,
                "max_enrichment": max_enrichment, "frac_concentrated": frac_concentrated},
        fixed={"model_localization": model_localization},
        n_steps=1, n_jobs=n_jobs,
    )
    res.meta["stage"] = "og-03 pore co-localization (multisolute)"
    res.meta["model_localization"] = model_localization
    res.meta["coloc_index"] = "min/max per-species enrichment (1=co-localized, 0=fractionating)"
    return res
