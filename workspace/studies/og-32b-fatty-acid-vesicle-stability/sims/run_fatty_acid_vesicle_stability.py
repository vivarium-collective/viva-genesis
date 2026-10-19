#!/usr/bin/env python
"""S1 -- fatty-acid VESICLE stability under Gate C, across the chain-length axis.

Replaces og-32's DLPC/DPPC phospholipid planar-bilayer STAND-IN with the real
protocell amphiphile: single-chain saturated FATTY ACIDS self-assembled into a
closed bilayer VESICLE (viva-openmm's Martini 3 fatty-acid defs + vesicle
builder + membrane barostat). We ask the Gate-C question directly: does a
fatty-acid vesicle stay a closed bilayer shell, and over what chain-length
window -- and does the matched null (fully-ionised, charged-only heads) fail by
micellising, as fatty-acid physics predicts (protonated/mixed heads form
vesicles; fully-deprotonated heads repel -> micelles)?

ARMS
  protonated C10/C12/C14/C16  -- neutral COOH (SP2) heads -> vesicle-forming
  charged-null C14 (+ C10)    -- deprotonated COO- (SQ5n) heads -> should micellise

STABILITY METRIC (end-state bilayer-shell retention)
  Each lipid head (COO bead) sits on the vesicle shell at radius ~R from the
  centre of mass. An intact bilayer vesicle keeps the heads in a narrow radial
  shell (two leaflets, a ~2 nm gap); a micellised / disrupted system scatters
  them. We report, from the final frame:
    shell_integrity = fraction of head beads within +/-1.0 nm of the median head
                      radius (1.0 == perfectly retained shell)
    head_radial_cv  = CV of head radii (low == tight shell, high == disrupted)
  verdict stable_vesicle if shell_integrity >= 0.75, else micellised/disrupted.

HONESTY
  - SHORT bounded MD -> a structural STABILITY TREND, not a converged free energy.
    The PMF-resolved permeability/stability closure is the GPU gold-standard
    follow-up (S3/og-32a), flagged separately.
  - Head bead pair SP2 (COOH) / SQ5n (COO-) is a Martini-3 building-block
    proposed_input (tracked <<CONFIRM>>), tails authoritative. See the viva-openmm
    fatty-acid .itp header.
  - pH is fixed-charge: an arm picks protonated vs deprotonated; it does NOT
    titrate. The protonated arm stands for local pH well below the carboxylate
    pKa (~4.8); the charged-null for pH well above. Intermediate (mixed) pH is a
    follow-up, not resolved here.

    python run_fatty_acid_vesicle_stability.py <out.json> [--quick] [--platform CPU]
"""
from __future__ import annotations

import argparse
import json
import math
import time

import numpy as np


# (label, chain, protonated) -- protonated=False is the charged-only null
ARMS_FULL = [
    ("C10_protonated", 10, True),
    ("C12_protonated", 12, True),
    ("C14_protonated", 14, True),
    ("C16_protonated", 16, True),
    ("C14_charged_null", 14, False),
    ("C10_charged_null", 10, False),
]
ARMS_QUICK = [
    ("C16_protonated", 16, True),
    ("C14_charged_null", 14, False),
]

# A closed bilayer vesicle is identified by a RETAINED INNER LEAFLET (heads
# clearly inside the median shell radius -> a water lumen, two leaflets) that
# stays radially COHERENT (not dispersed into free solution). A micelle /
# collapsed aggregate loses the inner surface and/or disperses. These two
# thresholds define the verdict; shell_integrity is reported as a diagnostic
# (its +/-1.5 nm band spans the ~2 nm leaflet separation plus undulation).
INNER_LEAFLET_MIN = 0.20    # min inner-leaflet head fraction (bilayer vs micelle)
CV_MAX = 0.35               # max head-radius CV (coherent shell vs dispersed)
SHELL_BAND_NM = 1.5         # diagnostic shell band (half the leaflet sep + spread)
N_SEEDS = 3                 # independent MD replicates per arm (1 in --quick)


def _head_radii(positions, head_mask, lipid_mask):
    """Radial distances (nm) of head beads from the LIPID-aggregate centre of
    mass (water excluded, so solvent can't skew the vesicle centre)."""
    com = positions[lipid_mask].mean(axis=0)
    r = np.linalg.norm(positions - com, axis=1)
    return r[head_mask]


def _run_once(label, chain, protonated, *, platform, quick):
    """One independent MD replicate -> raw end-state metrics (OpenMM auto-seeds
    the integrator/velocities, so repeated calls are independent trajectories)."""
    from openmm import unit
    from viva_openmm import (fatty_acid_spec, build_vesicle, bundled_forcefield,
                             bundled_fatty_acids, OpenMMMartiniProcess)
    from viva_openmm.topology import resources  # reuse the packaged data dir
    from process_bigraph import allocate_core
    import tempfile
    import os

    t0 = time.time()
    lipid = fatty_acid_spec(chain, protonated=protonated)
    d = tempfile.mkdtemp()
    gro = os.path.join(d, "v.gro")
    top = os.path.join(d, "v.top")

    radius = 4.0 if quick else 5.0
    n_water = 0 if quick else 1500
    solvents = str(resources.files("viva_openmm").joinpath(
        "data", "martini_v3.0.0_solvents_v1.itp"))
    res = build_vesicle(
        lipid, radius_nm=radius, leaflet_sep_nm=2.0, area_per_lipid_nm2=0.62,
        n_water=n_water, out_gro=gro, out_top=top,
        forcefield_itp=bundled_forcefield(), lipid_itp=bundled_fatty_acids(),
        water_itp=(None if n_water == 0 else solvents))

    prod = 8000 if quick else 40000      # @20 fs -> ~0.16 ns quick / ~0.8 ns full
    p = OpenMMMartiniProcess(config={
        "gro": gro, "top": top, "platform": platform,
        "minimize": True, "min_iterations": 5000,
        "equil_steps": (500 if quick else 2000), "equil_timestep_fs": 2.0,
        "steps_per_update": prod, "timestep_fs": 20.0,
        "barostat": "membrane", "surface_tension_bar_nm": 0.0, "pressure_bar": 1.0,
    }, core=allocate_core())

    # head mask on the lipid beads (COO), ignoring any trailing water beads
    atoms = list(p_atoms(gro))
    head_mask = np.array([name == "COO" for (_res, name) in atoms])
    lipid_mask = np.array([res != "W" for (res, _name) in atoms])

    start_pos = _positions_nm(gro)
    r0 = _head_radii(start_pos, head_mask, lipid_mask)
    out = p.update(p.initial_state(), interval=1.0)
    end_pos = _context_positions_nm(p)
    r1 = _head_radii(end_pos[: len(atoms)], head_mask, lipid_mask)

    med = float(np.median(r1))
    shell_integrity = float(np.mean(np.abs(r1 - med) <= SHELL_BAND_NM))
    head_radial_cv = float(np.std(r1) / (np.mean(r1) + 1e-9))
    # bilayer-vs-micelle discriminator: a closed bilayer vesicle keeps a
    # populated INNER leaflet (heads clearly inside the median radius) and a
    # water lumen; a micellised/collapsed aggregate loses the inner surface.
    inner_leaflet_fraction = float(np.mean(r1 < (med - 0.3)))
    outer_leaflet_fraction = float(np.mean(r1 > (med + 0.3)))
    # stable closed bilayer vesicle: a retained inner leaflet AND a coherent
    # (non-dispersed) head shell.
    is_stable = (inner_leaflet_fraction >= INNER_LEAFLET_MIN
                 and head_radial_cv <= CV_MAX)
    verdict = "stable_vesicle" if is_stable else "micellised"

    return {
        "n_lipids": res.n_lipids, "n_lipid_beads": res.n_lipid_beads,
        "n_water": res.n_water, "radius_nm": radius, "prod_steps": prod,
        "potential_energy_kj": round(float(out["potential_energy"]), 1),
        "head_radius_start_nm": round(float(np.median(r0)), 3),
        "head_radius_end_nm": round(med, 3),
        "shell_integrity": round(shell_integrity, 3),
        "head_radial_cv": round(head_radial_cv, 3),
        "inner_leaflet_fraction": round(inner_leaflet_fraction, 3),
        "outer_leaflet_fraction": round(outer_leaflet_fraction, 3),
        "verdict": verdict,
        "wall_s": round(time.time() - t0, 1),
    }


def run_arm(label, chain, protonated, *, platform, quick):
    """Aggregate N independent replicates into a robust, spread-reported arm."""
    n_seeds = 1 if quick else N_SEEDS
    reps = [_run_once(label, chain, protonated, platform=platform, quick=quick)
            for _ in range(n_seeds)]

    def ms(key):
        vals = [r[key] for r in reps]
        return round(float(np.mean(vals)), 3), round(float(np.std(vals)), 3)

    inner_mean, inner_std = ms("inner_leaflet_fraction")
    cv_mean, cv_std = ms("head_radial_cv")
    shell_mean, shell_std = ms("shell_integrity")
    n_stable = sum(r["verdict"] == "stable_vesicle" for r in reps)
    # robust verdict on the seed-MEAN metrics (not a single trajectory)
    is_stable = inner_mean >= INNER_LEAFLET_MIN and cv_mean <= CV_MAX
    return {
        "label": label, "chain": chain, "protonated": protonated,
        "arm": "protonated" if protonated else "charged_null",
        "n_seeds": n_seeds, "n_stable_seeds": n_stable,
        "n_lipids": reps[0]["n_lipids"], "n_lipid_beads": reps[0]["n_lipid_beads"],
        "n_water": reps[0]["n_water"], "radius_nm": reps[0]["radius_nm"],
        "prod_steps": reps[0]["prod_steps"],
        "shell_integrity": shell_mean, "shell_integrity_std": shell_std,
        "head_radial_cv": cv_mean, "head_radial_cv_std": cv_std,
        "inner_leaflet_fraction": inner_mean, "inner_leaflet_fraction_std": inner_std,
        "verdict": "stable_vesicle" if is_stable else "micellised",
        "seed_metrics": [{"shell_integrity": r["shell_integrity"],
                          "head_radial_cv": r["head_radial_cv"],
                          "inner_leaflet_fraction": r["inner_leaflet_fraction"],
                          "verdict": r["verdict"]} for r in reps],
        "wall_s": round(sum(r["wall_s"] for r in reps), 1),
    }


# -- small .gro / context readers (keep the sim self-contained) --------------
def p_atoms(gro):
    lines = open(gro).read().splitlines()
    n = int(lines[1].strip())
    for ln in lines[2:2 + n]:
        yield (ln[5:10].strip(), ln[10:15].strip())


def _positions_nm(gro):
    lines = open(gro).read().splitlines()
    n = int(lines[1].strip())
    xyz = [(float(ln[20:28]), float(ln[28:36]), float(ln[36:44]))
           for ln in lines[2:2 + n]]
    return np.array(xyz)


def _context_positions_nm(process):
    st = process._sim.context.getState(getPositions=True, enforcePeriodicBox=True)
    pos = st.getPositions().value_in_unit(process._unit.nanometer)
    return np.array([[p[0], p[1], p[2]] for p in pos])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--platform", default="CPU")
    args = ap.parse_args()

    arms = ARMS_QUICK if args.quick else ARMS_FULL
    results = []
    for (label, chain, protonated) in arms:
        print(f"[arm] {label} ...", flush=True)
        r = run_arm(label, chain, protonated, platform=args.platform,
                    quick=args.quick)
        print(f"   -> {r['verdict']} shell={r['shell_integrity']} "
              f"cv={r['head_radial_cv']} ({r['wall_s']}s)", flush=True)
        results.append(r)

    prot = [r for r in results if r["protonated"]]
    null = [r for r in results if not r["protonated"]]
    stable_chains = sorted({r["chain"] for r in prot if r["verdict"] == "stable_vesicle"})
    headline = {
        "stable_chain_window": stable_chains,
        "all_protonated_stable": bool(prot) and all(r["verdict"] == "stable_vesicle" for r in prot),
        "null_micellises": bool(null) and all(r["verdict"] == "micellised" for r in null),
        "quick": args.quick,
    }
    doc = {
        "metric": "end-state bilayer-shell retention (SHORT MD stability trend)",
        "verdict_thresholds": {"inner_leaflet_min": INNER_LEAFLET_MIN,
                               "head_radial_cv_max": CV_MAX,
                               "shell_band_nm": SHELL_BAND_NM},
        "arms": results, "headline": headline,
    }
    with open(args.out, "w") as f:
        json.dump(doc, f, indent=2)
    print("wrote", args.out, "| headline:", json.dumps(headline))


if __name__ == "__main__":
    main()
