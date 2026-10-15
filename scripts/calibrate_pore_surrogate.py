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
# not applied in the single-species reference, so porosity=0 here). The Soret
# grid now spans up to ~1.0 (the scale~8 regime where the narrow-range fit broke
# down) so geom/pe0 hold across the whole phase map.
DT = 30.0
L = 1.0
POROSITY = 0.0
PECLETS = (2.0, 4.0, 8.0, 16.0, 30.0)
SORETS = (0.05, 0.15, 0.30, 0.60, 1.00)


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


def _calibrate_adsorption(peclet=4.0, soret=0.3):
    """Fit the kinetic-adsorption contact time ``tau_contact``: run the FEM with
    and without adsorption and match the surrogate's kinetic mobile fraction
    ``1 - (k_ads/ktot)(1 - exp(-ktot*tau))`` to the FEM's effective mobile
    fraction (E_with / E_without). At prebiotic rates the FEM barely adsorbs, so
    the instant-equilibrium ``k_des/(k_ads+k_des)`` is wrong and a finite tau is
    needed."""
    from viva_fenics.fem_convergence import run_pore_enrichment  # noqa: F401
    # single-species helper reused via run_pore_enrichment doesn't take k_ads, so
    # call the multisolute step directly through a tiny inline run.
    import numpy as np
    from dolfinx import fem
    from viva_fenics.fem_multisolute import enrichment, multisolute_pore_step
    from viva_fenics.fem_pore3d import build_pore3d_mesh

    def _E(k_ads, k_des):
        dom, ft, mk = build_pore3d_mesh(h_throat=0.05)
        V = fem.functionspace(dom, ("Lagrange", 1)); n = V.dofmap.index_map.size_local
        z = V.tabulate_dof_coordinates()[:, 2]; T = 330.0 - DT * z; w = peclet * 0.05
        sp = [{"name": "t", "dissolved": np.zeros(n), "adsorbed": np.zeros(n), "D": 0.05,
               "soret": soret, "inlet": 1.0, "k_ads": k_ads, "k_des": k_des, "k_deg": 0.0}]
        for _ in range(120):
            sp = multisolute_pore_step(dom, V, ft, mk, sp, dt=0.02, velocity=(0, 0, w), temperature_array=T)
        return enrichment(dom, V, ft, mk, sp[0]["dissolved"])

    E0 = _E(0.0, 5e-4)
    fem_mobile = {}
    for k_ads in (1e-3, 5e-3, 2e-2, 1e-1):
        fem_mobile[k_ads] = _E(k_ads, 5e-4) / E0
    # fit tau: minimise error of kinetic mobile vs fem_mobile
    best = None
    for tau in np.linspace(0.1, 5.0, 500):
        err = 0.0
        for k_ads, fm in fem_mobile.items():
            ktot = k_ads + 5e-4
            m = 1.0 - (k_ads / ktot) * (1.0 - np.exp(-ktot * tau))
            err += (m - fm) ** 2
        if best is None or err < best[0]:
            best = (err, tau)
    return best[1], fem_mobile


def main():
    print("Running FEM reference grid (real dolfinx 3-D pore)...")
    rows = _fem_grid()
    geom, pe0, max_err, mean_err = _fit(rows)
    print(f"\nSoret fit (wide range): geom={geom:.4f} pe0={pe0:.4f} "
          f"max_err={max_err:.1%} mean_err={mean_err:.1%}")
    print("\nCalibrating kinetic adsorption contact time...")
    tau, fem_mobile = _calibrate_adsorption()
    print(f"  FEM effective mobile fractions: "
          f"{ {k: round(v, 3) for k, v in fem_mobile.items()} }")
    print(f"  tau_contact = {tau:.3f}")
    print("\nPaste into _SURROGATE in viva_genesis/multisolute_localization.py:")
    print(f'  _SURROGATE = {{"geom": {geom:.4f}, "pe0": {pe0:.4f}, "tau_contact": {tau:.3f}}}')


if __name__ == "__main__":
    main()
