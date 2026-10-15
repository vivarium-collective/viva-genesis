"""Canonical biological schemas (viva_genesis/schemas.py): every vg_* type
registers through build_core(), resolves, has parseable units, and every face
port maps onto a canonical field — the Model Upgrade plan's "every mechanism
implements a canonical interface" made a test, not a convention."""

from __future__ import annotations

import pytest

from viva_genesis import models, schemas
from viva_genesis.core import build_core


def test_all_canonical_types_registered_by_build_core():
    core = build_core()
    for name in schemas.CANONICAL_TYPES:
        assert schemas.is_registered(core, name), f"{name} did not register"
    # idempotent on a second build over the same core
    build_core(core)
    assert schemas.is_registered(core, "vg_individual")


def test_units_parse_with_pint():
    pint = pytest.importorskip("pint")
    ureg = pint.UnitRegistry()
    for name, spec in schemas.ATOMS.items():
        if isinstance(spec, dict) and "_units" in spec:
            ureg.parse_expression(spec["_units"])


def test_individual_default_has_no_heredity_until_attached():
    core = build_core()
    schema, state = core.default("vg_individual")
    assert "heredity" in core.access("vg_individual")          # the field exists (maybe[vg_heredity])
    assert state.get("heredity") is None                        # ... and is absent by default
    assert state["internal"]["dissolved"] == {}                 # one molecule pool, keyed by species
    assert core.check("vg_individual", state)


def test_map_and_maybe_forms_resolve():
    core = build_core()
    assert not isinstance(core.access("map[vg_concentration]"), str)
    assert not isinstance(core.access("maybe[vg_heredity]"), str)
    assert not isinstance(core.access("vg_lineage"), str)


def test_every_face_port_is_canonical():
    for face_name in models.FACES:
        cov = models.canonical_coverage(face_name)
        assert not cov["uncovered"], f"face {face_name} has non-canonical ports {cov['uncovered']}"


def test_bounds_metadata():
    assert schemas.bounds("vg_fraction") == (0.0, 1.0)
    assert schemas.bounds("vg_temperature") == (273.0, 673.0)
    assert schemas.bounds("vg_id") == (None, None)


def test_existing_process_units_are_atom_units():
    """Every unit string an existing process declares is one the atoms use —
    adopting the canonical atoms is a rename, not a change of physics."""
    core = build_core()
    atom_units = {s["_units"] for s in schemas.ATOMS.values() if isinstance(s, dict) and "_units" in s}
    atom_units |= {"eq/kgw", "meter**2/second", "1/(kelvin*second)", "kelvin/watt"}  # process-internal
    checked = 0
    for iface in models.interfaces():
        for name in models.model_names(iface):
            cls = models._class_for_address(core, models.resolve(iface, name))
            inst = cls(config={}, core=core)
            for port in list(inst.inputs().values()) + list(inst.outputs().values()):
                if isinstance(port, dict) and "_units" in port:
                    assert port["_units"] in atom_units, (cls.__name__, port)
                    checked += 1
    assert checked > 10


def test_species_transport_bundle_and_multisolute_species():
    """The multisolute localization refinement (plan §4.5/§6): species_params is a
    per-species transport-param bundle, not the concentration pool; the chemically
    -necessary mixture species are blessed as canonical."""
    from viva_genesis import schemas
    core = build_core()
    # the new param-bundle type registers and carries the five transport fields
    assert schemas.is_registered(core, "vg_species_transport")
    fields = schemas.schema_fields("vg_species_transport")
    assert set(fields) == {"diffusivity", "soret", "k_ads", "k_des", "k_deg"}
    # species_params now points at the param bundle map, NOT dissolved concentrations
    assert schemas.canonical_field("species_params") == "vg_molecules.transport_params"
    # the eight multisolute co-localization solutes are canonical dissolved species
    for sp in ("phosphate", "ammonium", "amino_precursor", "amphiphile",
               "nucleotide_precursor", "formate", "acetate", "pyruvate"):
        assert sp in schemas.CANONICAL_DISSOLVED_SPECIES
        assert schemas.canonical_field(sp) == f"vg_molecules.dissolved.{sp}"
