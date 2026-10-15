"""The geochemical world — og-00's vent behind canonical faces, with a ledger.

Model Upgrade plan, Phase 1 (environmental calibration) + the Process Bigraph
principle. This is the same real coupled model as
``serpentinizing_vent_reactor`` (genuine PHREEQC speciation feeding a genuine
FiPy finite-volume advection-diffusion solve), rebuilt as a *layer generator*
whose two mechanisms are selected through typed faces:

* ``model_serpentinization`` ∈ ``viva_genesis.models.model_names("serpentinization")``
  — ``"phreeqc"`` (real IPhreeqc peridotite speciation, the live default) or
  ``"reduced"`` (the tuned Gaussian source; no speciation, so the endmember pH
  is a declared hypothetical parameter rather than a result).
* ``model_spatial_transport`` ∈ ``model_names("spatial_transport")`` —
  ``"fipy"`` (Darcy-Boussinesq convecting wall, the live default),
  ``"fipy_uniform_upflow"`` (same solver, prescribed upflow, no convection) or
  ``"fenics"`` (dolfinx FEM; runs under viva-fenics's pixi env).

Both are *categorical sweep axes*: ``sweep_grid(geochemical_world,
axes={**models.axis("spatial_transport"), "flow_velocity": ...})`` produces one
decision surface per model class, and ``viva_genesis.uq.ensemble`` separates
parameter uncertainty from model-structure uncertainty on it.

A :class:`~viva_genesis.ledger.ConservationLedgerProcess` runs beside the two
world processes and publishes ``ledger/*``: integrated sources vs accumulated
pools (exact), worst-case charge and flux-divergence residuals, the heat
directionality witness and a single ``ledger_ok`` flag — the Phase-1 exit
criterion's "validated mass/charge/energy ledger".

The free parameters of the generator are exactly the ``vg-data`` package
``vent_environment`` (``viva_genesis.provenance.load_package``), so an ensemble
draw maps onto generator kwargs with ``package.to_config(values=draw)``.
"""

from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .. import models

_EMIT_PATHS = [
    "vent/temperature", "vent/pH", "vent/porosity", "vent/H2", "vent/alkalinity", "vent/heat",
    "rates/H2_flux", "rates/alkalinity_flux", "rates/heat_flux",
    "chem/pH_eq",
    "diagnostics/pe", "diagnostics/charge_imbalance", "diagnostics/flux_divergence_residual",
    "ledger/H2_in", "ledger/H2_residual", "ledger/alkalinity_in", "ledger/alkalinity_residual",
    "ledger/energy_in", "ledger/energy_residual", "ledger/charge_residual_max",
    "ledger/flux_residual_max", "ledger/energy_directionality", "ledger/ledger_ok",
    "global_time",
]

_EMIT_TYPES = {
    "temperature": "float", "pH": "float", "porosity": "float", "H2": "float",
    "alkalinity": "float", "heat": "float", "H2_flux": "float", "alkalinity_flux": "float",
    "heat_flux": "float", "pH_eq": "float", "pe": "float", "charge_imbalance": "float",
    "flux_divergence_residual": "float",
    "H2_in": "float", "H2_residual": "float", "alkalinity_in": "float",
    "alkalinity_residual": "float", "energy_in": "float", "energy_residual": "float",
    "charge_residual_max": "float", "flux_residual_max": "float",
    "energy_directionality": "float", "ledger_ok": "float", "global_time": "float",
}

_EMIT_WIRES = {
    "temperature": ["vent", "temperature"], "pH": ["vent", "pH"], "porosity": ["vent", "porosity"],
    "H2": ["vent", "H2"], "alkalinity": ["vent", "alkalinity"], "heat": ["vent", "heat"],
    "H2_flux": ["rates", "H2_flux"], "alkalinity_flux": ["rates", "alkalinity_flux"],
    "heat_flux": ["rates", "heat_flux"], "pH_eq": ["chem", "pH_eq"],
    "pe": ["diagnostics", "pe"], "charge_imbalance": ["diagnostics", "charge_imbalance"],
    "flux_divergence_residual": ["diagnostics", "flux_divergence_residual"],
    "H2_in": ["ledger", "H2_in"], "H2_residual": ["ledger", "H2_residual"],
    "alkalinity_in": ["ledger", "alkalinity_in"],
    "alkalinity_residual": ["ledger", "alkalinity_residual"],
    "energy_in": ["ledger", "energy_in"], "energy_residual": ["ledger", "energy_residual"],
    "charge_residual_max": ["ledger", "charge_residual_max"],
    "flux_residual_max": ["ledger", "flux_residual_max"],
    "energy_directionality": ["ledger", "energy_directionality"],
    "ledger_ok": ["ledger", "ledger_ok"], "global_time": ["global_time"],
}

# The reduced serpentinization class has no speciation: its endmember pH is a
# declared hypothetical parameter (provenance: hypothetical), used only so the
# FiPy transport has a pH target to relax toward on that arm.
_REDUCED_ENDMEMBER_PH = 9.5
_REDUCED_H2_RATE_AT_REFERENCE = 1.0e-3   # mol/s at olivine_rate = 0.15 (reduced class reference)


@composite_generator(
    name="geochemical_world",
    methods=["PHREEQC speciation (IPhreeqc)", "FiPy FVM advection-diffusion-reaction",
             "conservation ledger"],
    fidelity="real",
    description=(
        "og-00's real serpentinizing vent (genuine PHREEQC peridotite speciation feeding a "
        "genuine FiPy finite-volume advection-diffusion solve) rebuilt as the Phase-1 "
        "geochemical world: both mechanisms are selected through typed faces "
        "(model_serpentinization: phreeqc | reduced; model_spatial_transport: fipy convecting "
        "| fipy_uniform_upflow | fenics), so the model CLASS is a categorical sweep axis beside "
        "the physical parameters, and a ConservationLedgerProcess audits integrated sources "
        "against accumulated pools, charge balance, flux divergence and heat directionality "
        "(ledger/ledger_ok). The free parameters are the vg-data package 'vent_environment' "
        "(value-or-distribution, units, context, source, provenance class), which the "
        "environmental-calibration ensemble samples."
    ),
    parameters={
        **models.model_parameters("serpentinization", "spatial_transport",
                                  defaults={"serpentinization": "phreeqc",
                                            "spatial_transport": "fipy"}),
        "flow_velocity": {"type": "float", "default": 1.0e-3,
                          "description": "Boundary water flux through the reaction zone (m/s) [vg-data: inferred]"},
        "olivine_rate": {"type": "float", "default": 0.15,
                         "description": "Olivine reaction extent per flow-saturated step [vg-data: hypothetical]"},
        "pyroxene_fraction": {"type": "float", "default": 0.5,
                              "description": "Diopside per mole olivine (peridotite vs dunite) [vg-data: calibrated]"},
        "fe_fraction": {"type": "float", "default": 0.25,
                        "description": "Fayalite fraction of the dissolving olivine [vg-data: extrapolated]"},
        "heat_to_fluid_fraction": {"type": "float", "default": 8.0e-4,
                                   "description": "Serpentinization enthalpy retained in the fluid [vg-data: calibrated]"},
        "fluid_dic": {"type": "float", "default": 2.0e-3,
                      "description": "Inflowing-fluid DIC, Hadean-ocean proxy (molar) [vg-data: extrapolated]"},
        "nx": {"type": "integer", "default": 40,
               "description": "FiPy finite-volume cells across the interface column"},
    },
    default_n_steps=120,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def geochemical_world(core=None, *, model_serpentinization="phreeqc",
                      model_spatial_transport="fipy", flow_velocity=1.0e-3,
                      olivine_rate=0.15, pyroxene_fraction=0.5, fe_fraction=0.25,
                      heat_to_fluid_fraction=8.0e-4, fluid_dic=2.0e-3, nx=40):
    if core is None:
        core = build_core()
    serp_address = models.resolve_checked(core, "serpentinization", model_serpentinization)
    transport_address = models.resolve_checked(core, "spatial_transport", model_spatial_transport)

    if model_serpentinization == "phreeqc":
        serp_config = {"olivine_rate": float(olivine_rate),
                       "pyroxene_fraction": float(pyroxene_fraction),
                       "fe_fraction": float(fe_fraction),
                       "heat_to_fluid_fraction": float(heat_to_fluid_fraction),
                       "fluid_dic": float(fluid_dic)}
        serp_inputs = {"temperature": ["vent", "temperature"],
                       "flow_velocity": ["boundary", "flow_velocity"],
                       "DIC": ["vent", "DIC"]}
        serp_outputs = {"H2": ["vent", "H2"], "alkalinity": ["vent", "alkalinity"],
                        "heat": ["vent", "heat"],
                        "H2_flux": ["rates", "H2_flux"],
                        "alkalinity_flux": ["rates", "alkalinity_flux"],
                        "heat_flux": ["rates", "heat_flux"],
                        "pe": ["diagnostics", "pe"],
                        "pH_eq": ["chem", "pH_eq"],
                        "charge_imbalance": ["diagnostics", "charge_imbalance"]}
        ph_eq0 = 0.0
    else:
        # Reduced class: olivine_rate is read as a relative serpentinization
        # intensity (1.0e-3 mol/s at the 0.15 reference); no speciation.
        serp_config = {"h2_rate_max": _REDUCED_H2_RATE_AT_REFERENCE * float(olivine_rate) / 0.15}
        serp_inputs = {"temperature": ["vent", "temperature"],
                       "flow_velocity": ["boundary", "flow_velocity"]}
        serp_outputs = {"H2": ["vent", "H2"], "alkalinity": ["vent", "alkalinity"],
                        "heat": ["vent", "heat"],
                        "H2_flux": ["rates", "H2_flux"],
                        "alkalinity_flux": ["rates", "alkalinity_flux"],
                        "heat_flux": ["rates", "heat_flux"]}
        ph_eq0 = _REDUCED_ENDMEMBER_PH

    return {
        "serpentinization": {
            "_type": "process",
            "address": serp_address,
            "config": serp_config,
            "interval": 1.0,
            "inputs": serp_inputs,
            "outputs": serp_outputs,
        },
        "transport": {
            "_type": "process",
            "address": transport_address,
            "config": {"nx": int(nx)},
            "interval": 1.0,
            "inputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                       "porosity": ["vent", "porosity"], "H2": ["vent", "H2"],
                       "alkalinity": ["vent", "alkalinity"], "heat": ["vent", "heat"],
                       "flow_velocity": ["boundary", "flow_velocity"],
                       "pH_eq": ["chem", "pH_eq"]},
            "outputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                        "porosity": ["vent", "porosity"],
                        "flux_divergence_residual": ["diagnostics", "flux_divergence_residual"]},
        },
        "conservation_ledger": {
            "_type": "process",
            "address": "local:ConservationLedgerProcess",
            "config": {},
            "interval": 1.0,
            "inputs": {"H2": ["vent", "H2"], "alkalinity": ["vent", "alkalinity"],
                       "heat": ["vent", "heat"],
                       "H2_flux": ["rates", "H2_flux"],
                       "alkalinity_flux": ["rates", "alkalinity_flux"],
                       "heat_flux": ["rates", "heat_flux"],
                       "charge_imbalance": ["diagnostics", "charge_imbalance"],
                       "flux_divergence_residual": ["diagnostics", "flux_divergence_residual"]},
            "outputs": {k: ["ledger", k] for k in (
                "H2_in", "H2_residual", "alkalinity_in", "alkalinity_residual",
                "energy_in", "energy_residual", "charge_residual_max", "flux_residual_max",
                "energy_directionality", "ledger_ok")},
        },
        "vent": {"temperature": 300.0, "pH": 7.0, "porosity": 0.35,
                 "H2": 0.0, "alkalinity": 0.0, "heat": 0.0, "DIC": float(fluid_dic)},
        "chem": {"pH_eq": ph_eq0},
        "boundary": {"flow_velocity": float(flow_velocity)},
        "rates": {"H2_flux": 0.0, "alkalinity_flux": 0.0, "heat_flux": 0.0},
        "diagnostics": {"pe": 0.0, "charge_imbalance": 0.0, "flux_divergence_residual": 0.0},
        "ledger": {"H2_in": 0.0, "H2_residual": 0.0, "alkalinity_in": 0.0,
                   "alkalinity_residual": 0.0, "energy_in": 0.0, "energy_residual": 0.0,
                   "charge_residual_max": 0.0, "flux_residual_max": 0.0,
                   "energy_directionality": 1.0, "ledger_ok": 1.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": dict(_EMIT_TYPES)},
            "inputs": dict(_EMIT_WIRES),
        },
    }


# --------------------------------------------------------------------------- #
# Reducers (module-level, picklable) — the Phase-1 readouts of one run
# --------------------------------------------------------------------------- #
def _tail(rows, key, frac=0.25):
    n = max(1, int(round(len(rows) * frac)))
    return [float(r.get(key, float("nan"))) for r in rows[-n:]]


def settled_temperature_C(rows) -> float:
    t = _tail(rows, "temperature")
    return sum(t) / len(t) - 273.15 if t else float("nan")


def settled_pH(rows) -> float:
    t = _tail(rows, "pH")
    return sum(t) / len(t) if t else float("nan")


def settled_H2_flux(rows) -> float:
    t = _tail(rows, "H2_flux")
    return sum(t) / len(t) if t else float("nan")


def settled_pe(rows) -> float:
    t = _tail(rows, "pe")
    return sum(t) / len(t) if t else float("nan")


def dissolved_H2_mmol_kg(rows, flow_velocity: float | None = None, flux_area: float = 60.0) -> float:
    """Back out the reacted-fluid dissolved H2 (mmol/kg) from the published flux.

    ``PhreeqcSerpentinizationProcess`` publishes ``H2_flux = H2_conc * flow * area``
    (mol/s with H2_conc in mol/kgw), so ``H2_conc = H2_flux / (flow * area)``.
    ``flow_velocity`` is taken from the row's ``flow_velocity`` when present, else
    must be passed. ``flux_area`` is the process config value (default 60 m**2).
    """
    if not rows:
        return float("nan")
    flow = flow_velocity if flow_velocity is not None else rows[-1].get("flow_velocity")
    if not flow:
        return float("nan")
    return 1.0e3 * settled_H2_flux(rows) / (float(flow) * float(flux_area))


def ledger_ok_final(rows) -> float:
    return float(rows[-1].get("ledger_ok", 0.0)) if rows else float("nan")


def max_mass_residual(rows) -> float:
    return max((max(float(r.get("H2_residual", 0.0)), float(r.get("alkalinity_residual", 0.0)))
                for r in rows), default=float("nan"))


def max_energy_residual(rows) -> float:
    return max((float(r.get("energy_residual", 0.0)) for r in rows), default=float("nan"))


def energy_directionality_final(rows) -> float:
    return float(rows[-1].get("energy_directionality", 0.0)) if rows else float("nan")


def charge_residual_max(rows) -> float:
    return float(rows[-1].get("charge_residual_max", float("nan"))) if rows else float("nan")


def flux_residual_max(rows) -> float:
    return float(rows[-1].get("flux_residual_max", float("nan"))) if rows else float("nan")


PHASE1_REDUCERS = {
    "settled_temperature_C": settled_temperature_C,
    "settled_pH": settled_pH,
    "settled_H2_flux": settled_H2_flux,
    "settled_pe": settled_pe,
    "ledger_ok": ledger_ok_final,
    "max_mass_residual": max_mass_residual,
    "max_energy_residual": max_energy_residual,
    "energy_directionality": energy_directionality_final,
    "charge_residual_max": charge_residual_max,
    "flux_residual_max": flux_residual_max,
}
