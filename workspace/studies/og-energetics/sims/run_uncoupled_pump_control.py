"""Uncoupled-pump matched null for og-energetics (Gate E energy / og-05 internalization).

New-simulation control (figure-review Priority 2) on the real bioenergetic-internalization
selection loop: the favourable efficient pump (catalyst_efficiency=1.0) vs an UNCOUPLED
pump that does essentially no coupling work (catalyst_efficiency≈0). If the carrier's
benefit requires coupling, the uncoupled arm cannot internalize gradient generation and
the lineage collapses as the external gradient declines (the Sojo constraint).

NOTE (pbg is_empty gotcha): catalyst_efficiency=0.0 is backfilled to the DEFAULT (1.0)
because 0.0 reads as empty/unset — so the honest uncoupled control uses a near-zero
epsilon (1e-6), not 0.0. (Verified: eff=0.0 returns the eff=1.0 result; eff=1e-6 collapses.)
"""
from __future__ import annotations

import json
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
OUT = STUDY_DIR / "artifacts" / "og-05-environmental-to-internal-bioenergetics" / "uncoupled_pump_control.json"
EPS = 1.0e-6  # near-zero (0.0 would backfill to the default — pbg is_empty trap)


def main() -> int:
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.bioenergetic_internalization import bioenergetic_internalization

    def run(eff: float) -> dict:
        core = build_core()  # fresh core per arm
        sim = Composite({"state": bioenergetic_internalization(core, catalyst_efficiency=eff)}, core=core)
        sim.run(60.0)
        res = gather_emitter_results(sim)
        last = (res.get(("emitter",)) or next(iter(res.values())))[-1]
        return {
            "catalyst_efficiency": eff,
            "survivors": last.get("survivors"),
            "autonomy": last.get("autonomy"),
            "internalization": last.get("internalization"),
            "free_energy_flux": last.get("free_energy_flux"),
            "lineage_fitness": last.get("lineage_fitness"),
        }

    favorable = run(1.0)
    uncoupled = run(EPS)

    s_fav = favorable["survivors"] or 0.0
    s_unc = uncoupled["survivors"] or 0.0
    artifact = {
        "study": "og-energetics",
        "control": "uncoupled-pump matched null (catalyst_efficiency≈0 vs 1.0)",
        "description": (
            "Favourable efficient pump vs an uncoupled pump (near-zero coupling efficiency), every other "
            "parameter held equal, over a declining external gradient. Isolates that the internalization / "
            "autonomy benefit requires COUPLING, not the carrier's mere presence."
        ),
        "arms": {"favorable": favorable, "uncoupled": uncoupled},
        "collapses": (s_unc < 0.1 * s_fav) if s_fav else None,
        "verdict": (
            "uncoupled pump collapses (cannot internalize) → the benefit requires coupling"
            if s_fav and s_unc < 0.1 * s_fav else
            "uncoupled pump does NOT collapse — benefit not coupling-dependent (HONEST NEGATIVE — flag)"
        ),
        "note_is_empty": (
            "catalyst_efficiency=0.0 is backfilled to the default (1.0) by the pbg is_empty(0.0) rule, so the "
            "uncoupled control uses eff=1e-6; a bare 0.0 would silently reproduce the favourable arm."
        ),
        "note_first_law": (
            "The formal first-law / free-energy ledger closure (in + E0 - work - dissipated = E(t), residual "
            "~1e-16) is demonstrated by the proto-energetics arm's FreeEnergyLedgerProcess; here free_energy_flux "
            "is the internalized-power readout that collapses with the pump uncoupled."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2))
    print(f"favorable: survivors={s_fav:.4g} autonomy={favorable['autonomy']:.4g} fe_flux={favorable['free_energy_flux']:.3g}")
    print(f"uncoupled: survivors={s_unc:.4g} autonomy={uncoupled['autonomy']:.4g} fe_flux={uncoupled['free_energy_flux']:.3g}")
    print(f"verdict: {artifact['verdict']}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
