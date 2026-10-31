"""S2 calibration guard: pore exchange registers as cross-lineage flux, and proximity matters."""
from __future__ import annotations

from process_bigraph import Composite
from viva_genesis.core import build_core


def _flux(placement, n=250):
    from viva_genesis.composites.metabolite_exchange_community import metabolite_exchange_community
    core = build_core()
    sim = Composite({"state": metabolite_exchange_community(
        core=core, lineages="fixer:4,reducer:4", coupling="shared", model_proto_ecology="reaction_universe",
        p_diacid=1e-8, p_monoacid=1e-7, k_wash=0.01, placement=placement, k_diffusion=0.001)}, core=core)
    sim.run(float(n))
    return float(sim.state["exchange"]["cross_lineage_flux_total"])


def test_mixed_flux_nonzero_and_22x_over_segregated():
    mixed, seg = _flux("mixed"), _flux("segregated")
    assert mixed > 1e-22, mixed  # S2 pass threshold
    assert 3e-22 < mixed < 5e-22, mixed  # calibration 4.005e-22
    assert 15 < mixed / seg < 30, (mixed, seg)  # calibration ratio ~22x


def _sqlite_run(tmp_path, per_step_states):
    """Build a runs.db shaped like the workbench's tracked-run store (state = nested tree)."""
    import json
    import sqlite3
    db = tmp_path / "runs.db"
    c = sqlite3.connect(db)
    c.execute("create table history (simulation_id TEXT, step INTEGER, global_time REAL, state TEXT,"
              " primary key (simulation_id, step))")
    for i, st in enumerate(per_step_states):
        c.execute("insert into history values (?,?,?,?)", ("sim__1", i, float(i), json.dumps(st)))
    c.commit()
    c.close()
    return db


def test_derived_scalars_grade_from_recorded_sqlite_store(tmp_path):
    """Regression: the tracked-run store exposes nested state as dotted ids ('exchange.x'), while
    studies declare 'exchange/x'. Grading a recorded run must resolve both (was KeyError -> SKIP)."""
    from pathlib import Path

    from viva_emitters import RunReader, RunRef
    from viva_genesis import evaluators as E

    db = _sqlite_run(tmp_path, [
        {"exchange": {"cross_lineage_flux_total": 4.0e-22}, "enc": {"enclosure_probability": 0.6}}
        for _ in range(8)])
    reader = RunReader(RunRef(str(db), kind="sqlite", simulation_id="sim__1"))
    assert abs(E._settled_cross_lineage_flux(reader, {}, Path(".")) - 4.0e-22) < 1e-30
    assert abs(E._settled_enclosure_probability(reader, {}, Path(".")) - 0.6) < 1e-12
