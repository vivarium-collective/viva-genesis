"""Parameter-sweep harness — turn a composite's single run into a decision surface.

A composite answers *"what happens at THIS parameter point?"*. A campaign claim is
about a **region**: where in parameter space does the transition occur, and where
does it fail? This is the viz plan's **Decision view** — "don't show a representative
successful run; show the physical region in which the hypothesis works, and the
neighbouring regions in which it does not."

``sweep_grid`` runs a registered composite generator over an N-D parameter grid,
reduces each run to one or more decision scalars (via module-level reducer
functions), and returns the surfaces + axis coordinates so a phase-map viewer can
draw the pass/fail boundary. Serial by default; ``n_jobs > 1`` fans the points out
over a process pool (each worker builds its own ``core``), and the same point
function is what a Ray driver calls for heavy sweeps on the mini.

**Model class as a categorical axis** (Model Upgrade plan, Process Bigraph
principle). An axis whose values are strings — e.g.
``{"model_spatial_transport": ["fipy", "fenics"]}`` — is swept exactly like a
numeric one: the generator receives the string, resolves the class through
``viva_genesis.models``, and the resulting surface has one slice per model
class. ``viva_genesis.uq.ensemble`` then reduces such a result to
``pass_fraction`` per class and ``structure_agreement`` across classes, which is
how parameter uncertainty is separated from model-structure uncertainty.

Design constraints that keep the parallel path honest:
  * The generator must be a **module-level** callable (``generator(core, **kwargs)``
    returning a composite doc) so it pickles by reference.
  * Every reducer must likewise be **module-level** (no lambdas/closures) for the
    same reason. ``sweep.py`` ships only generic reducers; stage-specific ones live
    next to their composite.
"""
from __future__ import annotations

import itertools
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

import numpy as np


@dataclass
class SweepResult:
    """An N-D decision surface over a parameter grid.

    ``axis_order`` fixes the axis sequence; ``axes[name]`` holds each axis's
    coordinate values (a float array for a numeric axis, an object array of
    strings for a categorical / model-class axis); ``surfaces[name]`` is an N-D
    array (shape = the axis lengths in order) of one reduced scalar. ``meta``
    carries provenance (generator, fixed params, n_steps, categorical axes).
    """

    axis_order: list[str]
    axes: dict[str, np.ndarray]
    surfaces: dict[str, np.ndarray]
    meta: dict = field(default_factory=dict)

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(len(self.axes[a]) for a in self.axis_order)

    def primary(self) -> np.ndarray:
        """The first declared surface — the headline decision metric."""
        return self.surfaces[next(iter(self.surfaces))]

    def categorical_axes(self) -> list[str]:
        """Axes swept over model classes / labels rather than numbers."""
        return [a for a in self.axis_order if self.axes[a].dtype.kind in ("U", "O", "S")]

    def slice_along(self, axis: str, value) -> "SweepResult":
        """The sub-result at ``axis == value`` (drops that axis)."""
        i = self.axis_order.index(axis)
        vals = list(self.axes[axis])
        j = vals.index(value)
        taker = [slice(None)] * len(self.axis_order)
        taker[i] = j
        return SweepResult(
            axis_order=[a for a in self.axis_order if a != axis],
            axes={a: v for a, v in self.axes.items() if a != axis},
            surfaces={k: s[tuple(taker)] for k, s in self.surfaces.items()},
            meta={**self.meta, "sliced": {**self.meta.get("sliced", {}), axis: value}},
        )


def _is_numeric_axis(values) -> bool:
    try:
        np.asarray(list(values), dtype=float)
        return not any(isinstance(v, str) for v in values)
    except (TypeError, ValueError):
        return False


def _run_point(generator, kwargs, n_steps, reducers, tolerant=False):
    """Build → run → reduce ONE grid point. Module-level so the pool can pickle it.

    Each worker builds its own ``core`` (process-bigraph cores are not picklable and
    hold C-extension handles). Returns ``{reducer_name: scalar}``.

    ``tolerant`` catches a failed point (e.g. a parameter combination the underlying
    engine rejects — PHREEQC's LLNL aqueous model is only valid 0–100 °C, so an
    over-reacted / under-flushed vent point raises "Temperature out of range") and
    returns NaN for every reducer instead of aborting the whole sweep. The NaN then
    reads as "outside the viable window" in the phase map, which is physically correct:
    that corner is a FAIL, not a missing datum.
    """
    from process_bigraph import Composite, gather_emitter_results

    from .core import build_core

    try:
        core = build_core()
        doc = generator(core, **kwargs)
        sim = Composite({"state": doc}, core=core)
        sim.run(float(n_steps))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {name: float(fn(rows)) for name, fn in reducers.items()}
    except Exception:
        if tolerant:
            return {name: float("nan") for name in reducers}
        raise


def sweep_grid(
    generator: Callable,
    axes: Mapping[str, Sequence],
    *,
    reduce: Mapping[str, Callable],
    fixed: Mapping[str, object] | None = None,
    n_steps: int = 120,
    n_jobs: int | str = 1,
    tolerant: bool = False,
) -> SweepResult:
    """Sweep ``generator`` over the Cartesian product of ``axes``.

    Args:
        generator: module-level ``generator(core, **kwargs) -> doc``.
        axes: ordered ``{param_name: values}``; the grid is their Cartesian product.
            Numeric values form a float axis; string values form a **categorical**
            axis (a model class, e.g. ``model_spatial_transport``) and are passed to
            the generator verbatim.
        reduce: ``{surface_name: reducer(rows) -> float}`` (module-level functions).
        fixed: param overrides held constant across the grid.
        n_steps: steps to run each point.
        n_jobs: ``1`` serial; integer ``>1`` fans out over a process pool;
            ``"ray"`` fans out over a Ray cluster (one Ray task per grid point,
            the core rebuilt per worker) -- the standing rule for heavy phase-map
            sweeps on the mini (full modeling plan section 4.6). Ray is an
            optional import, serialised with cloudpickle (so the closure reducers
            ``last``/``peak`` work on the Ray path, unlike the process pool).
        tolerant: when True, a point that raises is recorded as NaN for every surface
            rather than aborting the sweep (default False — the existing strict
            behaviour). Use for engines that reject part of the swept domain (e.g.
            PHREEQC's 0–100 °C aqueous-model validity): the NaN corner reads as a
            FAIL region in the phase map, which is physically correct.

    Returns:
        A :class:`SweepResult` with one N-D surface per reducer.
    """
    fixed = dict(fixed or {})
    axis_order = list(axes.keys())
    axis_vals: dict[str, np.ndarray] = {}
    categorical: list[str] = []
    for a in axis_order:
        vals = list(axes[a])
        if _is_numeric_axis(vals):
            axis_vals[a] = np.asarray(vals, dtype=float)
        else:
            axis_vals[a] = np.asarray([str(v) for v in vals], dtype=object)
            categorical.append(a)
    shape = tuple(len(axis_vals[a]) for a in axis_order)

    # Every index tuple + its parameter kwargs, in row-major order.
    index_tuples = list(itertools.product(*[range(n) for n in shape]))
    point_kwargs = []
    for idx in index_tuples:
        kw = dict(fixed)
        for a, i in zip(axis_order, idx):
            v = axis_vals[a][i]
            kw[a] = str(v) if a in categorical else float(v)
        point_kwargs.append(kw)

    surfaces = {name: np.full(shape, np.nan) for name in reduce}

    if n_jobs == 1:
        results = [_run_point(generator, kw, n_steps, reduce, tolerant) for kw in point_kwargs]
    elif n_jobs == "ray":
        # Ray-parallel path for heavy sweeps on the mini (plan 4.6). One task per
        # grid point; each worker rebuilds its own (unpicklable) core inside
        # _run_point. Ray serialises with cloudpickle, so closure reducers work.
        import ray  # optional dependency — only needed for the mini path
        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True)
        _remote = ray.remote(_run_point)
        futures = [
            _remote.remote(generator, kw, n_steps, reduce, tolerant)
            for kw in point_kwargs
        ]
        results = ray.get(futures)
    else:
        with ProcessPoolExecutor(max_workers=int(n_jobs)) as ex:
            results = list(
                ex.map(
                    _run_point,
                    itertools.repeat(generator),
                    point_kwargs,
                    itertools.repeat(n_steps),
                    itertools.repeat(reduce),
                    itertools.repeat(tolerant),
                )
            )

    for idx, res in zip(index_tuples, results):
        for name, val in res.items():
            surfaces[name][idx] = val

    return SweepResult(
        axis_order=axis_order,
        axes=axis_vals,
        surfaces=surfaces,
        meta={
            "generator": getattr(generator, "__qualname__", str(generator)),
            "fixed": fixed,
            "n_steps": int(n_steps),
            "n_points": len(point_kwargs),
            "categorical_axes": categorical,
        },
    )


# ----------------------------------------------------------------------------
# Generic reducers (module-level → picklable for the parallel path).
# Stage-specific reducers live beside their composite (see phase_maps.py).
# ----------------------------------------------------------------------------
def last(key: str) -> Callable:
    """Reducer factory: settled (final-row) value of an emitted key.

    NOTE: returns a closure — usable in the **serial** path only. For the parallel
    path, write a named module-level reducer instead.
    """
    def _reduce(rows):
        return rows[-1].get(key, float("nan")) if rows else float("nan")
    return _reduce


def peak(key: str) -> Callable:
    """Reducer factory: peak value of an emitted key across the run (serial only)."""
    def _reduce(rows):
        return max((r.get(key, float("-inf")) for r in rows), default=float("nan"))
    return _reduce
