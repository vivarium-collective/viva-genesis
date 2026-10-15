#!/usr/bin/env python
"""Compute + persist the Phase-3 motif-enrichment artifact (og-02-alt-reaction-universe).

Runs the three ``proto_metabolism`` classes on the real libRoadRunner engine
under two feeds and grades every one of them with the same post-hoc detector:

* **phase1_feed** — the og-cal-vent-environment posterior example point
  (CO2 1.4 mM, H2 10.8 mM, pyruvate 0.1 mM, no formaldehyde): the flagship
  chain "Phase-1 posterior -> Phase-3 universe".
* **formose_feed** — the same feed plus 10 mM formaldehyde (the classic
  formose feedstock), which bypasses the thermodynamic C1 bottleneck.

Per arm: the generated universe, ``--nulls`` matched null networks (seeds
0..n-1) and the curated rTCA class, each for ``--steps`` ticks; the universe's
persistent autocatalytic-motif count / core size / persistent-species count are
then compared with the null distribution (empirical p, z). A small
(formaldehyde x washout) ignition map of motif counts is computed for the
universe and a few nulls. Writes

    artifacts/motif_enrichment.json

    PYTHONPATH=<worktree> python workspace/studies/og-02-alt-reaction-universe/sims/compute_motif_enrichment.py [--nulls 24] [--steps 200] [--map 6] [--map-nulls 3]
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

PHASE1_FEED = {"feed_CO2": 1.4e-3, "feed_H2": 1.08e-2, "feed_pyruvate": 1.0e-4,
               "feed_formaldehyde": 0.0, "feed_formate": 0.0, "feed_acetate": 0.0}
FORMOSE_FEED = {**PHASE1_FEED, "feed_formaldehyde": 1.0e-2}
ARMS = {"phase1_feed": PHASE1_FEED, "formose_feed": FORMOSE_FEED}
CURATED_FORMULAS = {"CO2": {"C": 1, "O": 2}, "pyruvate": {"C": 3, "H": 4, "O": 3},
                    "OAA": {"C": 4, "H": 4, "O": 5}, "malate": {"C": 4, "H": 6, "O": 5},
                    "succinate": {"C": 4, "H": 6, "O": 4}, "acetate": {"C": 2, "H": 4, "O": 2}}


def _arg(flag: str, default):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return type(default)(sys.argv[i + 1])
    return default


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return str(o)


def _snapshot(p, conc_floor=1e-12, flux_floor=1e-12) -> dict:
    """Alive species + flux-carrying internal reactions (for the subnetwork figure)."""
    from viva_genesis.protometabolism import universe as U
    u = p.universe()
    conc = {s: c for s, c in p._conc.items() if c > conc_floor and (s.startswith("X_") or s in ("CO2", "H2"))}
    rid = {r.id: r for r in u.reactions}
    rxns = []
    for r_id, v in p._fluxes.items():
        r = rid.get(r_id)
        if r is None or abs(v) < flux_floor:
            continue
        rxns.append({"id": r_id, "rule": r.rule, "rate": float(v), "dg0": float(r.dg0),
                     "reactants": dict(r.reactants), "products": dict(r.products)})
    names = {s: (U.common_name(U.skeleton_of(s)) if U.skeleton_of(s) else s) for s in conc}
    return {"conc": conc, "reactions": rxns, "names": names}


def run_generated(cls, feed: dict, n_steps: int, config: dict | None = None, *, snapshot: bool = False) -> dict:
    """Run ReactionUniverseProcess / NullNetworkProcess for n_steps; return the
    final outputs + motif summary + universe summary."""
    from process_bigraph import allocate_core
    core = allocate_core()
    cfg = {"motif_every": 20, **(config or {})}
    p = cls(config=cfg, core=core)
    out = None
    for _ in range(n_steps):
        out = p.update(feed, 1.0)
    u = p.universe()
    return {"final": out, "motifs": p._motif_summary, "universe": u.summary(),
            **({"snapshot": _snapshot(p)} if snapshot else {}),
            "n_motifs": int(p._motif_summary["n_motifs"]), "core_size": int(p._motif_summary["core_size"]),
            "max_dynamic_gain": float(p._motif_summary["max_dynamic_gain"]),
            "n_persistent_species": float(out["n_persistent_species"]),
            "element_residual": float(out["element_residual"]), "carbon_residual": float(out["carbon_residual"]),
            "dissipation": float(out["dissipation"])}


def run_curated(feed: dict, n_steps: int, k_wash: float = 0.05) -> dict:
    """og-02's curated rTCA class graded by the SAME post-hoc detector and the
    element ledger computed from its SBML."""
    from process_bigraph import allocate_core
    from viva_genesis.protometabolism.network import RoadRunnerNetworkProcess
    from viva_genesis.protometabolism import motifs as M
    p = RoadRunnerNetworkProcess(config={"k_wash": k_wash}, core=allocate_core())
    st = {"feed_pyruvate": feed["feed_pyruvate"], "feed_CO2": feed["feed_CO2"]}
    out = None
    for _ in range(n_steps):
        out = p.update(st, 1.0)
    rr = p._rr
    net = M.network_from_roadrunner(rr)
    conc = {s: float(rr[s]) for s in rr.getFloatingSpeciesIds()}
    rates = dict(zip(rr.getReactionIds(), (float(x) for x in rr.getReactionRates())))
    cycles = M.autocatalytic_cycles(net, rates, conc, exclude={"CO2"})
    summary = M.summarize_motifs(cycles, conc, k_wash)
    el = M.element_residual(net, CURATED_FORMULAS)
    n_pers = sum(1 for s, c in conc.items() if s != "CO2" and c > 1e-9)
    return {"final": out, "motifs": summary, "n_motifs": int(summary["n_motifs"]),
            "core_size": int(summary["core_size"]), "max_dynamic_gain": float(summary["max_dynamic_gain"]),
            "declared_autocatalytic_gain": float(out["autocatalytic_gain"]),
            "n_persistent_species": float(n_pers), "element_residual": float(el["max_abs"]),
            "element_residual_detail": el, "conc": conc}


def main() -> int:
    from viva_genesis.protometabolism.universe_process import ReactionUniverseProcess, NullNetworkProcess
    from viva_genesis.protometabolism import motifs as M
    from viva_genesis.protometabolism import universe as U

    n_null = _arg("--nulls", 24)
    n_steps = _arg("--steps", 200)
    n_map = _arg("--map", 6)
    map_nulls = _arg("--map-nulls", 3)
    t0 = time.time()

    def log(msg):
        print(msg, flush=True)

    pkg = U.load_package_dict()
    arms_out = {}
    for arm, feed in ARMS.items():
        log(f"== arm {arm}: feed {feed}")
        uni = run_generated(ReactionUniverseProcess, feed, n_steps, snapshot=True)
        log(f"   universe: motifs {uni['n_motifs']} core {uni['core_size']} gain {uni['max_dynamic_gain']:.2e} "
            f"persistent {uni['n_persistent_species']:.0f} element {uni['element_residual']}")
        for m in uni["motifs"]["motifs"][:3]:
            log(f"     motif {m['species']} gain {m['gain']} dynamic {m['dynamic_gain']:.2e}")
        nulls = []
        for seed in range(n_null):
            r = run_generated(NullNetworkProcess, feed, n_steps, {"null_seed": seed})
            r["energetic_span_kj_mol"] = r["universe"]["energetic_span_kj_mol"]
            r["catalyst_density"] = r["universe"]["catalyst_density"]
            r["n_reactions"] = r["universe"]["n_reactions"]
            r.pop("universe", None); r.pop("final", None)
            r["seed"] = seed
            nulls.append(r)
            log(f"   null {seed:2d}: motifs {r['n_motifs']} core {r['core_size']} persistent {r['n_persistent_species']:.0f} "
                f"element {r['element_residual']}")
        cur = run_curated(feed, n_steps)
        log(f"   curated_rtca: motifs {cur['n_motifs']} core {cur['core_size']} detector gain {cur['max_dynamic_gain']:.2e} "
            f"declared gain {cur['declared_autocatalytic_gain']:.2f} element residual {cur['element_residual']}")
        enr = {k: M.enrichment(uni[k], [n[k] for n in nulls])
               for k in ("n_motifs", "core_size", "n_persistent_species")}
        arms_out[arm] = {"feed": feed, "universe": uni, "nulls": nulls, "curated_rtca": cur, "enrichment": enr,
                         "matching": {"universe_energetic_span": uni["universe"]["energetic_span_kj_mol"],
                                      "null_energetic_span_mean": float(np.mean([n["energetic_span_kj_mol"]["span"] for n in nulls])),
                                      "null_n_reactions_mean": float(np.mean([n["n_reactions"] for n in nulls])),
                                      "universe_n_reactions": uni["universe"]["n_reactions"],
                                      "null_element_residual_mean": float(np.mean([n["element_residual"] for n in nulls]))}}
        log(f"   enrichment n_motifs: p = {enr['n_motifs']['p_empirical']:.3f}, z = {enr['n_motifs']['z']:.2f}, "
            f"null max {enr['n_motifs']['null_max']}")

    # ignition map: (feed_formaldehyde x k_wash), universe + a few nulls
    ch2o = np.logspace(-4, math.log10(3.0e-2), n_map)
    kwash = np.logspace(-3, math.log10(0.2), n_map)
    uni_n = np.zeros((n_map, n_map)); uni_g = np.zeros((n_map, n_map)); uni_sp = np.zeros((n_map, n_map))
    null_n = np.zeros((n_map, n_map))
    for i, c in enumerate(ch2o):
        for j, kw in enumerate(kwash):
            feed = {**PHASE1_FEED, "feed_formaldehyde": float(c)}
            r = run_generated(ReactionUniverseProcess, feed, n_steps, {"k_wash": float(kw)})
            uni_n[i, j] = r["n_motifs"]; uni_g[i, j] = r["max_dynamic_gain"]; uni_sp[i, j] = r["n_persistent_species"]
            nn = [run_generated(NullNetworkProcess, feed, n_steps, {"k_wash": float(kw), "null_seed": s})["n_motifs"]
                  for s in range(map_nulls)]
            null_n[i, j] = float(np.mean(nn))
            log(f"   map CH2O {c:.1e} k_wash {kw:.3f}: universe motifs {uni_n[i, j]:.0f} gain {uni_g[i, j]:.2e} | null mean {null_n[i, j]:.2f}")

    # null matching report (one draw)
    base = U.build_universe(int(pkg["parameters"][0]["value"]) if pkg["parameters"][0]["id"] == "max_carbons" else 4)
    null0 = U.null_network(base, 0)
    matching = {"universe": base.summary(), "null_seed0": null0.summary()}

    f_arm = arms_out["formose_feed"]; p_arm = arms_out["phase1_feed"]
    headline = (
        f"Phase-1 feed: universe {p_arm['universe']['n_motifs']} persistent autocatalytic motifs "
        f"({p_arm['universe']['n_persistent_species']:.0f} persistent species, malate "
        f"{p_arm['universe']['final']['malate']:.1e} M); nulls max {p_arm['enrichment']['n_motifs']['null_max']:.0f}. "
        f"Formose feed (10 mM CH2O): universe {f_arm['universe']['n_motifs']} motif(s), core "
        f"{f_arm['universe']['core_size']} species, dynamic gain {f_arm['universe']['max_dynamic_gain']:.2g}; "
        f"nulls mean {f_arm['enrichment']['n_motifs']['null_mean']:.2f}, max {f_arm['enrichment']['n_motifs']['null_max']:.0f}; "
        f"empirical p = {f_arm['enrichment']['n_motifs']['p_empirical']:.3f}. "
        f"Curated rTCA: detector finds {f_arm['curated_rtca']['n_motifs']} motif (the declared turn), "
        f"element residual {f_arm['curated_rtca']['element_residual']:.0f} atoms (not balanced)."
    )
    out = {
        "meta": {"n_null": n_null, "n_steps": n_steps, "map_n": n_map, "map_nulls": map_nulls,
                 "package_version": pkg.get("version"), "kinetics": U.kinetics_from_package(pkg),
                 "thermo_conditions": pkg["thermo"]["conditions"], "wall_time_s": time.time() - t0,
                 "detector": "flux-carrying simple cycles with stoichiometric gain > 1 (max length 6), "
                             "species > 1e-9 M, |flux| > 1e-12 M/s; currency species CO2/H2/H2O excluded"},
        "arms": arms_out,
        "ignition_map": {"feed_formaldehyde": ch2o.tolist(), "k_wash": kwash.tolist(),
                         "universe_n_motifs": uni_n.tolist(), "universe_max_gain": uni_g.tolist(),
                         "universe_n_persistent_species": uni_sp.tolist(), "null_n_motifs_mean": null_n.tolist()},
        "matching": matching,
        "headline": headline,
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "motif_enrichment.json").write_text(json.dumps(out, indent=1, default=_json_default))
    log(f"wrote {ARTIFACTS / 'motif_enrichment.json'} ({time.time() - t0:.0f}s)")
    log(headline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
