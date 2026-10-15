"""Calibrate the multisolute pore surrogate against the viva-fenics FEM reference.

The reduced surrogate (``MultisolutePoreSurrogateProcess``) models single-species
steady enrichment as

    E = exp( geom * S_T * dT * (1 - exp(-Pe/pe0)) * (1 - porosity) * L )

The two constants ``geom`` (pore-geometry accumulation factor) and ``pe0``
(convective-enhancement saturation Peclet) are fit here to the REAL dolfinx 3-D
pore solve (``viva_fenics.fem_convergence.run_pore_enrichment``) over a
(Peclet x Soret) grid, and the surrogate's max relative error on that grid is
reported — the plan §4.6 requirement to "report the surrogate's max error beside
the map". The fitted constants are pasted into ``_SURROGATE`` in
``viva_genesis/multisolute_localization.py``.

Run under viva-fenics's pixi env with viva-genesis + viva-fenics on PYTHONPATH:

    PYTHONPATH=<viva-genesis> pixi run --frozen --manifest-path <viva-fenics>/pixi.toml \
        python <viva-genesis>/scripts/calibrate_pore_surrogate.py
"""
from __future__ import annotations

import numpy as np

from viva_fenics.fem_convergence import run_pore_enrichment

# nondimensional matched to the FEM solve (fem_convergence: L=1, dT=30, porosity
# not applied in the single-species reference, so porosity=0 here).
DT = 30.0
L = 1.0
POROSITY = 0.0
PECLETS = (2.0, 4.0, 8.0, 16.0, 30.0)
SORETS = (0.04, 0.08, 0.14)


def _fem_grid():
    rows = []
    for pe in PECLETS:
        for sT in SORETS:
            # run_pore_enrichment hardcodes dT=30 (matched by DT above).
            r = run_pore_enrichment(peclet=pe, soret=sT, h_throat=0.05, n_steps=120)
            rows.append((pe, sT, r["enrichment"]))
            print(f"  FEM  Pe={pe:5.1f}  S_T={sT:.2f}  E={r['enrichment']:.4f}")
    return rows


def _fit(rows):
    pe = np.array([r[0] for r in rows])
    sT = np.array([r[1] for r in rows])
    E = np.array([r[2] for r in rows])
    logE = np.log(np.maximum(E, 1.0 + 1e-9))  # enrichment >= 1 in this regime
    best = None
    # In a FLOW-THROUGH pore, thermophoretic accumulation is strongest at low Pe
    # (diffusion-dominated) and washes out as advection dominates, so the
    # convective factor DECREASES with Pe: g(Pe) = 1/(1 + Pe/pe0).
    for pe0 in np.linspace(0.5, 60.0, 600):
        x = sT * DT / (1.0 + pe / pe0) * (1.0 - POROSITY) * L
        geom = float(np.dot(x, logE) / np.dot(x, x))  # least-squares slope, no intercept
        pred = geom * x
        resid = float(np.sum((pred - logE) ** 2))
        if best is None or resid < best[0]:
            best = (resid, geom, pe0)
    _, geom, pe0 = best
    # max relative error on enrichment (not log)
    x = sT * DT / (1.0 + pe / pe0) * (1.0 - POROSITY) * L
    E_sur = np.exp(geom * x)
    rel = np.abs(E_sur - E) / np.maximum(E, 1e-9)
    return geom, pe0, float(np.max(rel)), float(np.mean(rel))


def main():
    print("Running FEM reference grid (real dolfinx 3-D pore)...")
    rows = _fem_grid()
    geom, pe0, max_err, mean_err = _fit(rows)
    print("\n=== calibrated surrogate constants ===")
    print(f"  geom = {geom:.4f}")
    print(f"  pe0  = {pe0:.4f}")
    print(f"  surrogate max rel error vs FEM on grid = {max_err:.1%}")
    print(f"  surrogate mean rel error vs FEM on grid = {mean_err:.1%}")
    print("\nPaste into _SURROGATE in viva_genesis/multisolute_localization.py:")
    print(f'  _SURROGATE = {{"geom": {geom:.4f}, "pe0": {pe0:.4f}, "coloc_k": 1.0}}')


if __name__ == "__main__":
    main()
