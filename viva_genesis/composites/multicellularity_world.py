"""Shared CPM "world" blueprint for the multicellularity campaign (S04-S06).

``build_world_spec`` returns the viva-cpm ``spec`` for a growing clonal cluster of
one cell type; the ``adhesion`` knob in [0, 1] sets the homotypic contact energy.
``s04_morphomechanics`` wires it into a single ``CPMProcess`` whose
``n_propagules`` / ``largest_cluster_fraction`` outputs land in top-level stores
(so a study's ``readouts[].store_path`` can address them).

No heavy import here: the process is addressed by string, so the generator
registers even when viva_cpm is not installed.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

CPM_ADDR = "local:!viva_cpm.processes.cpm_process.CPMProcess"

# adhesion -> homotypic contact energy J(1,1), monotonic decreasing:
#     J_hom = J_MIN + (J_MAX - J_MIN) * (1 - adhesion)
# adhesion=1 -> J_MIN (cells much prefer each other: cohesive); adhesion=0 -> J_MAX.
# Medium-cell J(0,1) is fixed. A cluster stays condensed while J_hom < 2*J_MEDIUM
# (cell-cell contact cheaper than exposing two medium faces), so J_MAX > 2*J_MEDIUM
# makes adhesion=0 a true non-adhesive control.
J_MIN = 2.0
J_MAX = 60.0
J_MEDIUM = 12.0

_EMIT_PATHS = [
    "n_propagules", "largest_cluster_fraction", "volumes", "types", "positions",
    "global_time",
]


def homotypic_j(adhesion: float) -> float:
    a = min(1.0, max(0.0, float(adhesion)))
    return J_MIN + (J_MAX - J_MIN) * (1.0 - a)


def build_world_spec(*, adhesion, seed_volume=30.0, grow_rate=2.0, divide_threshold=55.0,
                     dims=(80, 40, 1), report_types=(1,)) -> dict:
    """Shared CPM world spec: one clonal 2x2 cluster of type 1 at the lattice centre and a
    full contact matrix (pure ``load_world`` vocabulary). The ``mitosis`` and
    ``report_aggregate_types`` knobs are CPMProcess config keys, not spec keys; build them
    with :func:`world_process_config`.

    NOTE (transient window): growth-driven fracture is a TRANSIENT, quasi-static readout.
    Measure at ~40 updates (``default_n_steps=40``); beyond ~80 updates crowding re-merges
    clusters and the strong-vs-weak adhesion contrast disappears. Downstream studies must
    pin the readout to this window.
    """
    nx, ny, nz = (int(d) for d in dims)
    side = max(2, int(round(float(seed_volume) ** 0.5)))      # square patch of ~seed_volume sites
    gap = 1
    n = 2
    total = n * side + (n - 1) * gap
    x_start, y_start = (nx - total) // 2, (ny - total) // 2
    cells = []
    for i in range(n):
        for j in range(n):
            x0 = x_start + i * (side + gap)
            y0 = y_start + j * (side + gap)
            cells.append({
                "type": 1, "target_volume": float(seed_volume), "lambda_volume": 2.0,
                "target_surface": 4.0 * side, "lambda_surface": 0.2,
                "seed_block": [x0, y0, 0, x0 + side, y0 + side, nz],
            })
    return {
        "potts": {"dims": [nx, ny, nz], "boundary": "noflux", "neighbor_order": 2,
                  "temperature": 8.0, "seed": 1},
        "cells": cells,
        "contact": [
            {"a": 0, "b": 1, "j": J_MEDIUM},                  # medium-cell
            {"a": 1, "b": 1, "j": homotypic_j(adhesion)},     # homotypic (adhesion-controlled)
        ],
    }


def world_process_config(*, adhesion, seed_volume=30.0, grow_rate=2.0, divide_threshold=55.0,
                         dims=(80, 40, 1), report_types=(1,), mcs_per_update=16) -> dict:
    """CPMProcess config: the world spec plus the mitosis and aggregate-report knobs."""
    return {
        "spec": build_world_spec(adhesion=adhesion, seed_volume=seed_volume, grow_rate=grow_rate,
                                 divide_threshold=divide_threshold, dims=dims,
                                 report_types=report_types),
        "mcs_per_update": int(mcs_per_update),
        "mitosis": [{"type": 1, "grow_rate": float(grow_rate),
                     "divide_threshold": float(divide_threshold),
                     "reset_target": float(seed_volume)}],
        "report_aggregate_types": [int(t) for t in report_types],
    }


# TRANSIENT WINDOW: the growth-driven fracture this composite shows is a transient,
# quasi-static readout. Measure at ~40 updates (default_n_steps=40); beyond ~80 updates
# crowding re-merges clusters and the contrast disappears. Studies must pin to this window.
@composite_generator(
    name="s04_morphomechanics",
    methods=["Cellular Potts (Glazier-Graner-Hogeweg) clonal growth with differential adhesion"],
    fidelity="spatial_dynamics",
    description=(
        "Multicellularity S04 (morphomechanics). A clonal cell cluster grows and divides on the "
        "Rust CPM engine; the adhesion knob sets homotypic contact energy. Strong adhesion keeps "
        "the cluster one cohesive body; weak adhesion lets growth fracture it into propagules. "
        "Emits n_propagules and largest_cluster_fraction."
    ),
    parameters={
        "adhesion": {"type": "number", "default": 0.8,
                     "description": "cell-cell adhesion in [0,1]; higher = lower homotypic J = cohesive"},
        "grow_rate": {"type": "number", "default": 2.0,
                      "description": "target-volume growth per update per cell"},
        "divide_threshold": {"type": "number", "default": 55.0,
                             "description": "volume at which a cell divides"},
    },
    default_n_steps=40,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def s04_morphomechanics(core=None, *, adhesion=0.8, grow_rate=2.0, divide_threshold=55.0):
    config = world_process_config(adhesion=adhesion, grow_rate=grow_rate,
                                  divide_threshold=divide_threshold)
    return {
        "cpm": {
            "_type": "process",
            "address": CPM_ADDR,
            "config": config,
            "interval": 1.0,
            "inputs": {},
            "outputs": {"volumes": ["volumes"], "types": ["types"], "positions": ["positions"],
                        "n_propagules": ["n_propagules"],
                        "largest_cluster_fraction": ["largest_cluster_fraction"]},
        },
    }
