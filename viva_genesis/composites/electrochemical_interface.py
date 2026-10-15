"""The electrochemical interface — og-01's carbon fixation behind the Phase-2 face.

Model Upgrade plan, Phase 2 (*electrochemical carbon fixation*). This is the
og-01 world (alkaline H2-rich vent fluid | Fe/Ni-sulfide wall | acidic
CO2-bearing ocean, the real FiPy Nernst-Planck proton gradient, the eQuilibrator
ΔG' gate) rebuilt as a *layer generator* whose carbon-fixation mechanism is
selected through the typed ``carbon_fixation`` face:

* ``model_carbon_fixation = "empirical"`` — og-01's lab-calibrated gated
  kinetics (``EmpiricalCarbonFixationProcess``), fed by the proton budget's
  loaded pmf, with ``gradient_efficiency`` no longer a knob but **derived** by
  ``MineralConductivityProcess`` from the wall's conductivity, thickness,
  porosity and the electrodes' charge-transfer resistance;
* ``"butler_volmer"`` — the galvanic-cell class
  (``ButlerVolmerCarbonFixationProcess``): Nernst potentials from the fluid
  redox state, Butler-Volmer kinetics, the ohmic mineral + ionic circuit, the
  faradaic split; the gradient efficiency is emergent;
* ``"microkinetic"`` — CatMAP/Cantera adsorbate microkinetics (builds here,
  runs under pixi).

The four physical axes of the Phase-2 mechanism map — vent pH, dissolved H2,
mineral conductivity, Ni fraction — are generator kwargs bound to the vg-data
package ``electrochemical_interface``; a ``ChargeLedgerProcess`` audits every
class's electron balance (Kirchhoff residual, faradaic efficiency ≤ 1,
current-voltage residual) and publishes ``ledger/charge_ledger_ok``. Every
class publishes the four loss fractions + ``limitation_code`` that the
``failure-mode-attributed`` gate compares across classes.
"""

from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .. import models
from ..electrochemistry.butler_volmer import LIMITATION_NAMES, limitation_label
from ..electrochemistry.mineral_conductivity import circuit_efficiency

_EMIT_WIRES = {
    "formate": ["products", "formate"], "acetate": ["products", "acetate"], "pyruvate": ["products", "pyruvate"],
    "net_carbon_flux": ["flux", "net_carbon_flux"],
    "delta_pH": ["electro", "delta_pH"], "pmf_open": ["electro", "pmf_open"], "pmf": ["electro", "pmf"],
    "proton_current_density": ["electro", "proton_current_density"],
    "flux_divergence_residual": ["electro", "flux_divergence_residual"],
    "charge_state": ["electro", "charge_state"],
    "gradient_efficiency": ["circuit", "gradient_efficiency"],
    "areal_resistance": ["circuit", "areal_resistance"],
    "charge_transfer_resistance": ["circuit", "charge_transfer_resistance"],
    "current_density": ["electro", "current_density"], "emf": ["electro", "emf"],
    "overpotential": ["electro", "overpotential"], "faradaic_efficiency": ["electro", "faradaic_efficiency"],
    "electron_flux": ["electro", "electron_flux"], "carbon_electron_flux": ["electro", "carbon_electron_flux"],
    "her_electron_flux": ["electro", "her_electron_flux"], "iv_residual": ["electro", "iv_residual"],
    "feasible_formate": ["gibbs", "feasible_formate"], "dg_formate": ["gibbs", "dg_formate"],
    "loss_thermodynamic": ["diagnostics", "loss_thermodynamic"], "loss_electrical": ["diagnostics", "loss_electrical"],
    "loss_catalytic": ["diagnostics", "loss_catalytic"], "loss_transport": ["diagnostics", "loss_transport"],
    "limitation_code": ["diagnostics", "limitation_code"],
    "charge_residual": ["ledger", "charge_residual"], "charge_residual_max": ["ledger", "charge_residual_max"],
    "ledger_faradaic_efficiency": ["ledger", "faradaic_efficiency"],
    "faradaic_efficiency_max": ["ledger", "faradaic_efficiency_max"], "iv_residual_max": ["ledger", "iv_residual_max"],
    "charge_passed": ["ledger", "charge_passed"], "electrons_to_carbon": ["ledger", "electrons_to_carbon"],
    "charge_ledger_ok": ["ledger", "charge_ledger_ok"],
    "global_time": ["global_time"],
}
_EMIT_TYPES = {k: "float" for k in _EMIT_WIRES}
_EMIT_PATHS = ["/".join(v) for v in _EMIT_WIRES.values()]

_CHARGE_LEDGER_OUT = ("charge_residual", "charge_residual_max", "faradaic_efficiency", "faradaic_efficiency_max",
                      "iv_residual_max", "charge_passed", "electrons_to_carbon", "charge_ledger_ok")


@composite_generator(
    name="electrochemical_carbon_fixation",
    methods=["FiPy FVM Nernst-Planck", "eQuilibrator ΔG′", "Nernst + Butler-Volmer galvanic cell",
             "circuit-derived gradient efficiency", "charge + electron ledger"],
    fidelity="real",
    description=(
        "og-01's H2/pH-driven carbon fixation rebuilt as the Phase-2 electrochemical interface: "
        "the carbon-fixation mechanism is a model CLASS on the carbon_fixation face "
        "(model_carbon_fixation: empirical | butler_volmer | microkinetic). The empirical class is "
        "og-01's lab-calibrated gated kinetics driven by the real FiPy Nernst-Planck proton gradient "
        "+ proton budget, with gradient_efficiency DERIVED from the wall's circuit "
        "(MineralConductivityProcess: conductivity, thickness, porosity vs the electrodes' charge-"
        "transfer resistance) instead of a knob. The butler_volmer class solves the vent wall as a "
        "galvanic cell each tick (Nernst half-cell potentials from the fluid redox state, Butler-"
        "Volmer kinetics scaled by catalyst activity / Ni fraction / T, Koutecky-Levich transport "
        "limits, the ohmic mineral + ionic path, the faradaic split over formate / acetate / "
        "pyruvate calibrated to the Altair-2025 current window and the Preiner-2020 yield "
        "hierarchy). The microkinetic class (CatMAP/Cantera) builds here and runs under pixi. Every "
        "class publishes the thermodynamic / electrical / catalytic / transport loss fractions and "
        "a limitation code, and a ChargeLedgerProcess audits its electron balance (Kirchhoff "
        "residual, faradaic efficiency <= 1, current-voltage residual -> ledger/charge_ledger_ok). "
        "Free parameters are the vg-data package 'electrochemical_interface'."
    ),
    parameters={
        **models.model_parameters("carbon_fixation", defaults={"carbon_fixation": "butler_volmer"}),
        "ph_vent": {"type": "float", "default": 9.5, "description": "Alkaline vent-side pH (from og-00)"},
        "ph_ocean": {"type": "float", "default": 6.0, "description": "Acidic early-ocean-side pH"},
        "h2": {"type": "float", "default": 5.0e-3, "description": "Dissolved H2 feed, vent side (M)"},
        "co2": {"type": "float", "default": 2.0e-3, "description": "Dissolved CO2 feed, ocean side (M)"},
        "temperature": {"type": "float", "default": 373.15, "description": "Interface temperature (K)"},
        "conductivity": {"type": "float", "default": 1.0e-3,
                         "description": "Electronic conductivity of the mineral layer (S/m) [vg-data: extrapolated]"},
        "layer_thickness": {"type": "float", "default": 1.0e-3,
                            "description": "Mineral layer thickness (m) [vg-data: inferred]"},
        "ni_fraction": {"type": "float", "default": 0.75,
                        "description": "Ni mole fraction of the Fe/Ni catalytic phase (0 greigite .. 0.75 awaruite) [vg-data: measured]"},
        "porosity": {"type": "float", "default": 0.35, "description": "Wall porosity (ionic return path)"},
        "catalyst_active": {"type": "float", "default": 1.0,
                            "description": "Active Fe/Ni/S mineral catalyst fraction (0 = no-catalyst control)"},
        "j0_co2": {"type": "float", "default": 1.0e-5,
                   "description": "CO2-reduction exchange current density at Ni3Fe, 100 C (A/m^2) [vg-data: calibrated]"},
        "boundary_layer": {"type": "float", "default": 1.0e-3,
                           "description": "Diffusion boundary layer at the electrodes (m) [vg-data: inferred]"},
        "dilution_rate": {"type": "float", "default": 0.0,
                          "description": "Open-flow washout (1/s); 0 = closed batch, >0 = sustained-throughput regime"},
        "nx": {"type": "integer", "default": 20, "description": "FiPy cells across the Nernst-Planck barrier"},
    },
    visualizations=[
        {"name": "electrochemistry-polarization", "address": "local:ElectrochemistryPolarization",
         "config": {"title": "Vent wall as a galvanic cell: polarization and loss partition"}},
    ],
    default_n_steps=60,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def electrochemical_carbon_fixation(core=None, *, model_carbon_fixation="butler_volmer",
                                    ph_vent=9.5, ph_ocean=6.0, h2=5.0e-3, co2=2.0e-3, temperature=373.15,
                                    conductivity=1.0e-3, layer_thickness=1.0e-3, ni_fraction=0.75,
                                    porosity=0.35, catalyst_active=1.0, j0_co2=1.0e-5, boundary_layer=1.0e-3,
                                    dilution_rate=0.0, nx=20):
    if core is None:
        core = build_core()
    fixation_address = models.resolve_checked(core, "carbon_fixation", model_carbon_fixation)
    # process-bigraph's is_empty(Float, 0.0) refills an exact 0.0 with the port
    # default, which would silently re-enable the no-catalyst control (og-01 gotcha).
    catalyst_active = max(float(catalyst_active), 1.0e-6)
    ni_fraction = max(float(ni_fraction), 1.0e-6)        # same gotcha: an Fe-only phase is 0.0
    ionic_strength = 0.25

    # The circuit-derived usable fraction of the gradient (replaces og-01's knob).
    circuit = circuit_efficiency(conductivity=conductivity, layer_thickness=layer_thickness, porosity=porosity,
                                 ionic_strength=ionic_strength, temperature=temperature,
                                 catalyst_activity=catalyst_active, ni_fraction=ni_fraction, j0_co2_ref=j0_co2)

    doc = {
        "conductivity": {
            "_type": "process", "address": "local:MineralConductivityProcess",
            "config": {"j0_co2_ref": float(j0_co2)}, "interval": 1.0,
            "inputs": {"conductivity": ["minerals", "conductivity"], "layer_thickness": ["minerals", "layer_thickness"],
                       "porosity": ["minerals", "porosity"], "ionic_strength": ["env", "ionic_strength"],
                       "temperature": ["env", "temperature"], "catalyst_activity": ["catalyst", "active"],
                       "ni_fraction": ["minerals", "ni_fraction"]},
            "outputs": {"gradient_efficiency": ["circuit", "gradient_efficiency"],
                        "areal_resistance": ["circuit", "areal_resistance"],
                        "charge_transfer_resistance": ["circuit", "charge_transfer_resistance"],
                        "shunt_fraction": ["circuit", "shunt_fraction"]},
        },
        "gradient": {
            "_type": "process", "address": "local:PhGradientNernstPlanckProcess",
            "config": {"gradient_efficiency": float(circuit["gradient_efficiency"]), "nx": int(nx)},
            "interval": 1.0,
            "inputs": {"pH_vent": ["env", "pH"], "pH_ocean": ["env", "pH_ocean"], "temperature": ["env", "temperature"]},
            "outputs": {"delta_pH": ["electro", "delta_pH"], "pmf": ["electro", "pmf_open"],
                        "electric_potential": ["electro", "electric_potential"],
                        "current_density": ["electro", "proton_current_density"],
                        "flux_divergence_residual": ["electro", "flux_divergence_residual"]},
        },
        "charge_ledger": {
            "_type": "process", "address": "local:ChargeLedgerProcess", "config": {}, "interval": 1.0,
            "inputs": {"electron_flux": ["electro", "electron_flux"],
                       "carbon_electron_flux": ["electro", "carbon_electron_flux"],
                       "her_electron_flux": ["electro", "her_electron_flux"],
                       "iv_residual": ["electro", "iv_residual"]},
            "outputs": {k: ["ledger", k] for k in _CHARGE_LEDGER_OUT},
        },
        "env": {"pH": float(ph_vent), "pH_ocean": float(ph_ocean), "ionic_strength": ionic_strength,
                "temperature": float(temperature), "H2": float(h2), "CO2": float(co2)},
        "minerals": {"conductivity": float(conductivity), "layer_thickness": float(layer_thickness),
                     "ni_fraction": float(ni_fraction), "porosity": float(porosity)},
        "catalyst": {"active": catalyst_active},
        "circuit": {"gradient_efficiency": float(circuit["gradient_efficiency"]),
                    "areal_resistance": float(circuit["areal_resistance"]),
                    "charge_transfer_resistance": float(circuit["charge_transfer_resistance"]),
                    "shunt_fraction": float(circuit["shunt_fraction"])},
        "electro": {"delta_pH": 0.0, "pmf": 0.0, "pmf_open": 0.0, "electric_potential": 0.0,
                    "proton_current_density": 0.0, "flux_divergence_residual": 0.0,
                    "charge_state": 1.0, "proton_reservoir": 0.0, "proton_draw": 0.0, "proton_supply": 0.0,
                    "current_density": 0.0, "emf": 0.0, "overpotential": 0.0, "faradaic_efficiency": 0.0,
                    "electron_flux": 0.0, "carbon_electron_flux": 0.0, "her_electron_flux": 0.0,
                    "iv_residual": 0.0},
        "gibbs": {"dg_formate": 0.0, "dg_acetate": 0.0, "dg_pyruvate": 0.0,
                  "feasible_formate": 0.0, "feasible_acetate": 0.0, "feasible_pyruvate": 0.0,
                  "free_energy_logged": False},
        "products": {"formate": 0.0, "acetate": 0.0, "pyruvate": 0.0},
        "flux": {"net_carbon_flux": 0.0},
        "diagnostics": {"loss_thermodynamic": 0.0, "loss_electrical": 0.0, "loss_catalytic": 0.0,
                        "loss_transport": 0.0, "limitation_code": 0.0},
        "ledger": {k: (1.0 if k == "charge_ledger_ok" else 0.0) for k in _CHARGE_LEDGER_OUT},
        "emitter": {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": dict(_EMIT_TYPES)},
            "inputs": dict(_EMIT_WIRES),
        },
    }

    product_in = {"formate": ["products", "formate"], "acetate": ["products", "acetate"],
                  "pyruvate": ["products", "pyruvate"]}
    product_out = {**product_in, "net_carbon_flux": ["flux", "net_carbon_flux"]}
    attribution_out = {k: ["diagnostics", k] for k in ("loss_thermodynamic", "loss_electrical",
                                                        "loss_catalytic", "loss_transport", "limitation_code")}
    electron_out = {k: ["electro", k] for k in ("electron_flux", "carbon_electron_flux",
                                                 "her_electron_flux", "faradaic_efficiency")}

    if model_carbon_fixation == "empirical":
        doc["budget"] = {
            "_type": "process", "address": "local:ProtonBudgetProcess", "config": {}, "interval": 1.0,
            "inputs": {"pmf_open": ["electro", "pmf_open"], "carbon_flux": ["flux", "net_carbon_flux"]},
            "outputs": {"pmf": ["electro", "pmf"], "charge_state": ["electro", "charge_state"],
                        "proton_reservoir": ["electro", "proton_reservoir"],
                        "proton_draw": ["electro", "proton_draw"], "proton_supply": ["electro", "proton_supply"]},
        }
        doc["thermo"] = {
            "_type": "step", "address": "local:EquilibratorThermoStep", "config": {},
            "inputs": {"pH": ["env", "pH"], "ionic_strength": ["env", "ionic_strength"],
                       "temperature": ["env", "temperature"], "H2": ["env", "H2"], "CO2": ["env", "CO2"],
                       **product_in},
            "outputs": {"dg_formate": ["gibbs", "dg_formate"], "dg_acetate": ["gibbs", "dg_acetate"],
                        "dg_pyruvate": ["gibbs", "dg_pyruvate"],
                        "feasible_formate": ["gibbs", "feasible_formate"],
                        "feasible_acetate": ["gibbs", "feasible_acetate"],
                        "feasible_pyruvate": ["gibbs", "feasible_pyruvate"],
                        "free_energy_logged": ["gibbs", "free_energy_logged"]},
        }
        doc["fixation"] = {
            "_type": "process", "address": fixation_address,
            "config": {"dilution_rate": float(dilution_rate)}, "interval": 1.0,
            "inputs": {"H2": ["env", "H2"], "CO2": ["env", "CO2"], "temperature": ["env", "temperature"],
                       "pmf": ["electro", "pmf"], "catalyst_activity": ["catalyst", "active"],
                       "ni_fraction": ["minerals", "ni_fraction"],
                       "feasible_formate": ["gibbs", "feasible_formate"],
                       "feasible_acetate": ["gibbs", "feasible_acetate"],
                       "feasible_pyruvate": ["gibbs", "feasible_pyruvate"], **product_in},
            "outputs": {**product_out, **attribution_out, **electron_out},
        }
    else:
        # butler_volmer / microkinetic: the class derives its own drive from the
        # fluid redox state and the mineral circuit; no proton budget needed.
        doc["fixation"] = {
            "_type": "process", "address": fixation_address,
            "config": {"dilution_rate": float(dilution_rate), "j0_co2_ref": float(j0_co2),
                       "boundary_layer": float(boundary_layer)},
            "interval": 1.0,
            "inputs": {"H2": ["env", "H2"], "CO2": ["env", "CO2"], "temperature": ["env", "temperature"],
                       "pH_vent": ["env", "pH"], "pH_ocean": ["env", "pH_ocean"],
                       "catalyst_activity": ["catalyst", "active"], "ni_fraction": ["minerals", "ni_fraction"],
                       "conductivity": ["minerals", "conductivity"],
                       "layer_thickness": ["minerals", "layer_thickness"], "porosity": ["minerals", "porosity"],
                       "ionic_strength": ["env", "ionic_strength"], **product_in},
            "outputs": {**product_out, **attribution_out, **electron_out,
                        "current_density": ["electro", "current_density"], "emf": ["electro", "emf"],
                        "overpotential": ["electro", "overpotential"], "iv_residual": ["electro", "iv_residual"]},
        }
    return doc


# --------------------------------------------------------------------------- #
# Reducers (module-level, picklable) — the Phase-2 readouts of one run
# --------------------------------------------------------------------------- #
def _last(rows, key, default=float("nan")) -> float:
    return float(rows[-1].get(key, default)) if rows else float("nan")


def _tail_mean(rows, key, frac=0.1) -> float:
    if not rows:
        return float("nan")
    n = max(1, int(round(len(rows) * frac)))
    vals = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    return sum(vals) / len(vals)


def sustained_throughput(rows) -> float:
    """Settled net carbon fixation rate (mol-C/s) over the final tenth of the run."""
    return _tail_mean(rows, "net_carbon_flux")


def settled_current_density(rows) -> float:
    return _tail_mean(rows, "current_density")


def settled_faradaic_efficiency(rows) -> float:
    return _tail_mean(rows, "faradaic_efficiency")


def settled_emf(rows) -> float:
    return _tail_mean(rows, "emf")


def settled_gradient_efficiency(rows) -> float:
    return _last(rows, "gradient_efficiency")


def loss_thermodynamic(rows) -> float:
    return _tail_mean(rows, "loss_thermodynamic")


def loss_electrical(rows) -> float:
    return _tail_mean(rows, "loss_electrical")


def loss_catalytic(rows) -> float:
    return _tail_mean(rows, "loss_catalytic")


def loss_transport(rows) -> float:
    return _tail_mean(rows, "loss_transport")


def limitation_code(rows) -> float:
    """The settled dominant limitation, re-derived from the settled loss fractions
    (same rule as the classes: largest loss; FE < 0.5 -> catalytic)."""
    if not rows:
        return float("nan")
    losses = {"thermodynamic": loss_thermodynamic(rows), "electrical": loss_electrical(rows),
              "catalytic": loss_catalytic(rows), "transport": loss_transport(rows)}
    if any(v != v for v in losses.values()):
        return float("nan")
    from ..electrochemistry.butler_volmer import LIMITATION_CODES
    return float(LIMITATION_CODES[limitation_label(losses, settled_faradaic_efficiency(rows))])


def charge_residual_max(rows) -> float:
    return _last(rows, "charge_residual_max")


def faradaic_efficiency_max(rows) -> float:
    return _last(rows, "faradaic_efficiency_max")


def iv_residual_max(rows) -> float:
    return _last(rows, "iv_residual_max")


def charge_ledger_ok(rows) -> float:
    return _last(rows, "charge_ledger_ok")


def settled_formate(rows) -> float:
    return _tail_mean(rows, "formate")


PHASE2_REDUCERS = {
    "sustained_throughput": sustained_throughput,
    "current_density": settled_current_density,
    "faradaic_efficiency": settled_faradaic_efficiency,
    "emf": settled_emf,
    "gradient_efficiency": settled_gradient_efficiency,
    "loss_thermodynamic": loss_thermodynamic,
    "loss_electrical": loss_electrical,
    "loss_catalytic": loss_catalytic,
    "loss_transport": loss_transport,
    "limitation_code": limitation_code,
    "charge_residual_max": charge_residual_max,
    "faradaic_efficiency_max": faradaic_efficiency_max,
    "iv_residual_max": iv_residual_max,
    "charge_ledger_ok": charge_ledger_ok,
    "formate": settled_formate,
}


def limitation_name(code: float) -> str:
    """Integer limitation code -> label (``'unresolved'`` for NaN / a failed point)."""
    if code != code:
        return "unresolved"
    return LIMITATION_NAMES.get(int(round(code)), "unresolved")
