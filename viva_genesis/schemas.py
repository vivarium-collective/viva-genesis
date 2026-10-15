"""Canonical biological schemas — the units-typed ``vg_*`` shared types.

The Model Upgrade plan's Process Bigraph principle: *every upgraded mechanism
implements a canonical biological interface* (environment, minerals, molecules,
energy, boundary, individual, heredity, ecology), so a model class becomes a
categorical experimental factor — the same study can sweep model structure as
well as parameter values while the surrounding world stays fixed.

This module is that interface layer. It exports

* ``ATOMS`` — units-typed leaf types (``vg_concentration``, ``vg_temperature``,
  ...). The unit strings are exactly the ones the existing processes already
  declare, so adopting them is a rename of port declarations, not a change of
  physics.
* ``SCHEMAS`` — the eight canonical composite types (``vg_environment``,
  ``vg_minerals``, ``vg_molecules``, ``vg_energy``, ``vg_boundary``,
  ``vg_individual``, ``vg_heredity``, ``vg_lineage``). ``vg_individual.heredity``
  is ``maybe[vg_heredity]``: heredity is attached conditionally, never assumed.
* ``CANONICAL_TYPES`` = ``{**ATOMS, **SCHEMAS}`` and
  ``register_canonical_types(core)`` — called from ``viva_genesis.core.build_core``
  so every composite and test sees the types under stable names.
* ``CANONICAL_INTERFACES`` — the plan's eight interface names mapped onto the
  schema(s) a model class on that interface produces.
* ``PORT_TO_CANONICAL`` — the mapping from existing process port names to the
  canonical ``schema.field`` they realise (plan 1.4 / integration doc 1.4). This
  is what ``viva_genesis.models`` uses to check that a face is expressible in
  canonical terms, and what the migration wrappers will read.

Nothing heavy is imported here: ``build_core`` walks this module and types must
never be missing.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Atoms: units-typed leaves
# --------------------------------------------------------------------------- #
ATOMS: dict[str, dict | str] = {
    "vg_concentration": {"_type": "float", "_units": "molar", "_min": 0.0},
    "vg_amount": {"_type": "float", "_units": "mole", "_min": 0.0},
    "vg_rate": {"_type": "float", "_units": "mole/second"},
    "vg_flux_density": {"_type": "float", "_units": "mole/meter**2/second"},
    "vg_temperature": {"_type": "float", "_units": "kelvin", "_min": 273.0, "_max": 673.0},
    "vg_pressure": {"_type": "float", "_units": "pascal", "_min": 1.0e5, "_max": 5.0e7},
    "vg_ph": {"_type": "float", "_units": "dimensionless", "_min": 0.0, "_max": 14.0},
    "vg_fraction": {"_type": "float", "_units": "dimensionless", "_min": 0.0, "_max": 1.0},
    "vg_potential": {"_type": "float", "_units": "volt"},
    "vg_current_density": {"_type": "float", "_units": "ampere/meter**2"},
    "vg_conductivity": {"_type": "float", "_units": "siemens/meter", "_min": 0.0},
    "vg_free_energy": {"_type": "float", "_units": "kilojoule/mole"},
    "vg_power": {"_type": "float", "_units": "watt"},
    "vg_energy_amount": {"_type": "float", "_units": "joule"},
    "vg_length": {"_type": "float", "_units": "meter", "_min": 0.0},
    "vg_area": {"_type": "float", "_units": "meter**2", "_min": 0.0},
    "vg_volume": {"_type": "float", "_units": "liter", "_min": 0.0},
    "vg_velocity": {"_type": "float", "_units": "meter/second"},
    "vg_permeability": {"_type": "float", "_units": "meter/second", "_min": 0.0},
    "vg_time": {"_type": "float", "_units": "second", "_min": 0.0},
    "vg_per_second": {"_type": "float", "_units": "1/second"},
    "vg_diffusivity": {"_type": "float", "_units": "meter**2/second", "_min": 0.0},
    "vg_soret": {"_type": "float", "_units": "1/kelvin"},
    "vg_tension": {"_type": "float", "_units": "newton/meter", "_min": 0.0},
    "vg_information": {"_type": "float", "_units": "bit", "_min": 0.0},
    # electrochemical interface (Phase 2): areal (per-unit-area) resistance of a
    # mineral layer / charge-transfer step, and the charge passed through it.
    "vg_areal_resistance": {"_type": "float", "_units": "ohm*meter**2", "_min": 0.0},
    "vg_charge": {"_type": "float", "_units": "coulomb"},
    "vg_count": {"_type": "integer", "_min": 0},
    "vg_id": "string",
}

# --------------------------------------------------------------------------- #
# The eight canonical schemas (plan: environment, minerals, molecules, energy,
# boundary, individual, heredity, ecology/lineage)
# --------------------------------------------------------------------------- #
SCHEMAS: dict[str, dict] = {
    # ---- layer 1: physical world ----------------------------------------
    "vg_environment": {
        "temperature": "vg_temperature",
        "pressure": "vg_pressure",
        "pH": "vg_ph",
        "pH_ocean": "vg_ph",
        "ionic_strength": "vg_concentration",
        "flow_velocity": "vg_velocity",
        "porosity": "vg_fraction",
        "pore_length": "vg_length",
        "residence_time": "vg_time",
        "heat": "vg_power",
    },
    "vg_minerals": {
        "phase_abundance": "map[vg_amount]",
        "surface_area": "vg_area",
        "catalytic_sites": "vg_amount",
        "fes_activity": "vg_fraction",
        "conductivity": "vg_conductivity",
        "passivation": "vg_fraction",
        "porosity_feedback": "vg_fraction",
        # electrochemical interface (Phase 2): the catalytic phase's elemental
        # composition (e.g. Ni mole fraction of the Fe/Ni alloy or sulfide), the
        # thickness of the conducting mineral layer and its areal resistance.
        "composition": "map[vg_fraction]",
        "layer_thickness": "vg_length",
        "areal_resistance": "vg_areal_resistance",
    },
    # Per-species transport-parameter bundle behind the spatial_transport
    # `species_params` port — the physics a multisolute pore model needs per
    # solute (NOT a concentration): molecular diffusivity, Soret/thermophoretic
    # coefficient, adsorption/desorption and first-order degradation rates.
    # Defined before vg_molecules so its `map[vg_species_transport]` field
    # resolves in the single register_types pass.
    "vg_species_transport": {
        "diffusivity": "vg_diffusivity",
        "soret": "vg_soret",
        "k_ads": "vg_per_second",
        "k_des": "vg_per_second",
        "k_deg": "vg_per_second",
    },
    "vg_molecules": {
        "dissolved": "map[vg_concentration]",
        "adsorbed": "map[vg_concentration]",
        "polymers": "map[vg_concentration]",
        "catalysts": "map[vg_fraction]",
        # per-species transport physics (multisolute localization, plan §4.5/§6):
        # each solute carries its own diffusion + Soret + adsorption/degradation
        # parameters, keyed by the same species names as `dissolved`.
        "transport_params": "map[vg_species_transport]",
    },
    "vg_energy": {
        "redox_potential": "vg_potential",
        "electric_potential": "vg_potential",
        "pmf": "vg_potential",
        "pmf_open": "vg_potential",
        "current_density": "vg_current_density",
        "ion_gradients": "map[vg_concentration]",
        "stored_work": "vg_energy_amount",
        "dissipated": "vg_energy_amount",
        "energy_charge": "vg_fraction",
        "drive_free_energy": "vg_free_energy",
        # electrochemical interface (Phase 2): the galvanic cell the vent wall
        # forms — open-circuit emf, the overpotential the load develops, the
        # electron flux through the mineral, the faradaic efficiency (fraction
        # of electrons reaching carbon products), the fraction of the emf that
        # is delivered across the catalytic interfaces, and the charge passed.
        "emf": "vg_potential",
        "overpotential": "vg_potential",
        "electron_flux": "vg_rate",
        "faradaic_efficiency": "vg_fraction",
        "delivered_fraction": "vg_fraction",
        "charge_passed": "vg_charge",
    },
    # ---- layer 2: boundary ---------------------------------------------
    "vg_boundary": {
        "area": "vg_area",
        "composition": "map[vg_fraction]",
        "permeability": "map[vg_permeability]",
        "charge": "vg_potential",
        "integrity": "vg_fraction",
        "tension": "vg_tension",
    },
    # ---- layer 4 (declared before the individual that embeds it) ---------
    "vg_heredity": {
        "mode": "string",
        "inherited_state": "map[vg_fraction]",
        "sequence": "maybe[string]",
        "fidelity": "vg_fraction",
        "mutation_rate": "vg_per_second",
        "information_content": "vg_information",
        "heritability": "vg_fraction",
    },
    # ---- layer 3: individual -------------------------------------------
    "vg_individual": {
        "id": "vg_id",
        "volume": "vg_volume",
        "internal": "vg_molecules",
        "boundary": "vg_boundary",
        "energy": "vg_energy",
        "maintenance_flux": "vg_power",
        "growth_rate": "vg_per_second",
        "division_state": "vg_fraction",
        "persistence": "vg_time",
        "autonomy": "vg_fraction",
        "heredity": "maybe[vg_heredity]",
    },
    # ---- layer 4: lineage / ecology ------------------------------------
    "vg_lineage": {
        "parent_id": "vg_id",
        "lineage_id": "vg_id",
        "generation": "vg_count",
        "position": "tuple[vg_length,vg_length]",
        "uptake": "map[vg_rate]",
        "secretion": "map[vg_rate]",
        "interaction": "map[vg_fraction]",
    },
}

CANONICAL_TYPES: dict[str, dict | str] = {**ATOMS, **SCHEMAS}

# The canonical dissolved-species names keying ``vg_molecules.dissolved`` /
# ``.transport_params``. The first block are the vent/network solutes already in
# use; the second is the chemically-necessary mixture a multisolute pore model
# must co-localize (plan §6 — phosphate/ammonium/amino/amphiphile/nucleotide).
CANONICAL_DISSOLVED_SPECIES: tuple[str, ...] = (
    "H2", "CO2", "DIC", "alkalinity", "formate", "acetate", "pyruvate",
    "phosphate", "ammonium", "amino_precursor", "amphiphile", "nucleotide_precursor",
)

# The plan's eight canonical interfaces -> the schema(s) a model class on that
# interface reads/produces. A model class "implements" an interface when every
# port it declares maps (via PORT_TO_CANONICAL) onto a field of these schemas.
CANONICAL_INTERFACES: dict[str, tuple[str, ...]] = {
    "environment": ("vg_environment",),
    "minerals": ("vg_minerals",),
    "molecules": ("vg_molecules",),
    "energy": ("vg_energy",),
    "boundary": ("vg_boundary",),
    "individual": ("vg_individual",),
    "heredity": ("vg_heredity",),
    "ecology": ("vg_lineage",),
}

# Existing process port names -> canonical ``schema.field`` (integration doc 1.4).
# Diagnostics / solver witnesses map to the ``ledger`` / ``diagnostics`` namespaces,
# which are not biological schemas but are required by the numerical-verification
# method of the plan (section 11) — they are listed so a face can be audited as
# "every port is either canonical or a declared diagnostic".
PORT_TO_CANONICAL: dict[str, str] = {
    # environment
    "temperature": "vg_environment.temperature",
    "pressure": "vg_environment.pressure",
    "pH": "vg_environment.pH",
    "pH_vent": "vg_environment.pH",
    "pH_eq": "vg_environment.pH",
    "pH_ocean": "vg_environment.pH_ocean",
    "ionic_strength": "vg_environment.ionic_strength",
    "flow_velocity": "vg_environment.flow_velocity",
    "porosity": "vg_environment.porosity",
    "pore_length": "vg_environment.pore_length",
    "residence_time": "vg_environment.residence_time",
    "heat": "vg_environment.heat",
    "temperature_field": "vg_environment.temperature",
    "velocity": "vg_environment.flow_velocity",
    "geometry": "vg_minerals",
    # molecules (single dissolved pool keyed by species)
    "H2": "vg_molecules.dissolved.H2",
    "CO2": "vg_molecules.dissolved.CO2",
    "DIC": "vg_molecules.dissolved.DIC",
    "alkalinity": "vg_molecules.dissolved.alkalinity",
    "formate": "vg_molecules.dissolved.formate",
    "acetate": "vg_molecules.dissolved.acetate",
    "pyruvate": "vg_molecules.dissolved.pyruvate",
    # the chemically-necessary mixture for multisolute co-localization (plan §6)
    "phosphate": "vg_molecules.dissolved.phosphate",
    "ammonium": "vg_molecules.dissolved.ammonium",
    "amino_precursor": "vg_molecules.dissolved.amino_precursor",
    "amphiphile": "vg_molecules.dissolved.amphiphile",
    "nucleotide_precursor": "vg_molecules.dissolved.nucleotide_precursor",
    "sources": "vg_molecules.dissolved",
    # per-species transport physics bundle (NOT the concentration pool)
    "species_params": "vg_molecules.transport_params",
    "fields": "vg_molecules.dissolved",
    "enrichment": "vg_molecules.dissolved",
    "enrichment_factor": "vg_molecules.dissolved",
    # rates (world-side fluxes are rates on the molecule pool)
    "H2_flux": "vg_molecules.dissolved.H2",
    "alkalinity_flux": "vg_molecules.dissolved.alkalinity",
    "heat_flux": "vg_environment.heat",
    "net_carbon_flux": "vg_molecules.dissolved",
    # thermodynamic feasibility multipliers (eQuilibrator dG' realised as a 0-1 drive)
    "feasible_formate": "vg_energy.drive_free_energy",
    "feasible_acetate": "vg_energy.drive_free_energy",
    "feasible_pyruvate": "vg_energy.drive_free_energy",
    # minerals
    "catalyst_activity": "vg_minerals.catalytic_sites",
    "fes_activity": "vg_minerals.fes_activity",
    "conductivity": "vg_minerals.conductivity",
    "ni_fraction": "vg_minerals.composition.Ni",
    "layer_thickness": "vg_minerals.layer_thickness",
    "areal_resistance": "vg_minerals.areal_resistance",
    "charge_transfer_resistance": "vg_minerals.areal_resistance",
    # energy
    "pe": "vg_energy.redox_potential",
    "electric_potential": "vg_energy.electric_potential",
    "pmf": "vg_energy.pmf",
    "pmf_open": "vg_energy.pmf_open",
    "current_density": "vg_energy.current_density",
    "drive_free_energy": "vg_energy.drive_free_energy",
    "energy_stored": "vg_energy.stored_work",
    "energy_dissipated": "vg_energy.dissipated",
    "energy_charge_fraction": "vg_energy.energy_charge",
    # electrochemical interface (Phase 2, carbon_fixation face)
    "emf": "vg_energy.emf",
    "overpotential": "vg_energy.overpotential",
    "faradaic_efficiency": "vg_energy.faradaic_efficiency",
    "electron_flux": "vg_energy.electron_flux",
    "carbon_electron_flux": "vg_energy.electron_flux",
    "her_electron_flux": "vg_energy.electron_flux",
    "gradient_efficiency": "vg_energy.delivered_fraction",
    "charge_passed": "vg_energy.charge_passed",
    # boundary / individual
    "membrane_area": "vg_boundary.area",
    "permeability": "vg_boundary.permeability",
    "lysed": "vg_boundary.integrity",
    "volume": "vg_individual.volume",
    "compartment_volume": "vg_individual.volume",
    "internalization": "vg_individual.autonomy",
    "net_growth": "vg_individual.growth_rate",
    # heredity / lineage
    "heritability": "vg_heredity.heritability",
    "information_retention": "vg_heredity.information_content",
    "lineage_depth": "vg_lineage.generation",
    # diagnostics / numerical-verification witnesses (not biology; declared)
    "charge_imbalance": "ledger.charge_residual",
    "charge_residual": "ledger.charge_residual",
    "iv_residual": "ledger.iv_residual",
    "flux_divergence_residual": "ledger.flux_residual",
    "accumulation_peclet": "diagnostics.accumulation_peclet",
    # Phase-2 failure-mode attribution: the fraction of the ideal driving force
    # lost to each limitation, and the dominant one as an integer code.
    "loss_thermodynamic": "diagnostics.loss_thermodynamic",
    "loss_electrical": "diagnostics.loss_electrical",
    "loss_catalytic": "diagnostics.loss_catalytic",
    "loss_transport": "diagnostics.loss_transport",
    "limitation_code": "diagnostics.limitation",
    "shunt_fraction": "diagnostics.shunt_fraction",
}


def canonical_field(port: str) -> str | None:
    """Return the canonical ``schema.field`` a port name realises, or ``None``."""
    return PORT_TO_CANONICAL.get(port)


def schema_fields(name: str) -> dict:
    """Return the field dict of a canonical schema (``KeyError`` if unknown)."""
    return SCHEMAS[name]


def bounds(name: str) -> tuple[float | None, float | None]:
    """Declared ``(_min, _max)`` of an atom (``(None, None)`` if unbounded).

    bigraph-schema 1.8.x realises ``Float`` with ``_units`` but does not keep
    ``_min``/``_max`` on the type object, so the bounds in ``ATOMS`` are contract
    metadata (they mirror the ``contract.face`` bounds the studies declare), read
    here by the provenance layer and the schema tests rather than enforced by
    ``core.check``.
    """
    schema = ATOMS.get(name)
    if not isinstance(schema, dict):
        return (None, None)
    return (schema.get("_min"), schema.get("_max"))


def is_registered(core, name: str) -> bool:
    """True when ``name`` resolves to a realised type in ``core``.

    ``core.access`` returns the bare string for an unknown type name rather than
    raising, so "registered" means "access did not hand the name back".
    """
    try:
        found = core.access(name)
    except Exception:
        return False
    return not isinstance(found, str)


def register_canonical_types(core):
    """Register every ``vg_*`` type into ``core`` (idempotent).

    bigraph-schema's ``register_types`` resolves string references between the
    entries, so atoms and schemas register in one call. Types already present
    (a second ``build_core`` on the same core, or a core another package
    pre-populated) are left untouched.
    """
    pending = {name: schema for name, schema in CANONICAL_TYPES.items()
               if not is_registered(core, name)}
    if pending:
        core.register_types(pending)
    return core


__all__ = [
    "ATOMS", "SCHEMAS", "CANONICAL_TYPES", "CANONICAL_INTERFACES",
    "CANONICAL_DISSOLVED_SPECIES",
    "PORT_TO_CANONICAL", "canonical_field", "schema_fields", "bounds",
    "is_registered", "register_canonical_types",
]
