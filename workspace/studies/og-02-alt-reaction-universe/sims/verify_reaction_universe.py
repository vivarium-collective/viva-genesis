#!/usr/bin/env python
"""Numerical verification of the Phase-3 network classes (og-02-alt-reaction-universe).

Per the roadmap's Phase-3 verification column, for each proto_metabolism class
(reaction_universe, null_network seed 0, curated_rtca) under the Phase-1 feed:

* **flux-control analysis** — libRoadRunner scaled flux-control coefficients
  at the steady state, with the MCA summation theorem residual |sum_j C^J_j - 1|
  per carried flux (Kacser & Burns 1973) as the check;
* **element + free-energy ledger** — exact stoichiometric element residual
  max|E S|, the integrated carbon-balance residual and the minimum dissipation
  over the run (second law);
* **stiffness check** — Jacobian stiffness ratio at the end state and the
  worst relative deviation of every species when the CVODE tolerances are
  loosened / tightened around libRoadRunner's defaults (rtol 1e-6, atol 1e-12).

Writes artifacts/reaction_universe_verification.json.

    PYTHONPATH=<worktree> python workspace/studies/og-02-alt-reaction-universe/sims/verify_reaction_universe.py [--steps 200]
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"
FEED = {"feed_CO2": 1.4e-3, "feed_H2": 1.08e-2, "feed_pyruvate": 1.0e-4,
        "feed_formaldehyde": 0.0, "feed_formate": 0.0, "feed_acetate": 0.0}
FORMOSE_FEED = {**FEED, "feed_formaldehyde": 1.0e-2}
CURATED_FORMULAS = {"CO2": {"C": 1, "O": 2}, "pyruvate": {"C": 3, "H": 4, "O": 3},
                    "OAA": {"C": 4, "H": 4, "O": 5}, "malate": {"C": 4, "H": 6, "O": 5},
                    "succinate": {"C": 4, "H": 6, "O": 4}, "acetate": {"C": 2, "H": 4, "O": 2}}


def _arg(flag, default):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return type(default)(sys.argv[i + 1])
    return default


def _default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return str(o)


def verify_generated(cls, feed, n_steps, config=None):
    from process_bigraph import allocate_core
    from viva_genesis.protometabolism import motifs as M
    from viva_genesis.protometabolism import universe as U
    core = allocate_core()
    p = cls(config={"motif_every": 50, **(config or {})}, core=core)
    diss_min, carbon_max = math.inf, 0.0
    out = None
    for _ in range(n_steps):
        out = p.update(feed, 1.0)
        diss_min = min(diss_min, out["dissipation"]); carbon_max = max(carbon_max, out["carbon_residual"])
    u = p.universe()
    kin = p._kin

    def factory():
        import tellurium as te
        rr = te.loada(U.to_antimony(u, kin, feed, initial={U.CO2: feed["feed_CO2"], U.H2: feed["feed_H2"]}))
        rr.f_mineral = p._f["mineral"]; rr.f_base = p._f["base"]
        return rr

    fca = M.flux_control_analysis(p._rr)
    stiff = M.stiffness_check(factory, t_end=float(n_steps))
    return {
        "ledger": {"element_residual": float(out["element_residual"]), "carbon_residual_max": float(carbon_max),
                   "dissipation_min_W": float(diss_min), "dissipation_final_W": float(out["dissipation"]),
                   "element_detail": u.element_residual()},
        "flux_control": fca, "stiffness": stiff,
        "n_species": len(u.organics()), "n_reactions": len(u.reactions),
        "final": {k: float(v) for k, v in out.items()},
    }


def verify_curated(feed, n_steps):
    from process_bigraph import allocate_core
    from viva_genesis.protometabolism.network import RoadRunnerNetworkProcess, _MODEL
    from viva_genesis.protometabolism import motifs as M
    p = RoadRunnerNetworkProcess(config={}, core=allocate_core())
    st = {"feed_pyruvate": feed["feed_pyruvate"], "feed_CO2": feed["feed_CO2"]}
    out = None
    for _ in range(n_steps):
        out = p.update(st, 1.0)
    net = M.network_from_roadrunner(p._rr)
    el = M.element_residual(net, CURATED_FORMULAS)

    def factory():
        import tellurium as te
        rr = te.loada(_MODEL)
        rr.co2_in = feed["feed_CO2"]; rr.pyr_in = feed["feed_pyruvate"]
        return rr

    return {"ledger": {"element_residual": float(el["max_abs"]), "element_detail": el,
                       "note": "no dissipation witness: the curated kinetics are irreversible and carry no dG'"},
            "flux_control": M.flux_control_analysis(p._rr), "stiffness": M.stiffness_check(factory, t_end=float(n_steps)),
            "n_species": 6, "n_reactions": 4, "final": {k: float(v) for k, v in out.items()}}


def main() -> int:
    from viva_genesis.protometabolism.universe_process import ReactionUniverseProcess, NullNetworkProcess
    n_steps = _arg("--steps", 200)
    t0 = time.time()
    res = {"meta": {"n_steps": n_steps, "feed": FEED, "formose_feed": FORMOSE_FEED,
                    "default_tolerances": {"rtol": 1e-6, "atol": 1e-12}}}
    res["reaction_universe"] = verify_generated(ReactionUniverseProcess, FEED, n_steps)
    print("universe:", json.dumps({k: res["reaction_universe"][k] for k in ("ledger",)}, default=_default)[:400], flush=True)
    res["reaction_universe_formose"] = verify_generated(ReactionUniverseProcess, FORMOSE_FEED, n_steps)
    res["null_network_seed0"] = verify_generated(NullNetworkProcess, FEED, n_steps, {"null_seed": 0})
    res["curated_rtca"] = verify_curated(FEED, n_steps)
    for k in ("reaction_universe", "reaction_universe_formose", "null_network_seed0", "curated_rtca"):
        r = res[k]
        fc = r["flux_control"]; st = r["stiffness"]
        print(f"{k:28s} element {r['ledger']['element_residual']:.3g} | FCC summation max resid "
              f"{fc.get('max_summation_residual', float('nan')):.2e} ({'ok' if fc.get('ok') else fc.get('error')}) | "
              f"stiffness ratio {st['jacobian'].get('stiffness_ratio', float('nan')):.2e} | tol deviations "
              f"{ {kk: f'{v['max_rel_dev']:.1e}' for kk, v in st['deviations'].items()} }", flush=True)
    res["meta"]["wall_time_s"] = time.time() - t0
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "reaction_universe_verification.json").write_text(json.dumps(res, indent=1, default=_default))
    print(f"wrote {ARTIFACTS / 'reaction_universe_verification.json'} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
