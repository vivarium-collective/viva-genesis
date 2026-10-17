"""The Martini bilayer generator (no OpenMM needed)."""
import tempfile
from viva_genesis.membranes.martini_bilayer import build_pope_bilayer, _POPE_BEADS


def test_bilayer_atom_counts_and_files():
    d = tempfile.mkdtemp()
    s = build_pope_bilayer(d, nx=3, ny=3)
    assert s.n_per_leaflet == 9 and s.n_lipids == 18
    # 18 lipids * 12 beads + water beads.
    gro = open(s.gro_path).read().splitlines()
    n_atoms = int(gro[1])
    assert n_atoms == 18 * len(_POPE_BEADS) + s.n_water
    # top declares the right molecule counts + includes the FF.
    top = open(s.top_path).read()
    assert "POPE 18" in top and f"W {s.n_water}" in top
    assert "martini_v3.0.0.itp" in top


def test_area_per_lipid_geometry():
    d = tempfile.mkdtemp()
    s = build_pope_bilayer(d, nx=4, ny=4, spacing_nm=1.0)
    # box xy = 4*1.0 each; 16 lipids/leaflet -> 1.0 nm^2 each.
    assert abs(s.area_per_lipid_nm2 - 1.0) < 1e-6
