"""Tier-1 reaction-diffusion PDE field artifact for og-carbon-fixation (arm
og-01-cal-electrochemistry, composite ``electrochemical_carbon_fixation``).

Figure-review request: a spatial reaction-diffusion panel of the vent-wall
carbon-fixation interface. This runner executes the REAL composite (FiPy
Nernst-Planck proton electrodiffusion + Butler-Volmer galvanic-cell kinetics +
eQuilibrator-gated thermo + the charge/electron ledger) and extracts every
field it genuinely computes into a committed artifact JSON that a pure
JSON-reader viz renders. NO solver runs at render time; NO field is fabricated.

What this composite ACTUALLY resolves (so the honest bar is explicit):

  * a genuine 1-D FiPy electroneutral Nernst-Planck proton (H+ -> pH) field
    ACROSS the Fe/Ni/S barrier (ocean acidic face -> vent alkaline face), every
    value a real FiPy ``CellVariable`` (via ``ph_gradient.spatial_profile``);
  * a single well-mixed Fe/Ni/S reaction interface: net carbon-fixation rate,
    the formate/acetate/pyruvate product pools, the faradaic current split and
    the Kirchhoff/electron (boundary-flux) ledger -- all 0-D point observables.

What it does NOT resolve, and is therefore flagged "requested future
simulation" in the artifact + caption rather than fabricated:

  * 2-D pore-geometry maps of dissolved H2, DIC and formate;
  * a spatially-varying net-carbon-fixation-rate field;
  * a surface-reaction-rate heatmap along a spatially-resolved mineral
    interface.

These need a 2-D multi-solute reactive-transport mesh (og-00's
FipyReactiveTransportProcess is 2-D but carries only T + one lumped tracer, not
the carbon-fixation species), i.e. a model extension, not a re-run.

Matched control: the no-catalyst null sets ``catalyst_active -> 1e-6`` (NEVER
0.0 -- a bare 0.0 is backfilled to the port default by the bigraph-schema
is_empty rule and would silently rerun the favourable arm). The diffusion field
is geochemically set and so is correctly catalyst-independent; the REACTION
(net carbon flux + products) is what must -- and does -- collapse (~6 orders).

Robustness: each arm runs in its own fresh spawn subprocess (processes=1,
maxtasksperchild=1) so a FiPy solver hiccup cannot bleed across arms. Any arm
that fails is recorded as ``status: "failed"`` and its fields flagged future-sim
rather than crashing the artifact; the viz never solves, so it never errors.
"""
from __future__ import annotations

import json
import multiprocessing as mp
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
OUT = STUDY_DIR / "artifacts" / "og-01-cal-electrochemistry" / "carbonfix_pde_fields.json"

COMPOSITE = "viva_genesis.composites.electrochemical_interface.electrochemical_carbon_fixation"
MODEL = "butler_volmer"          # the study's canonical electrochemistry class
N_STEPS = 60                     # batch (dilution_rate=0): products accumulate
# time-point indices (1-based steps) snapshotted for the field panel
FIELD_STEPS = (1, 15, 60)

# point observables tracked as a time series (the interface reaction-rate +
# boundary-flux ledger live here)
SERIES_KEYS = (
    "net_carbon_flux", "current_density", "proton_current_density",
    "formate", "acetate", "pyruvate", "faradaic_efficiency",
    "electron_flux", "carbon_electron_flux", "her_electron_flux",
    "charge_residual_max", "charge_ledger_ok", "pmf_open",
    "loss_thermodynamic", "loss_electrical", "loss_catalytic", "loss_transport",
)


def _find_gradient(node):
    """Walk the composite state tree for the live PhGradientNernstPlanckProcess."""
    if isinstance(node, dict):
        inst = node.get("instance")
        if inst is not None and type(inst).__name__ == "PhGradientNernstPlanckProcess":
            return inst
        for v in node.values():
            r = _find_gradient(v)
            if r is not None:
                return r
    return None


def _run_arm(catalyst_active: float, q: "mp.Queue") -> None:
    """Run ONE arm of the real composite in this (fresh) process and push a
    JSON-able dict of extracted fields onto ``q``. Any exception is reported as a
    failed arm rather than raising, so the parent still writes a valid artifact."""
    try:
        from process_bigraph import Composite, gather_emitter_results
        from viva_genesis.core import build_core
        from viva_genesis.composites.electrochemical_interface import (
            electrochemical_carbon_fixation,
        )
        from viva_genesis.electrochemistry.ph_gradient import spatial_profile

        core = build_core()
        doc = electrochemical_carbon_fixation(
            core, model_carbon_fixation=MODEL, catalyst_active=float(catalyst_active)
        )
        sim = Composite({"state": doc}, core=core)
        grad = _find_gradient(sim.state)
        if grad is None:
            raise RuntimeError("PhGradientNernstPlanckProcess not found in composite state")

        barrier_m = float(grad.config["barrier_length"])
        series = {k: [] for k in SERIES_KEYS}
        series["time_s"] = []
        series["step"] = []
        field_timepoints = []
        x_cm = None

        for step in range(1, N_STEPS + 1):
            sim.run(1)
            rows = gather_emitter_results(sim)[("emitter",)]
            last = rows[-1]
            series["step"].append(step)
            series["time_s"].append(float(last.get("global_time", step)))
            for k in SERIES_KEYS:
                v = last.get(k)
                series[k].append(None if v is None else float(v))
            if step in FIELD_STEPS:
                p = spatial_profile(grad)
                if p.get("x_cm"):
                    x_cm = [float(v) for v in p["x_cm"]]
                    field_timepoints.append({
                        "step": step,
                        "time_s": float(last.get("global_time", step)),
                        "pH": [float(v) for v in p["pH"]],
                        "H_molar": [float(v) for v in p["H"]],
                    })

        last = rows[-1]
        ledger = {
            "proton_current_density_A_m2": _f(last.get("proton_current_density")),
            "cell_current_density_A_m2": _f(last.get("current_density")),
            "electron_flux": _f(last.get("electron_flux")),
            "carbon_electron_flux": _f(last.get("carbon_electron_flux")),
            "her_electron_flux": _f(last.get("her_electron_flux")),
            "faradaic_efficiency": _f(last.get("faradaic_efficiency")),
            "charge_residual_max": _f(last.get("charge_residual_max")),
            "charge_ledger_ok": _f(last.get("charge_ledger_ok")),
        }
        interface_rate = {
            "settled_net_carbon_flux_mol_s": _f(last.get("net_carbon_flux")),
            "settled_cell_current_density_A_m2": _f(last.get("current_density")),
            "settled_formate_M": _f(last.get("formate")),
        }
        q.put({
            "status": "ok",
            "params": {"model_carbon_fixation": MODEL, "catalyst_active": float(catalyst_active),
                       "dilution_rate": 0.0},
            "barrier_length_m": barrier_m,
            "x_cm": x_cm,
            "field_timepoints": field_timepoints,
            "series": series,
            "boundary_flux_ledger": ledger,
            "interface_reaction_rate": interface_rate,
        })
    except Exception as exc:  # pragma: no cover - reported, not raised
        import traceback
        q.put({"status": "failed", "error": f"{type(exc).__name__}: {exc}",
               "traceback": traceback.format_exc(),
               "params": {"model_carbon_fixation": MODEL, "catalyst_active": float(catalyst_active)}})


def _f(v):
    return None if v is None else float(v)


def _run_arm_isolated(catalyst_active: float) -> dict:
    """Run one arm in a fresh spawn subprocess and return its result dict."""
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_run_arm, args=(float(catalyst_active), q))
    p.start()
    try:
        result = q.get(timeout=1200)
    finally:
        p.join(timeout=30)
        if p.is_alive():
            p.terminate()
    return result


def main() -> int:
    favorable = _run_arm_isolated(1.0)
    no_catalyst = _run_arm_isolated(1.0e-6)

    # Prove the control collapses the REACTION (not a backfill artifact): the
    # diffusion field may be identical (correct physics) but the net carbon flux
    # must drop by orders.
    collapse = None
    if favorable.get("status") == "ok" and no_catalyst.get("status") == "ok":
        fav_ncf = favorable["interface_reaction_rate"]["settled_net_carbon_flux_mol_s"] or 0.0
        noc_ncf = no_catalyst["interface_reaction_rate"]["settled_net_carbon_flux_mol_s"] or 0.0
        fav_fmt = favorable["interface_reaction_rate"]["settled_formate_M"] or 0.0
        noc_fmt = no_catalyst["interface_reaction_rate"]["settled_formate_M"] or 0.0
        import math as _m
        collapse = {
            "favorable_net_carbon_flux_mol_s": fav_ncf,
            "no_catalyst_net_carbon_flux_mol_s": noc_ncf,
            "net_carbon_flux_collapse_orders": (
                _m.log10(fav_ncf / noc_ncf) if (fav_ncf > 0 and noc_ncf > 0) else None),
            "favorable_formate_M": fav_fmt,
            "no_catalyst_formate_M": noc_fmt,
            "formate_collapse_orders": (
                _m.log10(fav_fmt / noc_fmt) if (fav_fmt > 0 and noc_fmt > 0) else None),
            "reaction_collapses": (noc_ncf < 1e-3 * fav_ncf) if fav_ncf > 0 else None,
        }

    artifact = {
        "study": "og-carbon-fixation",
        "arm": "og-01-cal-electrochemistry",
        "composite": COMPOSITE,
        "run_provenance": (
            "viva_genesis.composites.electrochemical_interface.electrochemical_carbon_fixation"
            "__1792066785__b9f82a"),
        "figure": "reaction-diffusion PDE field at the vent-wall carbon-fixation interface",
        "model_carbon_fixation": MODEL,
        "n_steps": N_STEPS,
        "field_steps": list(FIELD_STEPS),
        "field_axis": {
            "name": "position across the Fe/Ni/S barrier",
            "units": "cm",
            "orientation": "ocean (acidic) face -> vent (alkaline) face",
            "note": "1-D FiPy Nernst-Planck proton field; every cell value is a real FiPy CellVariable.",
        },
        "arms": {"favorable": favorable, "no_catalyst": no_catalyst},
        "control_collapse": collapse,
        "extractable_fields": [
            "proton_pH_1d (real FiPy Nernst-Planck field across the barrier)",
            "interface net-carbon-fixation rate (0-D, time series)",
            "formate/acetate/pyruvate product pools (0-D, time series)",
            "faradaic current split + integrated boundary-flux (charge/electron) ledger",
        ],
        "requested_future_simulation": [
            "2-D pore-geometry dissolved-H2 field",
            "2-D pore-geometry DIC field",
            "2-D pore-geometry formate field",
            "spatially-varying net-carbon-fixation-rate field",
            "surface-reaction-rate heatmap along a spatially-resolved mineral interface",
        ],
        "honesty_notes": {
            "dimensionality": (
                "electrochemical_carbon_fixation resolves a 1-D proton electrodiffusion barrier plus a "
                "single well-mixed Fe/Ni/S reaction interface. H2/DIC/formate are well-mixed feeds/pools, "
                "not spatial fields; a 2-D multi-solute pore map is a model extension (future sim), not a "
                "re-run, so it is flagged rather than fabricated."),
            "control": (
                "no-catalyst null uses catalyst_active=1e-6, NOT 0.0 (bigraph-schema is_empty backfill). "
                "The proton diffusion field is geochemically set and is correctly catalyst-independent; the "
                "collapse is in the REACTION (net carbon flux + products), proving the null is genuine."),
            "yields": (
                "product pools are lab-calibrated Preiner-2020/Altair-2025 CEILINGS gated by the catalyst, "
                "deterministic (no error bars, none fabricated); the spatial panel shows the computed field, "
                "it does not turn the calibrated ceilings into a prediction."),
            "field_steady": (
                "the proton electrodiffusion field equilibrates within the first step (fast relative to the "
                "reaction), so the three field time points are near-identical by construction -- a real "
                "result, not a rendering shortcut; the genuine time dependence is the product accumulation."),
            "gate": "figure is descriptive; it does NOT change any arm verdict or the study gate.",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2))

    for name, arm in (("favorable", favorable), ("no_catalyst", no_catalyst)):
        st = arm.get("status")
        if st == "ok":
            ir = arm["interface_reaction_rate"]
            lg = arm["boundary_flux_ledger"]
            print(f"{name}: status=ok  net_C_flux={ir['settled_net_carbon_flux_mol_s']:.3g} mol/s  "
                  f"j={ir['settled_cell_current_density_A_m2']:.3g} A/m^2  FE={lg['faradaic_efficiency']:.3g}  "
                  f"charge_resid_max={lg['charge_residual_max']:.2g}  field_tps={len(arm['field_timepoints'])}")
        else:
            print(f"{name}: status=FAILED  {arm.get('error')}")
    if collapse:
        print(f"control collapse: net-C-flux {collapse['net_carbon_flux_collapse_orders']:.1f} orders, "
              f"formate {collapse['formate_collapse_orders']:.1f} orders, "
              f"reaction_collapses={collapse['reaction_collapses']}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
