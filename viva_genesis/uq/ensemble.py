"""Structural model ensembles: separate parameter uncertainty from model-form uncertainty.

Plan section 11: *run alternative equations/solvers behind common PBG
interfaces — separate parameter uncertainty from model-form uncertainty.*
Full modeling plan 4.3 names the reducers:

* ``pass_fraction[m]`` — the fraction of the parameter grid where model class
  ``m`` passes the gate (parameter uncertainty, per class);
* ``structure_agreement`` — the fraction of grid points where ALL classes agree
  (pass/pass or fail/fail); ``1 - structure_agreement`` is the share of the
  parameter space where the answer depends on which model you believe;
* ``decision_envelope`` — union and intersection pass regions across classes
  (the two contours on one phase map).

All three operate on a :class:`~viva_genesis.sweep.SweepResult` that has a
categorical model-class axis (``model_<interface>``), or on a plain
``{class_name: boolean_array}`` mapping (the ensemble pipeline's form).
"""

from __future__ import annotations

from typing import Callable, Mapping

import numpy as np

from ..sweep import SweepResult


def _gate_masks(result: SweepResult, axis: str, surface: str,
                gate: Callable[[np.ndarray], np.ndarray] | None = None,
                threshold: float = 0.5) -> dict[str, np.ndarray]:
    """``{class_name: pass-mask over the remaining axes}`` for one gate surface."""
    if axis not in result.axis_order:
        raise KeyError(f"axis {axis!r} not in sweep axes {result.axis_order}")
    masks = {}
    for name in result.axes[axis]:
        sub = result.slice_along(axis, name)
        surf = sub.surfaces[surface]
        if gate is None:
            m = np.asarray(surf >= threshold)
        else:
            m = np.asarray(gate(surf), dtype=bool)
        m = m & np.isfinite(surf)   # NaN (engine rejected the point) is a FAIL, never a pass
        masks[str(name)] = m
    return masks


def pass_fraction(result_or_masks, axis: str | None = None, surface: str | None = None, *,
                  gate=None, threshold: float = 0.5) -> dict[str, float]:
    """Per model class: fraction of the parameter domain that passes the gate."""
    masks = (result_or_masks if isinstance(result_or_masks, Mapping)
             else _gate_masks(result_or_masks, axis, surface, gate, threshold))
    return {k: float(np.mean(v)) if np.size(v) else float("nan") for k, v in masks.items()}


def structure_agreement(result_or_masks, axis: str | None = None, surface: str | None = None, *,
                        gate=None, threshold: float = 0.5) -> dict:
    """Agreement across model classes; ``1 - agreement`` is model-structure uncertainty."""
    masks = (result_or_masks if isinstance(result_or_masks, Mapping)
             else _gate_masks(result_or_masks, axis, surface, gate, threshold))
    names = list(masks)
    if not names:
        return {"agreement": float("nan"), "structure_uncertainty": float("nan"), "classes": []}
    stack = np.stack([np.asarray(masks[n], dtype=bool) for n in names])
    all_pass = np.all(stack, axis=0)
    all_fail = np.all(~stack, axis=0)
    agree = all_pass | all_fail
    return {
        "classes": names,
        "agreement": float(np.mean(agree)) if agree.size else float("nan"),
        "structure_uncertainty": float(np.mean(~agree)) if agree.size else float("nan"),
        "all_pass_fraction": float(np.mean(all_pass)) if agree.size else float("nan"),
        "all_fail_fraction": float(np.mean(all_fail)) if agree.size else float("nan"),
        "pass_fraction": {n: float(np.mean(masks[n])) for n in names},
    }


def decision_envelope(result_or_masks, axis: str | None = None, surface: str | None = None, *,
                      gate=None, threshold: float = 0.5) -> dict[str, np.ndarray]:
    """``{"intersection": mask, "union": mask, "structure_sensitive": union & ~intersection}``."""
    masks = (result_or_masks if isinstance(result_or_masks, Mapping)
             else _gate_masks(result_or_masks, axis, surface, gate, threshold))
    stack = np.stack([np.asarray(m, dtype=bool) for m in masks.values()])
    inter = np.all(stack, axis=0)
    union = np.any(stack, axis=0)
    return {"intersection": inter, "union": union, "structure_sensitive": union & ~inter}


def paired_class_difference(outcomes_by_class: Mapping[str, list[Mapping[str, float]]],
                            readouts: list[str]) -> dict[str, dict]:
    """Per readout: standardised paired difference between two model classes on the SAME draws.

    The discrimination reducer for an ensemble run once per class with identical
    parameter draws: ``d = mean(a - b) / pooled_sd``. Large |d| means the readout
    tells the classes apart; ~0 means the readout cannot discriminate them.
    """
    names = list(outcomes_by_class)
    if len(names) != 2:
        raise ValueError("paired_class_difference compares exactly two classes")
    a_rows, b_rows = outcomes_by_class[names[0]], outcomes_by_class[names[1]]
    out = {}
    for r in readouts:
        a = np.array([float(x.get(r, np.nan)) for x in a_rows])
        b = np.array([float(x.get(r, np.nan)) for x in b_rows])
        ok = np.isfinite(a) & np.isfinite(b)
        if ok.sum() < 2:
            out[r] = {"d": float("nan"), "mean_diff": float("nan"), "n": int(ok.sum())}
            continue
        diff = a[ok] - b[ok]
        pooled = np.sqrt(0.5 * (np.var(a[ok], ddof=1) + np.var(b[ok], ddof=1))) + 1e-30
        out[r] = {"d": float(np.mean(diff) / pooled), "mean_diff": float(np.mean(diff)),
                  "mean_abs_diff": float(np.mean(np.abs(diff))), "n": int(ok.sum()),
                  "classes": names}
    return out


__all__ = ["pass_fraction", "structure_agreement", "decision_envelope", "paired_class_difference"]
