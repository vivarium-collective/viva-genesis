# Spatial transport: FiPy ↔ FEniCS/dolfinx head-to-head

Solver/structural-uncertainty readout for the `spatial_transport` face (full
modeling plan §4.5). Same world, two solvers behind one face
(`model_spatial_transport ∈ {fipy, fenics}`); where they disagree is where the
answer depends on the discretisation, not on the parameters.

Reproduce (both solvers in one env — dolfinx from viva-fenics's pixi env, fipy
pip-installed there, both worktrees on `PYTHONPATH`):

```
FIPY_SOLVERS=scipy \
PYTHONPATH=<viva-genesis-worktree>:<viva-fenics-worktree> \
  pixi run --frozen --manifest-path ~/code/viva-fenics/pixi.toml \
  python scripts/compare_spatial_transport.py --out \
  workspace/references/spatial-transport-solver-comparison.json
```

Raw numbers: `spatial-transport-solver-comparison.json` (this directory).

## 1. Manufactured solution — advection-diffusion boundary layer (Pe = 10)

Steady `−D u'' + w u' = 0`, `u(0)=0, u(1)=1`, analytic
`u(x) = (exp(Pe x) − 1)/(exp(Pe) − 1)`. L2 error vs analytic at matched
resolution:

| resolution | FiPy L2 | dolfinx L2 |
|---|---|---|
| 16 | 5.3e-4 | 2.8e-3 |
| 32 | 1.1e-4 | 7.1e-4 |
| 64 | 2.0e-4 | 1.8e-4 |

Both reproduce the analytic boundary layer. dolfinx P1 converges at a clean
**O(h²)** (orders 2.0, 2.0); FiPy's first-order upwinded FVM is already at the
~1e-4 floor by resolution 32 (its last "rate" is noise against that floor).
**Verdict: both correct; dolfinx is the higher-order discretisation.**

## 2. og-00 vent reactor outlet — identical prescribed drivers

Prescribed serpentinization source (H2 5 mM, alkalinity 3 mM, heat 12 W, flow
1e-3 m/s, pH_eq 10.5), 60 steps:

| readout | FiPy | dolfinx | agreement |
|---|---|---|---|
| outlet temperature (K) | 312.67 | 311.73 | 0.30 % rel |
| outlet pH | 10.494 | 10.494 | exact |
| flux-divergence residual | 2.8e-15 | 3.0e-15 | both ~machine ε |

**Verdict: the two solvers agree on the og-00 outlet (T within 0.3 %, pH
identical) and both conserve flux to machine precision.** The og-00 gates are
solver-agnostic here.

## 3. og-03 thermophoretic trap — enrichment across a pore-length (Pe) sweep

FiPy reports the reduced accumulation-column value `exp(Pe_acc)`; dolfinx reads
enrichment from the **resolved** Soret-drift field (the new weak-form term),
which is numerical-diffusion limited beyond a resolvable Péclet.

| pore length (m) | Pe_acc | FiPy enrichment | dolfinx enrichment | |log10| diff | agree (<1 dex) |
|---|---|---|---|---|---|
| 5.0e-4 | 1.84 | 6.3 | 5.4 | 0.06 | ✓ |
| 1.0e-3 | 3.68 | 39.4 | 29.6 | 0.12 | ✓ |
| 2.0e-3 | 7.35 | 1.56e3 | 2.53e2 | 0.79 | ✓ |
| 3.5e-3 | 12.86 | 3.86e5 | 2.53e2 | 3.18 | ✗ |
| 5.0e-3 | 18.38 | 9.55e7 | 2.53e2 | 5.58 | ✗ |

**Verdict (solver-structural uncertainty, not parameter uncertainty):**
- **Pe_acc ≲ 4 — agreement region.** The resolved FEM field reproduces the
  reduced `exp(Pe)` column to within ~0.1 dex. Either solver is trustworthy.
- **Pe_acc ≳ 13 — solver-sensitive region.** FiPy's reduced model keeps
  climbing to Baaske's >10⁸-fold; the resolved dolfinx field saturates because a
  P1 mesh cannot resolve the sub-micron accumulation boundary layer at that
  Péclet (numerical diffusion). **The answer depends on which model you
  believe:** the reduced column's exponential extrapolation, or the resolved
  field's honest statement that the gradient is under-resolved. This is exactly
  the structural uncertainty §4.5 asks to be measured, and it says the default
  Baaske-favorable pore sits *inside* the solver-sensitive region — the >10⁸
  figure is a reduced-model extrapolation, not a resolved result.

## Takeaways

1. On smooth, resolvable problems (MMS, og-00 outlet) the two solvers agree
   (≤0.3 %), so those gates are solver-agnostic; dolfinx converges at the higher
   order.
2. The og-03 trap's headline >10⁸ enrichment is a **reduced-model** number; a
   resolved FEM solve saturates once Pe_acc exceeds what the mesh resolves. Any
   claim resting on extreme trap enrichment should carry this solver-structural
   caveat (or use adaptive refinement / a finer mesh to push the resolvable
   Péclet up — viva-fenics ships `AdaptiveRefinementStep`).
3. The face makes this a one-line swap (`model_spatial_transport`), so the
   comparison re-runs per study with no new grading code.
