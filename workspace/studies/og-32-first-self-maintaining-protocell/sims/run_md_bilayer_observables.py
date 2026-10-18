#!/usr/bin/env python
"""Short Martini 3 CG-MD of two chain-length bilayer compositions (DLPC/DPPC
phosphatidylcholine stand-ins for the amphiphile chain-length axis, NOT fatty acids) ->
composition-responsive STRUCTURAL observables (bilayer thickness, area per lipid).

Option-B evidence for study 32 (full Gate C): the og-17/og-31 amphiphile composition
axis is acyl TAIL LENGTH (C2 elongation -> longer tails, lower CAC). Here two real
Martini 3 saturated lipids that differ in tail length stand in for that axis:
  DLPC (di-C12:0, 3 tail beads/chain) = SHORTER tail
  DPPC (di-C16:0, 4 tail beads/chain) = LONGER tail
Both have validated Martini 3 itps (martini_v3.0.0_phospholipids_v1.itp). This is an
MD-INFORMED STRUCTURAL PROXY, NOT a PMF-resolved permeability closure.

Builds each bilayer (heads out / tails to midplane, solvated with W), runs a SHORT
MD (minimize + brief equil ramp + ~1 ns), and measures:
  - bilayer thickness   = <z(PO4) upper leaflet> - <z(PO4) lower leaflet>  [nm]
  - hydrophobic span    = z-range of tail beads                           [nm]
  - area per lipid      = box_x * box_y / n_per_leaflet                   [nm^2]
Longer tails -> thicker, more ordered core -> lower permeability (mapped downstream).

Writes JSON to the path given as argv[2]. Self-contained: needs only martini_openmm +
OpenMM + the itp data dir (argv[1]).

    python md_bilayer_observables.py <viva_openmm_data_dir> <out.json> [platform]
"""
from __future__ import annotations

import json
import os
import sys

HEAD_NAMES = {"NC3", "NH3", "PO4", "GL1", "GL2"}
# short production for a bounded run; honest: short MD, structural trend not a
# fully-converged equilibrium value.
MINIMIZE_ITERS = 5000
EQUIL_STEPS = 2000          # @ 2 fs warm-up ramp
PROD_STEPS = 50000          # @ 20 fs ~= 1 ns
NX = NY = 6                 # 36 lipids/leaflet, 72 total
TEMP_K = 322.35             # vent T (matches ThermoConditions)


def parse_lipid_beads(itp_path, resname):
    """Return the bead-name list of ``resname`` from a Martini itp [atoms] block."""
    beads, in_mol, in_atoms, cur = [], False, False, None
    with open(itp_path) as f:
        for raw in f:
            line = raw.split(";")[0].rstrip()
            s = line.strip()
            if s.startswith("[") and "moleculetype" in s:
                in_mol, in_atoms, cur = True, False, None
                continue
            if in_mol and cur is None and s and not s.startswith("["):
                cur = s.split()[0]
                in_mol = False
                continue
            if s.startswith("[") and "atoms" in s:
                in_atoms = (cur == resname)
                continue
            if s.startswith("["):
                in_atoms = False
                continue
            if in_atoms and s:
                parts = s.split()
                if len(parts) >= 5:
                    beads.append(parts[4])
    return beads


def split_beads(beads):
    head = [b for b in beads if b in HEAD_NAMES]
    tailA = [b for b in beads if b.endswith("A") and b not in HEAD_NAMES]
    tailB = [b for b in beads if b.endswith("B") and b not in HEAD_NAMES]
    return head, tailA, tailB


def build_bilayer(out_dir, data_dir, resname, *, nx=NX, ny=NY, spacing=0.9,
                  z_bead=0.30, water_layers=3, water_spacing=0.5):
    itp = os.path.join(data_dir, "martini_v3.0.0_phospholipids_v1.itp")
    beads = parse_lipid_beads(itp, resname)
    head, tailA, tailB = split_beads(beads)
    assert head and tailA and tailB, f"{resname}: parsed beads={beads}"
    nbead = len(beads)
    n_per_leaflet = nx * ny
    lipid_len = (len(head) + len(tailA)) * z_bead

    def place(x0, y0, z_head, direction):
        out = []
        for i, name in enumerate(head):
            out.append((name, (x0, y0, z_head - direction * i * z_bead)))
        z_t0 = z_head - direction * len(head) * z_bead
        for tail, dx in ((tailA, -0.15), (tailB, +0.15)):
            for i, name in enumerate(tail):
                out.append((name, (x0 + dx, y0, z_t0 - direction * i * z_bead)))
        return out

    mid = 0.0
    z_head_up = mid + lipid_len + 0.1
    z_head_dn = mid - lipid_len - 0.1
    atoms = []
    for z_head, direction in ((z_head_up, +1), (z_head_dn, -1)):
        for ix in range(nx):
            for iy in range(ny):
                x0, y0 = (ix + 0.5) * spacing, (iy + 0.5) * spacing
                for name, xyz in place(x0, y0, z_head, direction):
                    atoms.append((resname, name, xyz))
    box_x, box_y = nx * spacing, ny * spacing
    n_water = 0
    for sign, z_start in ((+1, z_head_up + 0.4), (-1, z_head_dn - 0.4)):
        for layer in range(water_layers):
            z = z_start + sign * layer * water_spacing
            for ix in range(nx):
                for iy in range(ny):
                    atoms.append(("W", "W", ((ix + 0.5) * spacing, (iy + 0.5) * spacing, z)))
                    n_water += 1
    z_lo = z_head_dn - 0.4 - water_layers * water_spacing - 0.5
    z_hi = z_head_up + 0.4 + water_layers * water_spacing + 0.5
    box = (box_x, box_y, z_hi - z_lo)

    os.makedirs(out_dir, exist_ok=True)
    gro = os.path.join(out_dir, f"{resname}.gro")
    with open(gro, "w") as f:
        f.write(f"{resname} bilayer (Martini 3)\n{len(atoms)}\n")
        resnum = atomnum = 0
        for rn, atom, (x, y, z) in atoms:
            if rn == "W":
                resnum += 1
            elif atomnum % nbead == 0:
                resnum += 1
            atomnum += 1
            f.write(f"{resnum % 100000:>5d}{rn:<5s}{atom:>5s}{atomnum % 100000:>5d}"
                    f"{x:8.3f}{y:8.3f}{z - z_lo:8.3f}\n")
        f.write(f"{box[0]:10.5f}{box[1]:10.5f}{box[2]:10.5f}\n")

    top = os.path.join(out_dir, f"{resname}.top")
    with open(top, "w") as f:
        f.write(f'#include "{os.path.join(data_dir, "martini_v3.0.0.itp")}"\n')
        f.write(f'#include "{itp}"\n')
        f.write(f'#include "{os.path.join(data_dir, "martini_v3.0.0_solvents_v1.itp")}"\n')
        f.write(f"\n[ system ]\n{resname} bilayer\n\n[ molecules ]\n")
        f.write(f"{resname} {2 * n_per_leaflet}\nW {n_water}\n")
    return gro, top, n_per_leaflet, nbead, head, tailA + tailB


def run_md(gro, top, platform_name):
    import martini_openmm as mo
    from openmm import app, unit, LangevinMiddleIntegrator, Platform

    conf = app.GromacsGroFile(gro)
    box = conf.getPeriodicBoxVectors()
    mtop = mo.MartiniTopFile(top, periodicBoxVectors=box, epsilon_r=15.0)
    system = mtop.create_system(nonbonded_cutoff=1.1 * unit.nanometer)
    integ = LangevinMiddleIntegrator(TEMP_K * unit.kelvin, 1.0 / unit.picosecond,
                                     20.0 * unit.femtosecond)
    plat = Platform.getPlatformByName(platform_name)
    sim = app.Simulation(mtop.topology, system, integ, plat)
    sim.context.setPositions(conf.getPositions())
    sim.minimizeEnergy(maxIterations=MINIMIZE_ITERS)
    # warm-up ramp at 2 fs
    integ.setStepSize(2.0 * unit.femtosecond)
    sim.context.setVelocitiesToTemperature(TEMP_K * unit.kelvin)
    sim.step(EQUIL_STEPS)
    integ.setStepSize(20.0 * unit.femtosecond)
    sim.step(PROD_STEPS)
    st = sim.context.getState(getPositions=True, enforcePeriodicBox=False)
    pos = st.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
    bv = st.getPeriodicBoxVectors(asNumpy=True).value_in_unit(unit.nanometer)
    return pos, (bv[0][0], bv[1][1], bv[2][2])


def observables(pos, boxxyz, n_per_leaflet, nbead, head, tail_names):
    import numpy as np
    pos = np.asarray(pos)
    n_lipids = 2 * n_per_leaflet
    lip = pos[:n_lipids * nbead].reshape(n_lipids, nbead, 3)
    po4_idx = head.index("PO4")
    po4_z = lip[:, po4_idx, 2]
    upper = po4_z[:n_per_leaflet].mean()
    lower = po4_z[n_per_leaflet:].mean()
    thickness = float(abs(upper - lower))
    tail_positions = [i for i, _ in enumerate(head + tail_names)][len(head):]
    tz = lip[:, tail_positions, 2].ravel()
    hydrophobic_span = float(tz.max() - tz.min())
    area_per_lipid = float(boxxyz[0] * boxxyz[1] / n_per_leaflet)
    return {"bilayer_thickness_nm": thickness, "hydrophobic_span_nm": hydrophobic_span,
            "area_per_lipid_nm2": area_per_lipid}


def main():
    data_dir = sys.argv[1]
    out_json = sys.argv[2]
    platform = sys.argv[3] if len(sys.argv) > 3 else "CPU"
    import tempfile
    import time
    results = {}
    for resname, label in (("DLPC", "short_di-C12"), ("DPPC", "long_di-C16")):
        t0 = time.time()
        with tempfile.TemporaryDirectory() as d:
            gro, top, npl, nbead, head, tails = build_bilayer(d, data_dir, resname)
            pos, boxxyz = run_md(gro, top, platform)
            obs = observables(pos, boxxyz, npl, nbead, head, tails)
        obs.update({"resname": resname, "composition": label,
                    "n_tail_beads_per_chain": len([t for t in tails if t.endswith("A")]),
                    "n_lipids": 2 * npl, "wall_s": round(time.time() - t0, 1)})
        results[resname] = obs
        print(f"{resname} ({label}): thickness={obs['bilayer_thickness_nm']:.3f} nm  "
              f"apl={obs['area_per_lipid_nm2']:.3f} nm^2  ({obs['wall_s']}s)", flush=True)
    with open(out_json, "w") as f:
        json.dump({"platform": platform, "temp_k": TEMP_K, "prod_steps": PROD_STEPS,
                   "results": results}, f, indent=2)
    print("WROTE", out_json, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
