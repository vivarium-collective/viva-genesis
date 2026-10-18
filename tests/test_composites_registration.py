"""The composites package auto-registers every submodule via a glob import.

Guards the item-4 refactor (manual ``from . import X`` append block -> pkgutil
glob): every ``*.py`` composite submodule must import cleanly and register at
least one ``@composite_generator`` in the process-bigraph registry, with no
manual list to drift.
"""
import importlib
import pkgutil

from process_bigraph.composite_generator import _REGISTRY

import viva_genesis.composites as composites


def _registered_refs():
    return {k for k in _REGISTRY if k.startswith("viva_genesis.composites.")}


def test_all_submodules_import_and_register():
    refs = _registered_refs()
    assert refs, "no composite generators registered"
    # Every submodule discovered by the glob must contribute >=1 registered generator.
    for m in pkgutil.iter_modules(composites.__path__):
        importlib.import_module(f"viva_genesis.composites.{m.name}")
        assert any(
            k.startswith(f"viva_genesis.composites.{m.name}.") for k in refs
        ), f"submodule {m.name} imported but registered no composite generator"


def test_all_is_the_submodule_set():
    submods = sorted(m.name for m in pkgutil.iter_modules(composites.__path__))
    assert composites.__all__ == submods


def test_known_spine_generators_registered():
    # The spine + families that previously needed manual appends still resolve.
    refs = _registered_refs()
    for want in (
        "vent_reactor.serpentinizing_vent_reactor",
        "open_chemical_network.open_chemical_network",
        "og_27_coupled_geochemical_reaction_interface.og_27_coupled_geochemical_reaction_interface",
        "og_29_endogenous_autocatalysis.og_29_endogenous_autocatalysis",
        "og_31_protometabolism_to_amphiphiles.og_31_protometabolism_to_amphiphiles",
    ):
        assert f"viva_genesis.composites.{want}" in refs
