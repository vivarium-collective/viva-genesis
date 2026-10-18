"""Study 33 (Gate D, first half) — Chemically Coupled Growth & Division.

Couples study 32's self-maintaining protocell (the Gate-B pore-concentrated A1
network + MD-informed membrane) to amphiphile-driven membrane growth and division
at a MEASURED critical-geometry threshold (⚑2, Option B; grounded in hanczyc2003 /
budin2012 growth-division geometries). Full coarse-grained membrane mechanics
(viva-md-membrane) is the gold-standard follow-on (og-33a), NOT built here.

The membrane AREA grows from the metabolism's productive flux (amphiphile supply);
as area outpaces the enclosed volume the reduced volume falls, and at the measured
critical reduced volume the compartment DIVIDES — a geometric event, not an imposed
rule. ``coupled=True`` drives area growth from the real metabolic flux (so division
RATE scales with metabolism); ``coupled=False`` is the growth-decoupled matched
null (fixed external amphiphile supply, flux-independent). ``imposed_division=True``
is the imposed-rule control.

Guardrail: the metabolism is the sustained A1 carbon-fixing network, NOT
autocatalytic (A2 refuted) — growth is funded by carbon fixation, not
self-amplification. Daughters count as viable only if they resume the study-32
self-maintenance criterion (net amphiphile production >= degradation).

Reuses :func:`og_32_first_self_maintaining_protocell` for the real metabolism +
MD-informed membrane; the growth/division layer is the ``GrowthDivisionProcess``
wired to read the metabolism's ``flux/net_carbon_flux``.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .og_32_first_self_maintaining_protocell import og_32_first_self_maintaining_protocell


@composite_generator(
    name="og_33_chemically_coupled_growth_and_division",
    methods=["study-32 self-maintaining protocell (A1 network + MD-informed membrane)",
             "amphiphile-driven membrane area growth", "division at a measured critical-geometry threshold",
             "growth-decoupled / imposed-division matched nulls"],
    fidelity="real",
    description=(
        "Gate D first half: couples study 32's self-maintaining protocell to amphiphile-driven membrane "
        "growth and division at a MEASURED critical-geometry (reduced-volume) threshold (hanczyc/budin; "
        "⚑2 Option B, NOT CG membrane mechanics - that is og-33a). Membrane area grows from the metabolism's "
        "productive flux; at the measured critical reduced volume the compartment divides (geometry, not an "
        "imposed rule). coupled=False is the growth-decoupled null (fixed amphiphile supply); "
        "imposed_division=True is the imposed-rule null. Daughters viable only if they resume study-32 "
        "self-maintenance. Metabolism = sustained A1 network, NOT autocatalytic (A2 refuted)."
    ),
    parameters={
        "coupled": {"type": "boolean", "default": True,
                    "description": "Growth driven by metabolic flux (True) vs growth-decoupled null (False)"},
        "imposed_division": {"type": "boolean", "default": False,
                             "description": "Divide on a fixed timer (imposed-rule null) vs measured geometry"},
        "composition": {"type": "string", "default": "long_di-C16",
                        "description": "MD amphiphile composition for the study-32 membrane"},
        "base_CO2": {"type": "float", "default": 1.0e-3, "description": "Bulk precursor CO2 (molar) — equal across arms"},
        "base_H2": {"type": "float", "default": 1.0e-3, "description": "Bulk precursor H2 (molar) — equal across arms"},
        "porosity": {"type": "float", "default": 0.88, "description": "Gate-B pore porosity"},
        "k_wash": {"type": "float", "default": 0.05, "description": "Base CSTR washout (1/s)"},
        "max_carbons": {"type": "integer", "default": 4, "description": "Carbon cap of the reaction universe"},
    },
    default_n_steps=160,
    preferred_time="6 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["flux/net_carbon_flux", "net/total_organic_carbon",
                         "gd/membrane_area", "gd/reduced_volume", "gd/division_count",
                         "gd/division_rate", "gd/daughter_viable"]}],
)
def og_33_chemically_coupled_growth_and_division(
        core=None, *, coupled=True, imposed_division=False, composition="long_di-C16",
        base_CO2=1.0e-3, base_H2=1.0e-3, porosity=0.88, k_wash=0.05, max_carbons=4):
    if core is None:
        core = build_core()
    # study-32 self-maintaining protocell (real metabolism + MD-informed membrane).
    doc = og_32_first_self_maintaining_protocell(
        core, membrane=True, composition=composition, base_CO2=float(base_CO2),
        base_H2=float(base_H2), porosity=float(porosity), k_wash=float(k_wash), max_carbons=int(max_carbons))

    # Growth/division layer: reads the metabolism's productive flux, grows membrane
    # area, divides at the measured critical geometry. coupled=False -> growth-decoupled.
    doc["growth"] = {
        "_type": "process",
        "address": "local:GrowthDivisionProcess",
        "config": {"coupled": bool(coupled), "imposed_division": bool(imposed_division)},
        "interval": 1.0,
        "inputs": {"productive_flux": ["flux", "net_carbon_flux"]},
        "outputs": {
            "membrane_area": ["gd", "membrane_area"],
            "enclosed_volume": ["gd", "enclosed_volume"],
            "reduced_volume": ["gd", "reduced_volume"],
            "area_to_volume_ratio": ["gd", "area_to_volume_ratio"],
            "division_count": ["gd", "division_count"],
            "division_event": ["gd", "division_event"],
            "division_rate": ["gd", "division_rate"],
            "amphiphile_production_rate": ["gd", "amphiphile_production_rate"],
            "daughter_viable": ["gd", "daughter_viable"],
        },
    }
    doc["gd"] = {"membrane_area": 0.0, "enclosed_volume": 0.0, "reduced_volume": 0.0,
                 "area_to_volume_ratio": 0.0, "division_count": 0, "division_event": 0,
                 "division_rate": 0.0, "amphiphile_production_rate": 0.0, "daughter_viable": 0.0}

    # Extend the emitter with the growth/division observables.
    doc["emitter"]["config"]["emit"].update({
        "membrane_area": "float", "reduced_volume": "float", "division_count": "integer",
        "division_rate": "float", "daughter_viable": "float"})
    doc["emitter"]["inputs"].update({
        "membrane_area": ["gd", "membrane_area"], "reduced_volume": ["gd", "reduced_volume"],
        "division_count": ["gd", "division_count"], "division_rate": ["gd", "division_rate"],
        "daughter_viable": ["gd", "daughter_viable"]})
    return doc
