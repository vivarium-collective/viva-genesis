"""S06 group_partition: pure read-out feeding the Price-equation partition."""
import pytest

pytest.importorskip("viva_cpm")

from viva_genesis.composites.multicellularity_world import group_partition


def _world():
    from viva_cpm.schema import load_world
    from viva_genesis.composites.multicellularity_world import J_MEDIUM, homotypic_j

    def cell(t, x0, x1):
        return {"type": t, "target_volume": 30.0, "lambda_volume": 2.0,
                "target_surface": 20.0, "lambda_surface": 0.2,
                "seed_block": [x0, 5, 0, x1, 11, 1]}
    spec = {
        "potts": {"dims": [40, 16, 1], "boundary": "noflux", "neighbor_order": 2,
                  "temperature": 8.0, "seed": 1},
        "cells": [cell(1, 4, 10), cell(2, 26, 32)],
        "contact": [
            {"a": 0, "b": 1, "j": J_MEDIUM}, {"a": 0, "b": 2, "j": J_MEDIUM},
            {"a": 1, "b": 1, "j": homotypic_j(0.9)},
            {"a": 2, "b": 2, "j": homotypic_j(0.2)},
            {"a": 1, "b": 2, "j": J_MEDIUM},
        ],
    }
    w = load_world(spec)
    for _ in range(8):
        for t in (1, 2):
            w.grow(t, 8.0)
        w.step(16)
        w.divide_cells(55.0, 30.0)
    return w


def test_group_partition_matches_metrics_and_counts():
    from viva_cpm import metrics
    w = _world()
    before = list(w.snapshot())
    p = group_partition(w, [1, 2])
    assert list(w.snapshot()) == before  # pure
    for f in (1, 2):
        assert p[f]["toughness"] == metrics.largest_cluster_fraction(w, [f])
    live = [i for i, v in enumerate(w.cell_volumes()) if i > 0 and v > 0]
    assert sum(v["n_cells"] for v in p["by_cell_type"].values()) == len(live)
    assert sum(p[f]["n_cells"] for f in (1, 2)) == len(live)
    assert p[1]["n_cells"] > 1 or p[2]["n_cells"] > 1
    assert p[1]["volume"] == pytest.approx(p["by_cell_type"][1]["volume"])
