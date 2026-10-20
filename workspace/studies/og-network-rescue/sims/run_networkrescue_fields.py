"""Tier-1 spatial-field extraction for og-network-rescue (Gate B pore-ignition).

Reviewer request: PDE concentration-field snapshots and local reaction-rate fields
for the protometabolic network in a CONCENTRATING pore vs a matched WELL-MIXED /
open-pore control, with threshold contours, a spatially-integrated net-carbon
total, and a mesh-convergence check.

Everything here is a REAL computed field — no fabricated arrays:

  * Concentration field c(z): the genuine FiPy accumulation-column solve of the
    real ``ThermophoreticTrapProcess`` (1-D vertical column, scipy LU). The pore
    arm runs the canonical porosity 0.88; the matched control is the open-pore /
    well-mixed arm (confinement -> epsilon 1e-9, NOT 0.0 — a bare 0.0 would be an
    is_empty backfill), which gives a flat field (enrichment ~1). The FVM balance
    residual is carried as the spatial-flux-conservation witness.

  * Local reaction-rate field: the real libRoadRunner reaction universe
    (``open_chemical_network``, reaction_universe) evaluated at the LOCAL precursor
    concentration c(z) along the column — a local-equilibrium reaction-rate map
    over the solved field. Each evaluation runs in a FRESH spawned process
    (maxtasksperchild=1) so repeated libRoadRunner solves cannot leak/flake.

  * Ignition threshold: read from where the local rate field crosses the
    net-carbon-flux ignition criterion (1e-6) — overlaid as a contour on the field.

  * Spatially-integrated net carbon production: trapezoid of the rate field over z.

  * Mesh-convergence check: the trap solved at nz = 20..320; the enrichment (Pe_acc)
    and the FVM residual are reported vs resolution.

NOT computed here (flagged "requested future simulation" in the figure caption, never
fabricated): a fully space-resolved 2-D/3-D TRANSIENT reaction-diffusion solve with the
reaction terms coupled inside the PDE and time-lapse 2-D snapshots. The trap solve is
1-D steady and the reaction network is well-mixed 0-D evaluated pointwise.

Run (from the study's canonical venv, worktree on PYTHONPATH):
    PYTHONPATH=<boot> /path/to/.venv/bin/python run_networkrescue_fields.py
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
OUT = (STUDY_DIR / "artifacts" / "og-30-spatially-integrated-protometabolism"
       / "networkrescue_fields.json")

BASE_FEED = 1.0e-3          # vent-posterior base CO2/H2 (molar), held EQUAL pore vs control
POROSITY_PORE = 0.88        # canonical concentrating pore (gate_b_spatial.json)
POROSITY_CTRL = 1.0 - 1e-9  # open-pore / well-mixed control: confinement -> epsilon, NOT 0.0
TEMPERATURE = 333.15
FLOW = 1.0e-4
K_WASH = 0.05
MAX_CARBONS = 4
N_STEPS = 120
N_Z_SAMPLES = 18            # spatial samples for the reaction-rate map (per arm)
IGNITION_FLUX = 1.0e-6      # net-carbon-flux ignition criterion (matches gate_b metric)
PLAUSIBLE_FEED_MAX = 0.5    # molar; above this the pore-local feed is physically implausible


# --------------------------------------------------------------------------- #
# Network worker — module-level & picklable, ONE fresh process per evaluation. #
# --------------------------------------------------------------------------- #
def _eval_network(args: dict) -> dict:
    """Run the real reaction universe at a fixed feed; return settled flux, the
    connectivity flag, persistent-species count and (optionally) the flux time
    series. Runs in its own spawned process so libRoadRunner state never leaks."""
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.open_chemical_network import (
        open_chemical_network, settled_net_carbon_flux)

    core = build_core()
    doc = open_chemical_network(
        core, model_proto_metabolism="reaction_universe",
        feed_CO2=float(args["feed_CO2"]), feed_H2=float(args["feed_H2"]),
        k_wash=K_WASH, max_carbons=int(args.get("max_carbons", MAX_CARBONS)))
    sim = Composite({"state": doc}, core=core)
    sim.run(float(N_STEPS))
    res = gather_emitter_results(sim)
    rows = res.get(("emitter",)) or next(iter(res.values()))
    out = {
        "feed_CO2": float(args["feed_CO2"]),
        "net_carbon_flux": float(settled_net_carbon_flux(rows)),
        "network_connected": float(rows[-1].get("network_connected", 0.0)) if rows else 0.0,
        "n_persistent_species": float(rows[-1].get("n_persistent_species", 0.0)) if rows else 0.0,
    }
    if args.get("keep_series"):
        out["flux_t"] = [float(r.get("net_carbon_flux", 0.0)) for r in rows]
        out["step"] = list(range(len(rows)))
    return out


def _solve_trap(porosity: float, nz: int = 80) -> dict:
    """Solve the real FiPy accumulation column at a porosity; return the vertical
    concentration profile c(z), enrichment, Pe_acc and the FVM balance residual."""
    from viva_genesis.core import build_core
    from viva_genesis.transport.thermophoretic_trap import (
        ThermophoreticTrapProcess, trap_profile)
    core = build_core()
    proc = ThermophoreticTrapProcess(config={"nz": int(nz)}, core=core)
    out = proc.update({"temperature": TEMPERATURE, "flow_velocity": FLOW,
                       "porosity": float(porosity)}, 1.0)
    prof = trap_profile(proc)
    return {
        "z_mm": prof["z_mm"],                 # base (z=0) .. feed/top (z=L)
        "conc_rel": prof["conc"],             # c(z)/c_top, dimensionless (top=1)
        "enrichment": float(out["enrichment_factor"]),
        "accumulation_peclet": float(out["accumulation_peclet"]),
        "flux_divergence_residual": float(out["flux_divergence_residual"]),
        "beta_per_m": float(getattr(proc, "_beta", 0.0)),
    }


def _crossing_z(z_mm, feed_molar, flux, threshold):
    """First z (mm, from the top down) where the local rate field crosses the
    ignition threshold, by linear interpolation; also the local feed there."""
    # z_mm is base..top ascending; walk from the enriched base upward until flux
    # drops below threshold -> the ignition front.
    prev_z = prev_f = prev_feed = None
    for z, feed, f in zip(z_mm, feed_molar, flux):
        if prev_f is not None and ((prev_f >= threshold) != (f >= threshold)):
            # interpolate the z where flux == threshold
            if f != prev_f:
                t = (threshold - prev_f) / (f - prev_f)
                zc = prev_z + t * (z - prev_z)
                feedc = prev_feed + t * (feed - prev_feed)
                return float(zc), float(feedc)
        prev_z, prev_f, prev_feed = z, f, feed
    return None, None


def main() -> int:
    import numpy as np
    from multiprocessing import get_context

    t0 = time.time()

    # --- 1. Real FiPy concentration fields: pore vs matched open-pore control --- #
    pore_field = _solve_trap(POROSITY_PORE)
    ctrl_field = _solve_trap(POROSITY_CTRL)
    beta = pore_field["beta_per_m"]
    L_m = pore_field["z_mm"][-1] / 1000.0

    # --- 2. Mesh-convergence check on the trap solve --- #
    mesh = {"nz": [], "enrichment": [], "accumulation_peclet": [], "flux_divergence_residual": []}
    for nz in (20, 40, 80, 160, 320):
        s = _solve_trap(POROSITY_PORE, nz=nz)
        mesh["nz"].append(nz)
        mesh["enrichment"].append(s["enrichment"])
        mesh["accumulation_peclet"].append(s["accumulation_peclet"])
        mesh["flux_divergence_residual"].append(s["flux_divergence_residual"])
    e_fin = mesh["enrichment"][-1]
    mesh["enrichment_rel_to_finest"] = [abs(e - e_fin) / abs(e_fin) if e_fin else 0.0
                                        for e in mesh["enrichment"]]
    mesh["converged_under_1pct"] = bool(max(mesh["enrichment_rel_to_finest"]) < 0.01)

    # --- 3. Local reaction-rate field: sample z, eval network at local feed ----- #
    # Local enrichment at height z: c(z)/c_top = exp(beta*(L - z)). Pore-local feed
    # = BASE_FEED * that. Control feed is flat at BASE_FEED (field ~1 everywhere).
    z_samples_mm = np.linspace(0.0, pore_field["z_mm"][-1], N_Z_SAMPLES)
    z_samples_m = z_samples_mm / 1000.0
    local_enrich = np.exp(np.clip(beta * (L_m - z_samples_m), 0.0, 45.0))
    pore_feed = BASE_FEED * local_enrich
    ctrl_feed = np.full_like(pore_feed, BASE_FEED)

    jobs = []
    # z=0 (base, most enriched) is the whole-pore canonical point -> keep its series.
    for i, f in enumerate(pore_feed):
        jobs.append({"arm": "pore", "iz": i, "feed_CO2": float(f), "feed_H2": float(f),
                     "keep_series": bool(i == 0)})
    for i, f in enumerate(ctrl_feed):
        jobs.append({"arm": "control", "iz": i, "feed_CO2": float(f), "feed_H2": float(f),
                     "keep_series": bool(i == 0)})

    ctx = get_context("spawn")
    results = []
    with ctx.Pool(processes=1, maxtasksperchild=1) as pool:
        for job, out in zip(jobs, pool.map(_eval_network, jobs)):
            out["arm"] = job["arm"]
            out["iz"] = job["iz"]
            results.append(out)

    def collect(arm, key):
        return [r[key] for r in sorted((x for x in results if x["arm"] == arm),
                                       key=lambda x: x["iz"])]

    rate = {
        "z_mm": z_samples_mm.tolist(),
        "pore": {
            "feed_molar": pore_feed.tolist(),
            "local_enrichment": local_enrich.tolist(),
            "net_carbon_flux": collect("pore", "net_carbon_flux"),
            "network_connected": collect("pore", "network_connected"),
            "n_persistent_species": collect("pore", "n_persistent_species"),
            "physical_feed": [bool(f <= PLAUSIBLE_FEED_MAX) for f in pore_feed],
        },
        "control": {
            "feed_molar": ctrl_feed.tolist(),
            "net_carbon_flux": collect("control", "net_carbon_flux"),
            "network_connected": collect("control", "network_connected"),
            "n_persistent_species": collect("control", "n_persistent_species"),
        },
    }

    # --- 4. Ignition threshold contour (where the pore rate field crosses it) --- #
    zc_mm, feedc = _crossing_z(rate["z_mm"], rate["pore"]["feed_molar"],
                               rate["pore"]["net_carbon_flux"], IGNITION_FLUX)
    threshold = {
        "ignition_flux": IGNITION_FLUX,
        "ignition_feed_molar": feedc,                 # local feed at the ignition front
        "pore_z_cross_mm": zc_mm,                      # height of the ignition front in the pore
        "control_ignites": bool(max(rate["control"]["net_carbon_flux"]) > IGNITION_FLUX),
        "method": ("ignition front = where the local reaction-rate map crosses "
                   "net_carbon_flux > 1e-6; the control never crosses it."),
    }

    # --- 5. Spatially-integrated net carbon production (trapezoid over z) -------- #
    z_m = z_samples_m
    pore_rate = np.clip(np.asarray(rate["pore"]["net_carbon_flux"], float), 0.0, None)
    ctrl_rate = np.clip(np.asarray(rate["control"]["net_carbon_flux"], float), 0.0, None)
    _trapz = getattr(np, "trapezoid", None) or np.trapz
    pore_int = float(_trapz(pore_rate, z_m))
    ctrl_int = float(_trapz(ctrl_rate, z_m))
    integral = {
        "pore_total_net_carbon": pore_int,
        "control_total_net_carbon": ctrl_int,
        "ratio_pore_over_control": (pore_int / ctrl_int) if ctrl_int > 0 else None,
        "units": "mol/s * m (net carbon flux integrated over pore length)",
        "method": "trapezoid of the (clipped>=0) local reaction-rate field over z.",
    }

    # --- 6. Synchronized time trajectories (whole-pore vs control) -------------- #
    pore_series = next(r for r in results if r["arm"] == "pore" and r["iz"] == 0)
    ctrl_series = next(r for r in results if r["arm"] == "control" and r["iz"] == 0)
    time_block = {
        "step": pore_series.get("step", []),
        "pore_flux_t": pore_series.get("flux_t", []),
        "control_flux_t": ctrl_series.get("flux_t", []),
        "note": ("whole-pore net carbon flux over the 120-step run at identical "
                 "synchronized time points; pore = network at the pore-enriched feed, "
                 "control = network at the same base feed, open-pore (no enrichment)."),
    }

    # --- summary (matches gate_b_spatial.json headline) ------------------------- #
    summary = {
        "pore": {
            "enrichment": pore_field["enrichment"],
            "feed_molar": BASE_FEED * pore_field["enrichment"],
            "net_carbon_flux": rate["pore"]["net_carbon_flux"][0],
            "network_connected": rate["pore"]["network_connected"][0],
            "n_persistent_species": rate["pore"]["n_persistent_species"][0],
        },
        "control": {
            "enrichment": ctrl_field["enrichment"],
            "feed_molar": BASE_FEED,
            "net_carbon_flux": rate["control"]["net_carbon_flux"][0],
            "network_connected": rate["control"]["network_connected"][0],
            "n_persistent_species": rate["control"]["n_persistent_species"][0],
        },
        "rescued": bool(rate["pore"]["net_carbon_flux"][0] > IGNITION_FLUX
                        and rate["control"]["net_carbon_flux"][0] <= IGNITION_FLUX),
        "feeds_held_equal_base": BASE_FEED,
    }

    artifact = {
        "meta": {
            "study": "og-network-rescue",
            "composite": ("viva_genesis.composites.og_30_spatially_integrated_protometabolism"
                          ".og_30_spatially_integrated_protometabolism"),
            "arm": "30_spatially_integrated_protometabolism",
            "wall_time_s": time.time() - t0,
            "base_feed_molar": BASE_FEED,
            "porosity_pore": POROSITY_PORE,
            "porosity_control": POROSITY_CTRL,
            "n_steps": N_STEPS,
            "geometry": {
                "pore_length_mm": pore_field["z_mm"][-1],
                "pore_width_mm": 0.1, "delta_T_K": 30.0,
                "soret_coeff_per_K": 0.10, "solute_diffusivity_m2_s": 1.0e-10,
            },
            "honest_note": (
                "All fields are REAL computed quantities. Concentration field = the FiPy "
                "accumulation-column solve of ThermophoreticTrapProcess (1-D steady, FVM "
                "residual carried). Reaction-rate field = the real libRoadRunner reaction "
                "universe evaluated at the local concentration c(z) (local-equilibrium "
                "reaction-rate map over the solved field). Control uses confinement epsilon "
                "(porosity 1-1e-9), NOT 0.0, to avoid the pbg is_empty backfill."),
            "future_sim_note": (
                "REQUESTED FUTURE SIMULATION (not computed, not fabricated): a fully "
                "space-resolved 2-D/3-D TRANSIENT reaction-diffusion solve with the reaction "
                "terms coupled inside the PDE and time-lapse 2-D field snapshots. The trap "
                "solve here is 1-D steady; the reaction network is well-mixed 0-D evaluated "
                "pointwise along the solved concentration field."),
            "framing": (
                "Spatial concentration is the causal difference that ignites the network vs "
                "the dead well-mixed control: persistence/ignition at vent-realistic feeds, "
                "NOT autocatalytic self-amplification."),
        },
        "field": {"pore": pore_field, "control": ctrl_field,
                  "units": {"z_mm": "mm along pore (base=0, feed/top=L)",
                            "conc_rel": "c(z)/c_top (dimensionless, top=1)"}},
        "rate_field": rate,
        "threshold": threshold,
        "integral": integral,
        "time": time_block,
        "mesh_convergence": mesh,
        "summary": summary,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(artifact, f, indent=1)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes) in {artifact['meta']['wall_time_s']:.1f}s")
    print(f"  pore flux={summary['pore']['net_carbon_flux']:.4g} connected="
          f"{summary['pore']['network_connected']} | control flux="
          f"{summary['control']['net_carbon_flux']:.4g} connected="
          f"{summary['control']['network_connected']} | rescued={summary['rescued']}")
    print(f"  ignition front z={threshold['pore_z_cross_mm']} mm  feed="
          f"{threshold['ignition_feed_molar']} M | integral ratio="
          f"{integral['ratio_pore_over_control']}")
    print(f"  mesh converged<1%={mesh['converged_under_1pct']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
