"""Phase 1 — environmental calibration of the serpentinizing vent, worked concretely.

Model Upgrade plan, priority upgrade A / roadmap Phase 1: *build a hierarchical
calibration around observed ultramafic hydrothermal systems; propagate the
inferred distributions through reactive transport; ask what fraction of vent
states consistent with observed systems also satisfy downstream chemical
requirements.* Exit criterion: *posterior probability of viable vent states;
validated mass/charge/energy ledger.*

Pipeline (every step is real; nothing is fitted to pass):

1. **Prior** — the ``vg-data`` package ``vent_environment``: the free
   parameters of the og-00 world with their provenance classes.
2. **Ensemble** — Latin-hypercube draws from that prior, each run through the
   real PHREEQC + FiPy :func:`~viva_genesis.composites.geochemical_world.geochemical_world`
   once per **model class** on the spatial-transport face (convecting wall vs
   prescribed upflow by default; FEniCS when run under pixi), with the
   conservation ledger on. Points PHREEQC rejects (outside its 0-100 °C
   validity) are recorded as failed, not dropped.
3. **Conditioning** — ABC rejection on the package's observation windows
   (Lost City T, pH, dissolved H2; MARHYS 4.0 pending): the posterior is the
   set of prior draws whose settled vent state is consistent with observation.
4. **Posterior prediction** — the fraction of the posterior that also meets
   the package's ``downstream_requirements`` (what og-01's carbon fixation
   needs: H2 ≥ 1 mM at the interface, a ≥ 3-unit pH gradient, T inside
   validity), per model class, plus the cross-class ``structure_agreement``
   and the readouts that discriminate the classes.
5. **Report** — a :class:`~viva_genesis.uq.report.TransitionReport`
   (Feasibility / Robustness / Discrimination + evidence tier), with the
   provenance audit, the ledger verification and an optional Morris
   screening attached.

The ensemble is serial on purpose: the PHREEQC C extension does not survive a
process-pool worker (see ``compute_vent_habitability_grid.py``). ~4 s per
30-step point at ``nx=20``.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np

from ..provenance import ParameterPackage, load_package
from .calibration import (Observation, abc_rejection, consistency_mask, per_observation_masks,
                          posterior_summary)
from .ensemble import paired_class_difference, structure_agreement
from .report import Discrimination, EvidenceTier, Feasibility, Robustness, TransitionReport
from .sampling import sample_package
from .sensitivity import morris

OCEAN_PH = 6.0   # og-01's acidic early-ocean side (hypothetical; the pH-gradient readout uses it)

DEFAULT_CLASSES = (
    {"model_serpentinization": "phreeqc", "model_spatial_transport": "fipy"},
    {"model_serpentinization": "phreeqc", "model_spatial_transport": "fipy_uniform_upflow"},
)

READOUTS = ("settled_temperature_C", "settled_pH", "dissolved_H2_mmol_kg", "delta_pH",
            "settled_H2_flux", "settled_pe")


def class_label(model_kwargs: Mapping[str, str]) -> str:
    return "+".join(f"{k[len('model_'):]}={v}" for k, v in sorted(model_kwargs.items()))


# --------------------------------------------------------------------------- #
# one point
# --------------------------------------------------------------------------- #
def run_point(core, config: Mapping[str, float], model_kwargs: Mapping[str, str], *,
              n_steps: int = 30, nx: int = 20) -> dict:
    """Run the geochemical world once; return the Phase-1 readouts (NaN + error on failure)."""
    from process_bigraph import Composite, gather_emitter_results
    from ..composites.geochemical_world import (PHASE1_REDUCERS, dissolved_H2_mmol_kg,
                                                geochemical_world)

    gen_kwargs = {k: v for k, v in config.items()
                  if k in ("flow_velocity", "olivine_rate", "pyroxene_fraction", "fe_fraction",
                           "heat_to_fluid_fraction", "fluid_dic")}
    t0 = time.time()
    try:
        doc = geochemical_world(core, nx=int(nx), **gen_kwargs, **model_kwargs)
        sim = Composite({"state": doc}, core=core)
        sim.run(float(n_steps))
        rows = gather_emitter_results(sim)[("emitter",)]
        out = {k: float(fn(rows)) for k, fn in PHASE1_REDUCERS.items()}
        out["dissolved_H2_mmol_kg"] = dissolved_H2_mmol_kg(
            rows, flow_velocity=float(config["flow_velocity"]),
            flux_area=float(config.get("flux_area", 60.0)))
        out["delta_pH"] = out["settled_pH"] - OCEAN_PH
        out["ok"] = True
        out["error"] = None
    except Exception as exc:  # the engine rejected the point (e.g. T out of PHREEQC range)
        out = {k: float("nan") for k in PHASE1_REDUCERS}
        out.update({"dissolved_H2_mmol_kg": float("nan"), "delta_pH": float("nan"),
                    "ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]})
    out["wall_s"] = time.time() - t0
    return out


# --------------------------------------------------------------------------- #
# the ensemble
# --------------------------------------------------------------------------- #
@dataclass
class EnvironmentEnsemble:
    package_name: str
    package_version: str
    n_draws: int
    seed: int
    n_steps: int
    nx: int
    draws: list[dict]                               # prior draws {parameter_id: value}
    classes: list[dict]                             # model kwargs per class
    outcomes: dict[str, list[dict]]                 # class_label -> one outcome dict per draw
    morris: dict | None = None
    meta: dict = field(default_factory=dict)

    def labels(self) -> list[str]:
        return [class_label(c) for c in self.classes]

    def to_dict(self) -> dict:
        return {
            "package": {"name": self.package_name, "version": self.package_version},
            "n_draws": self.n_draws, "seed": self.seed, "n_steps": self.n_steps, "nx": self.nx,
            "draws": self.draws, "classes": self.classes, "outcomes": self.outcomes,
            "morris": self.morris, "meta": self.meta,
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=1, default=_json_default))

    @classmethod
    def from_dict(cls, d: Mapping) -> "EnvironmentEnsemble":
        return cls(package_name=d["package"]["name"], package_version=str(d["package"]["version"]),
                   n_draws=int(d["n_draws"]), seed=int(d["seed"]), n_steps=int(d["n_steps"]),
                   nx=int(d["nx"]), draws=list(d["draws"]), classes=list(d["classes"]),
                   outcomes={k: list(v) for k, v in d["outcomes"].items()},
                   morris=d.get("morris"), meta=dict(d.get("meta") or {}))

    @classmethod
    def load(cls, path: str | Path) -> "EnvironmentEnsemble":
        return cls.from_dict(json.loads(Path(path).read_text()))


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    raise TypeError(f"not JSON serialisable: {type(o)}")


def vent_environment_ensemble(*, n_draws: int = 32, seed: int = 0, n_steps: int = 30, nx: int = 20,
                              classes: Sequence[Mapping[str, str]] = DEFAULT_CLASSES,
                              package: ParameterPackage | str = "vent_environment",
                              only: Sequence[str] | None = None,
                              progress: Callable[[str], None] | None = None,
                              core=None) -> EnvironmentEnsemble:
    """Draw the prior and run every draw through every model class (serial, tolerant)."""
    from ..core import build_core
    pkg = load_package(package) if isinstance(package, str) else package
    rng = np.random.default_rng(seed)
    draws = sample_package(pkg, n_draws, rng, method="lhs", only=only)
    core = core or build_core()
    outcomes: dict[str, list[dict]] = {}
    t0 = time.time()
    for ci, model_kwargs in enumerate(classes):
        label = class_label(model_kwargs)
        rows = []
        for i, draw in enumerate(draws):
            cfg = pkg.to_config(values=draw)
            rows.append(run_point(core, cfg, model_kwargs, n_steps=n_steps, nx=nx))
            if progress:
                progress(f"[{label}] {i + 1}/{n_draws} ok={rows[-1]['ok']} "
                         f"T={rows[-1]['settled_temperature_C']:.1f}C pH={rows[-1]['settled_pH']:.2f} "
                         f"H2={rows[-1]['dissolved_H2_mmol_kg']:.2f}mM ({time.time() - t0:.0f}s)")
        outcomes[label] = rows
    return EnvironmentEnsemble(
        package_name=pkg.name, package_version=pkg.version, n_draws=n_draws, seed=seed,
        n_steps=n_steps, nx=nx, draws=draws, classes=[dict(c) for c in classes],
        outcomes=outcomes,
        meta={"wall_s": time.time() - t0, "readouts": list(READOUTS),
              "free_parameters": [p.id for p in pkg.free()], "ocean_pH": OCEAN_PH,
              "provenance_audit": pkg.audit()},
    )


# --------------------------------------------------------------------------- #
# conditioning + posterior prediction
# --------------------------------------------------------------------------- #
def package_observations(pkg: ParameterPackage) -> list[Observation]:
    return [Observation.from_package_entry(k, v) for k, v in pkg.observations.items()
            if v.get("status", "available") != "pending" and (v.get("low") is not None or v.get("high") is not None)]


def package_requirements(pkg: ParameterPackage) -> list[Observation]:
    reqs = getattr(pkg, "requirements", None)
    raw = reqs if reqs is not None else _raw_requirements(pkg)
    return [Observation.from_package_entry(k, v) for k, v in raw.items()
            if v.get("low") is not None or v.get("high") is not None]


def _raw_requirements(pkg: ParameterPackage) -> dict:
    # ParameterPackage keeps only the standard blocks; re-read the YAML for the
    # downstream_requirements block of a packaged file.
    from ..provenance import data_dir
    import yaml
    path = data_dir() / f"{pkg.name}.yaml"
    if not path.exists():
        return {}
    return dict((yaml.safe_load(path.read_text()) or {}).get("downstream_requirements") or {})


def condition_ensemble(ens: EnvironmentEnsemble, package: ParameterPackage | None = None) -> dict:
    """ABC-condition every class on the observation windows and evaluate the downstream requirements."""
    pkg = package or load_package(ens.package_name)
    observations = package_observations(pkg)
    requirements = package_requirements(pkg)
    per_class = {}
    consistent_masks, viable_masks = {}, {}
    for label, rows in ens.outcomes.items():
        abc = abc_rejection(rows, observations)
        req_mask = consistency_mask(rows, requirements) if requirements else np.ones(len(rows), bool)
        viable = abc.mask & req_mask
        consistent_masks[label] = abc.mask
        viable_masks[label] = viable
        n_ok = int(sum(1 for r in rows if r.get("ok")))
        per_obs = {k: int(v.sum()) for k, v in per_observation_masks(rows, observations).items()}
        binding = min(per_obs, key=per_obs.get) if per_obs else ""
        ledger_ok = [float(r.get("ledger_ok", 0.0)) for r in rows if r.get("ok")]
        per_class[label] = {
            "n_runs": len(rows), "n_ok": n_ok, "n_failed": len(rows) - n_ok,
            "n_consistent": int(abc.mask.sum()),
            "p_consistent": float(abc.mask.mean()) if rows else float("nan"),
            "per_observation": per_obs,
            "binding_observation": binding,
            "n_viable": int(viable.sum()),
            "p_viable_given_consistent": (float(viable.sum() / abc.mask.sum()) if abc.mask.sum() else float("nan")),
            "p_viable": float(viable.mean()) if rows else float("nan"),
            "per_requirement": ({k: int(v.sum()) for k, v in per_observation_masks(rows, requirements).items()}
                                if requirements else {}),
            "posterior": posterior_summary(ens.draws, abc.mask.astype(float), ens.meta.get("free_parameters")),
            "prior": posterior_summary(ens.draws, np.ones(len(ens.draws)), ens.meta.get("free_parameters")),
            "ledger": {
                "all_ok": bool(ledger_ok) and all(v >= 1.0 for v in ledger_ok),
                "max_mass_residual": max((float(r.get("max_mass_residual", 0.0)) for r in rows if r.get("ok")), default=float("nan")),
                "max_energy_residual": max((float(r.get("max_energy_residual", 0.0)) for r in rows if r.get("ok")), default=float("nan")),
                "max_charge_residual": max((float(r.get("charge_residual_max", 0.0)) for r in rows if r.get("ok")), default=float("nan")),
                "max_flux_residual": max((float(r.get("flux_residual_max", 0.0)) for r in rows if r.get("ok")), default=float("nan")),
                "energy_directionality": bool(ledger_ok) and all(float(r.get("energy_directionality", 0.0)) >= 1.0 for r in rows if r.get("ok")),
            },
        }
    cross = {
        "consistent": structure_agreement(consistent_masks),
        "viable": structure_agreement(viable_masks),
    }
    labels = list(ens.outcomes)
    discrimination = (paired_class_difference({l: ens.outcomes[l] for l in labels[:2]}, list(READOUTS))
                      if len(labels) >= 2 else {})
    return {
        "observations": [o.to_dict() for o in observations],
        "requirements": [o.to_dict() for o in requirements],
        "per_class": per_class,
        "cross_class": cross,
        "discrimination": discrimination,
    }


def vent_calibration_report(ens: EnvironmentEnsemble, conditioned: dict | None = None,
                            headline_class: str | None = None) -> TransitionReport:
    """Assemble the Feasibility / Robustness / Discrimination triple for Phase 1."""
    cond = conditioned or condition_ensemble(ens)
    labels = list(ens.outcomes)
    head = headline_class or labels[0]
    pc = cond["per_class"][head]
    rows = ens.outcomes[head]
    obs = cond["observations"]
    admissibility = "settled vent state inside every observation window: " + "; ".join(
        f"{o['name']} in [{o.get('low', '-inf')}, {o.get('high', '+inf')}] {o.get('units', '')}".strip()
        for o in obs)
    # a supporting parameterization: the first viable draw of the headline class
    example = {}
    pkg = load_package(ens.package_name)
    reqs = package_requirements(pkg)
    observations = package_observations(pkg)
    viable = consistency_mask(rows, observations) & (consistency_mask(rows, reqs) if reqs else True)
    if viable.any():
        i = int(np.flatnonzero(viable)[0])
        example = {"draw": ens.draws[i], "readouts": {k: rows[i].get(k) for k in READOUTS}}
    feas = Feasibility(
        feasible=bool(pc["n_viable"] > 0),
        n_admissible=int(pc["n_consistent"]),
        n_supporting=int(pc["n_viable"]),
        example=example,
        admissibility=admissibility,
    )
    cc = cond["cross_class"]["viable"]
    rob = Robustness(
        fraction=float(pc["p_viable_given_consistent"]),
        by_class={l: float(cond["per_class"][l]["p_viable_given_consistent"]) for l in labels},
        structure_agreement=float(cc["agreement"]) if len(labels) > 1 else None,
        structure_uncertainty=float(cc["structure_uncertainty"]) if len(labels) > 1 else None,
        n_posterior=int(pc["n_consistent"]), n_prior=int(pc["n_runs"]),
        binding_observation=str(pc["binding_observation"]),
        note=("fraction of vent states consistent with observation that also satisfy the "
              "downstream chemical requirements (posterior predictive); classes = model_spatial_transport"),
    )
    disc_rows = sorted(
        [{"readout": k, **v} for k, v in cond["discrimination"].items() if np.isfinite(v.get("d", np.nan))],
        key=lambda r: -abs(r["d"]))
    disc = Discrimination(
        alternatives=labels[1:],
        discriminating=[r for r in disc_rows if abs(r["d"]) >= 0.5],
        non_discriminating=[r["readout"] for r in disc_rows if abs(r["d"]) < 0.5],
        proposed_perturbations=[
            "vary flow_velocity across the washout band: the convecting vs uniform-upflow classes "
            "separate on outlet temperature, not on pH or H2",
            "attach MARHYS 4.0 and condition on the ultramafic-vent population instead of Lost City alone",
            "swap the geochemistry engine (Reaktoro / PFLOTRAN on the serpentinization face) to test "
            "database / activity-model dependence of the pH endmember",
        ],
        note="paired standardised difference d between model classes on identical prior draws",
    )
    nv = {"ok": bool(pc["ledger"]["all_ok"]),
          "mass_residual": pc["ledger"]["max_mass_residual"],
          "energy_residual": pc["ledger"]["max_energy_residual"],
          "charge_residual": pc["ledger"]["max_charge_residual"],
          "flux_residual": pc["ledger"]["max_flux_residual"],
          "energy_directionality": pc["ledger"]["energy_directionality"],
          "n_failed_points": pc["n_failed"]}
    return TransitionReport(
        transition="Phase 1 — a physically self-consistent serpentinizing vent sustains the conditions downstream chemistry requires",
        tier=EvidenceTier.MECHANISTIC_PREDICTION,
        feasibility=feas, robustness=rob, discrimination=disc,
        gate="posterior-viable-vent-fraction",
        model_classes=labels,
        provenance_audit=dict(ens.meta.get("provenance_audit") or {}),
        numerical_verification=nv,
        sensitivity=dict(ens.morris or {}),
        meta={"n_draws": ens.n_draws, "seed": ens.seed, "n_steps": ens.n_steps, "nx": ens.nx,
              "headline_class": head, "package": f"{ens.package_name} v{ens.package_version}",
              "conditioning": "ABC rejection on observation windows (uniform likelihood)",
              "marhys": "pending — Lost City windows only"},
    )


# --------------------------------------------------------------------------- #
# Morris screening of the prior (which parameters control the conditioning readouts)
# --------------------------------------------------------------------------- #
class _CachedWorld:
    """Memoise world runs by parameter point so several readouts share one Morris design."""

    def __init__(self, core, pkg: ParameterPackage, model_kwargs: Mapping[str, str], n_steps: int, nx: int):
        self.core, self.pkg, self.model_kwargs, self.n_steps, self.nx = core, pkg, dict(model_kwargs), n_steps, nx
        self.cache: dict[tuple, dict] = {}
        self.n_runs = 0

    def __call__(self, x: Mapping[str, float]) -> dict:
        key = tuple(sorted((k, round(float(v), 12)) for k, v in x.items()))
        if key not in self.cache:
            values = {**self.pkg.nominal(), **{k: float(v) for k, v in x.items()}}
            self.cache[key] = run_point(self.core, self.pkg.to_config(values=values), self.model_kwargs,
                                        n_steps=self.n_steps, nx=self.nx)
            self.n_runs += 1
        return self.cache[key]


def morris_screening(*, r: int = 4, levels: int = 4, seed: int = 0, n_steps: int = 30, nx: int = 20,
                     model_kwargs: Mapping[str, str] = DEFAULT_CLASSES[0],
                     package: ParameterPackage | str = "vent_environment",
                     readouts: Sequence[str] = ("settled_temperature_C", "settled_pH", "dissolved_H2_mmol_kg"),
                     core=None, progress: Callable[[str], None] | None = None) -> dict:
    """Morris elementary effects of the free parameters on the conditioning readouts."""
    from ..core import build_core
    pkg = load_package(package) if isinstance(package, str) else package
    core = core or build_core()
    world = _CachedWorld(core, pkg, model_kwargs, n_steps, nx)
    free = pkg.free()
    bounds = {p.id: p.bounds() for p in free}
    log_params = {p.id for p in free if p.distribution.kind in ("loguniform", "lognormal")}
    out = {"r": r, "levels": levels, "seed": seed, "class": class_label(model_kwargs),
           "bounds": {k: list(v) for k, v in bounds.items()}, "log_params": sorted(log_params),
           "readouts": {}}
    for ro in readouts:
        rng = np.random.default_rng(seed)   # same trajectories for every readout -> cache hits
        res = morris(lambda x, _ro=ro: world(x)[_ro], bounds, r=r, levels=levels, rng=rng,
                     log_params=log_params, tolerant=True)
        out["readouts"][ro] = res.to_dict()
        if progress:
            progress(f"[morris] {ro}: ranking {res.ranking} ({world.n_runs} world runs so far)")
    out["n_world_runs"] = world.n_runs
    return out


__all__ = ["OCEAN_PH", "DEFAULT_CLASSES", "READOUTS", "class_label", "run_point",
           "EnvironmentEnsemble", "vent_environment_ensemble", "package_observations",
           "package_requirements", "condition_ensemble", "vent_calibration_report",
           "morris_screening"]
