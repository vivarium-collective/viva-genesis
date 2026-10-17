"""Generate a runnable Martini 3 amphiphile bilayer (.gro + .top) for study 31/32.

viva-openmm ships the Martini 3 engine + the POPE/phospholipid force fields but no
membrane *system* — so this builds one: a POPE bilayer (two leaflets on an XY grid,
heads out / tails toward the midplane) solvated with Martini W water, written as a
GROMACS ``.gro`` + a ``.top`` that martini_openmm's ``MartiniTopFile`` reads. It is
the pore-/vesicle-free first membrane for the amphiphile-assembly question; the
coordinates are deliberately spread (generous spacing) so energy minimization
relaxes the hand-placed system instead of blowing up.

POPE Martini 3 bead layout (12 beads): NH3 PO4 (head) · GL1 GL2 (glycerol) ·
C1A D2A C3A C4A (sn-1 tail) · C1B C2B C3B C4B (sn-2 tail). The two tails are placed
in parallel columns offset in x so they don't overlap at t=0.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Tuple

# POPE beads in itp order (must match martini_v3.0.0_POPE.itp [atoms]).
_POPE_BEADS = ["NH3", "PO4", "GL1", "GL2",
               "C1A", "D2A", "C3A", "C4A",
               "C1B", "C2B", "C3B", "C4B"]
_HEAD = ["NH3", "PO4", "GL1", "GL2"]   # head/glycerol column
_TAIL_A = ["C1A", "D2A", "C3A", "C4A"]
_TAIL_B = ["C1B", "C2B", "C3B", "C4B"]


def _data_dir() -> str:
    import viva_openmm
    return os.path.join(os.path.dirname(viva_openmm.__file__), "data")


@dataclass
class BilayerSystem:
    gro_path: str
    top_path: str
    n_lipids: int          # total lipids (both leaflets)
    n_per_leaflet: int
    n_water: int
    box: Tuple[float, float, float]   # nm

    @property
    def area_per_lipid_nm2(self) -> float:
        """Initial XY area per lipid per leaflet (the box cross-section / leaflet count)."""
        return (self.box[0] * self.box[1]) / float(self.n_per_leaflet)


def _lipid_positions(x0: float, y0: float, z_head: float, direction: int,
                     z_bead: float) -> List[Tuple[str, Tuple[float, float, float]]]:
    """Place one POPE's 12 beads. ``direction`` +1 = upper leaflet (tails point down),
    -1 = lower leaflet (tails point up). z_head is the headgroup z."""
    out: List[Tuple[str, Tuple[float, float, float]]] = []
    # Head/glycerol column descends from the headgroup toward the midplane.
    for i, name in enumerate(_HEAD):
        z = z_head - direction * i * z_bead
        out.append((name, (x0, y0, z)))
    z_tail0 = z_head - direction * len(_HEAD) * z_bead
    # Two tail columns, offset +/- in x so they don't overlap.
    for tail, dx in ((_TAIL_A, -0.15), (_TAIL_B, +0.15)):
        for i, name in enumerate(tail):
            z = z_tail0 - direction * i * z_bead
            out.append((name, (x0 + dx, y0, z)))
    return out


def build_pope_bilayer(out_dir: str, *, nx: int = 4, ny: int = 4,
                       spacing_nm: float = 1.0, z_bead_nm: float = 0.30,
                       water_layers: int = 3, water_spacing_nm: float = 0.5) -> BilayerSystem:
    """Write ``bilayer.gro`` + ``bilayer.top`` for an ``nx*ny``-per-leaflet POPE bilayer."""
    os.makedirs(out_dir, exist_ok=True)
    n_per_leaflet = nx * ny
    lipid_len = (len(_HEAD) + len(_TAIL_A)) * z_bead_nm   # head + one tail column
    mid = 0.0

    atoms: List[Tuple[str, str, Tuple[float, float, float]]] = []  # (resname, atom, xyz)
    # Upper leaflet: heads at +z, tails toward midplane. Lower leaflet mirrored.
    z_head_up = mid + lipid_len + 0.1
    z_head_dn = mid - lipid_len - 0.1
    for leaflet, (z_head, direction) in enumerate(((z_head_up, +1), (z_head_dn, -1))):
        for ix in range(nx):
            for iy in range(ny):
                x0 = (ix + 0.5) * spacing_nm
                y0 = (iy + 0.5) * spacing_nm
                for name, xyz in _lipid_positions(x0, y0, z_head, direction, z_bead_nm):
                    atoms.append(("POPE", name, xyz))

    lipid_atom_count = len(atoms)
    # Water slabs above the upper heads and below the lower heads.
    box_x = nx * spacing_nm
    box_y = ny * spacing_nm
    n_water = 0
    for sign, z_start in ((+1, z_head_up + 0.4), (-1, z_head_dn - 0.4)):
        for layer in range(water_layers):
            z = z_start + sign * layer * water_spacing_nm
            for ix in range(nx):
                for iy in range(ny):
                    x0 = (ix + 0.5) * spacing_nm
                    y0 = (iy + 0.5) * spacing_nm
                    atoms.append(("W", "W", (x0, y0, z)))
                    n_water += 1

    # Box: xy from the grid; z spans the water slabs with padding.
    z_lo = z_head_dn - 0.4 - water_layers * water_spacing_nm - 0.5
    z_hi = z_head_up + 0.4 + water_layers * water_spacing_nm + 0.5
    box = (box_x, box_y, z_hi - z_lo)

    # Shift all z so the box starts at 0.
    gro_path = os.path.join(out_dir, "bilayer.gro")
    with open(gro_path, "w") as f:
        f.write("Prebiotic POPE bilayer (Martini 3)\n")
        f.write(f"{len(atoms)}\n")
        resnum = 0
        atomnum = 0
        prev_res = None
        for resname, atom, (x, y, z) in atoms:
            # New residue number per lipid (12 beads) / per water bead.
            if resname == "POPE":
                if atomnum % len(_POPE_BEADS) == 0:
                    resnum += 1
            else:
                resnum += 1
            atomnum += 1
            zz = z - z_lo
            f.write(f"{resnum % 100000:>5d}{resname:<5s}{atom:>5s}{atomnum % 100000:>5d}"
                    f"{x:8.3f}{y:8.3f}{zz:8.3f}\n")
        f.write(f"{box[0]:10.5f}{box[1]:10.5f}{box[2]:10.5f}\n")

    data = _data_dir()
    top_path = os.path.join(out_dir, "bilayer.top")
    with open(top_path, "w") as f:
        f.write(f'#include "{os.path.join(data, "martini_v3.0.0.itp")}"\n')
        f.write(f'#include "{os.path.join(data, "martini_v3.0.0_POPE.itp")}"\n')
        f.write(f'#include "{os.path.join(data, "martini_v3.0.0_solvents_v1.itp")}"\n')
        f.write("\n[ system ]\nPrebiotic POPE bilayer\n\n[ molecules ]\n")
        f.write(f"POPE {2 * n_per_leaflet}\n")
        f.write(f"W {n_water}\n")

    assert lipid_atom_count == 2 * n_per_leaflet * len(_POPE_BEADS)
    return BilayerSystem(gro_path=gro_path, top_path=top_path,
                         n_lipids=2 * n_per_leaflet, n_per_leaflet=n_per_leaflet,
                         n_water=n_water, box=box)
