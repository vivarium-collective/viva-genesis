"""S06 GroupSelectionProcess: generational cell<->population loop."""
import pytest

pytest.importorskip("viva_cpm")

from viva_genesis.core import build_core
from viva_genesis.s06_process import GroupSelectionProcess

KEYS = ("generation", "mean_adhesion", "among_group", "within_group",
        "delta_adhesion", "mean_toughness", "heritability")


def _proc(clonality, **kw):
    cfg = {"n_founders": 4, "window": 16, "region": 40, "clonality": clonality,
           "cheater_adhesion": 0.0, "seed": 3}
    cfg.update(kw)
    return GroupSelectionProcess(config=cfg, core=build_core())


@pytest.fixture(scope="module")
def clonal():
    p = _proc("clonal")
    return p, p.update({}, 1)


@pytest.fixture(scope="module")
def mixed():
    p = _proc("mixed")
    return p, p.update({}, 1)


def test_emits_all_keys(clonal):
    _, out = clonal
    assert set(out) == set(KEYS)
    assert isinstance(out["generation"], int)
    for k in KEYS[1:]:
        assert isinstance(out[k], float)


@pytest.mark.parametrize("arm", ["clonal", "mixed"])
def test_price_identity(arm, clonal, mixed):
    _, out = clonal if arm == "clonal" else mixed
    assert abs(out["among_group"] + out["within_group"] - out["delta_adhesion"]) < 1e-6


def test_clonal_within_group_zero(clonal):
    assert abs(clonal[1]["within_group"]) < 0.02


def test_division_happened(clonal, mixed):
    for p, _ in (clonal, mixed):
        assert p.last_world.n_cells() > p.last_seeded_cells


def test_no_lineage_leak(clonal, mixed):
    for p, _ in (clonal, mixed):
        allowed = set(p.last_seeded_types)
        live = {t for t, v in zip(p.last_world.cell_types()[1:],
                                  p.last_world.cell_volumes()[1:]) if v > 0}
        assert live <= allowed
