"""The Phase-1 posterior, carried forward as draws (not a best fit).

Model Upgrade plan section 11 and the roadmap's flagship chain: downstream
phases propagate the environmental calibration *as a distribution*. The
``og-cal-vent-environment`` study committed its ensemble
(``artifacts/vent_environment_ensemble.json``: 48 LHS prior draws of the
``vent_environment`` package run through the geochemical world, with every
draw's readouts) and its conditioning report (the Lost City observation
windows + the downstream requirements). :func:`posterior_draws` re-applies
exactly that conditioning rule to the committed outcomes and returns the
draws that survive it — the posterior — each with the readouts a downstream
world needs as its vent endmember: dissolved H2, the pH contrast, the vent
temperature, the inflowing DIC and the flow.
"""

from __future__ import annotations

import json
from pathlib import Path

_ENSEMBLE = "workspace/studies/og-cal-vent-environment/artifacts/vent_environment_ensemble.json"
_REPORT = "workspace/studies/og-cal-vent-environment/artifacts/vent_environment_report.json"
HEADLINE_CLASS = "serpentinization=phreeqc+spatial_transport=fipy"


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load(path: str) -> dict:
    p = workspace_root() / path
    if not p.exists():
        raise FileNotFoundError(f"Phase-1 artifact missing: {p}")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _within(value: float, spec: dict) -> bool:
    lo, hi = spec.get("low"), spec.get("high")
    if value is None or value != value:
        return False
    if lo is not None and value < float(lo):
        return False
    if hi is not None and value > float(hi):
        return False
    return True


def posterior_draws(model_class: str = HEADLINE_CLASS, *, viable: bool = True) -> list[dict]:
    """The Phase-1 draws consistent with every Lost City observation window
    (and, with ``viable``, meeting every downstream requirement), as
    ``{"index", "params": {...}, "readouts": {...}, "endmember": {...}}``.

    ``endmember`` is what a downstream world consumes: ``h2_vent`` (M, from
    the dissolved-H2 readout in mmol/kg), ``delta_ph``, ``temperature`` (K),
    ``dic`` (M, the draw's inflowing DIC), ``flow_velocity`` (m/s) and
    ``olivine_rate``.
    """
    ens = _load(_ENSEMBLE)
    rep = _load(_REPORT)
    cond = rep["conditioning"]
    outcomes = ens["outcomes"][model_class]
    draws = ens["draws"]
    out = []
    for i, (params, oc) in enumerate(zip(draws, outcomes)):
        if not oc.get("ok", False):
            continue
        consistent = all(_within(oc.get(o["readout"]), o) for o in cond["observations"])
        if not consistent:
            continue
        if viable and not all(_within(oc.get(r["readout"]), r) for r in cond["requirements"]):
            continue
        out.append({
            "index": i, "params": dict(params),
            "readouts": {k: oc.get(k) for k in ens["meta"]["readouts"]},
            "endmember": {
                "h2_vent": float(oc["dissolved_H2_mmol_kg"]) * 1.0e-3,
                "delta_ph": float(oc["delta_pH"]),
                "temperature": float(oc["settled_temperature_C"]) + 273.15,
                "dic": float(params["fluid_dic"]),
                "flow_velocity": float(params["flow_velocity"]),
                "olivine_rate": float(params["olivine_rate"]),
            },
        })
    if not out:
        raise ValueError(f"no Phase-1 draw survives the conditioning for {model_class!r}")
    return out


def posterior_summary(draws: list[dict] | None = None) -> dict:
    """Mean / sd / min / max of every endmember quantity over the posterior draws
    (what the vg-data package ``integrated_autonomy`` records as its distributions)."""
    import numpy as np
    draws = draws if draws is not None else posterior_draws()
    keys = list(draws[0]["endmember"])
    out = {"n": len(draws), "indices": [d["index"] for d in draws]}
    for k in keys:
        v = np.array([float(d["endmember"][k]) for d in draws])
        out[k] = {"mean": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
                  "min": float(v.min()), "max": float(v.max())}
    return out


__all__ = ["posterior_draws", "posterior_summary", "HEADLINE_CLASS"]
