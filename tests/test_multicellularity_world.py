"""Shared CPM multicellularity world + S04 morphomechanics composite."""
import pytest

pytest.importorskip("viva_cpm")

from process_bigraph import Composite  # noqa: E402

from viva_genesis.composites.multicellularity_world import build_world_spec  # noqa: E402
from viva_genesis.core import build_core  # noqa: E402

GEN_ID = "viva_genesis.composites.multicellularity_world.s04_morphomechanics"


def _registered_ids():
    import viva_genesis  # noqa: F401  (fires the @composite_generator decorators)
    from process_bigraph import composite_spec
    return {GEN_ID} if composite_spec.get(GEN_ID) is not None else set()


def _run_generator(adhesion, updates=40):
    from viva_genesis.composites.multicellularity_world import s04_morphomechanics
    core = build_core()
    comp = Composite({"state": s04_morphomechanics(core, adhesion=adhesion)}, core=core)
    comp.run(updates)
    return comp


def test_generator_registers_with_expected_id():
    assert GEN_ID in _registered_ids()


def test_contact_matrix_populates_every_type_pair():
    spec = build_world_spec(adhesion=0.8)
    pairs = {(e["a"], e["b"]) for e in spec["contact"]}
    assert (0, 1) in pairs and (1, 1) in pairs


def test_strong_adhesion_cluster_stays_cohesive():
    comp = _run_generator(adhesion=0.95)
    assert comp.state["n_propagules"] == 1


def test_weak_adhesion_cluster_fractures_under_growth():
    comp = _run_generator(adhesion=0.15)
    assert comp.state["n_propagules"] > 1


def test_zero_differential_adhesion_forms_no_cohesive_propagule():
    comp = _run_generator(adhesion=0.0)
    assert comp.state["largest_cluster_fraction"] < 0.5
