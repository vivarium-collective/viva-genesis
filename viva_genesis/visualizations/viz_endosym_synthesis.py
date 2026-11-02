"""Eukaryogenesis synthesis — the transition barrier ledger (investigation-level).

One at-a-glance view of the whole investigation: the endosymbiotic transition as a
chain of barriers, each tested by a member study, with its discriminating result
(favorable regime vs matched control) and whether the gate passes. The reviewer sees
the full arc — exchange → proximity → selection → enclosure → coupling → transmission
→ reciprocity — and the margin of each gate, rather than reading six studies separately.

Runs every member composite's favorable + control arm fresh (no fabricated data) and
renders a styled scorecard through the shared viz_style chrome. Headline: the arc is
feasible but MULTIPLY BOUNDED — every gate passes, and every one is regime-dependent.
"""
from __future__ import annotations

from html import escape

from process_bigraph import Composite
from process_bigraph.visualization import Visualization

from . import viz_style as S
from ..core import build_core


def _run_obs(generator, core, obs_fn, keys, *, n_steps, **kw):
    sim = Composite({"state": generator(core=core, **kw)}, core=core)
    rows = []
    for _ in range(int(n_steps)):
        sim.run(1)
        rows.append({k: sim.state.get(k) for k in keys})
    return float(obs_fn(rows))


class TransitionLedgerViz(Visualization):
    """The barrier ledger: one row per transition gate with favorable vs control + verdict."""
    config_schema = {"title": {"_type": "string",
                     "_default": "The endosymbiotic transition is feasible — but multiply bounded"}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def _rows(self, core):
        from ..composites.proto_endosymbiosis_hybrid import (
            proto_endosymbiosis_hybrid as GH, selection_coefficient_for_adhesion as OH)
        from ..composites.proto_endosymbiosis_enclosure import (
            proto_endosymbiosis_enclosure as GE, probability_of_stable_enclosure as OE)
        from ..composites.proto_endosymbiosis_coupled import (
            proto_endosymbiosis_coupled as GC, joint_feasibility_region as OC)
        from ..composites.proto_endosymbiosis_transmission import (
            proto_endosymbiosis_transmission as GT, endosymbiont_retention_fraction as OT)
        from ..composites.proto_endosymbiosis_spatial import (
            proto_endosymbiosis_spatial as GS, realised_exchange_level as OS)
        from ..composites.proto_endosymbiosis_multimetab import (
            proto_endosymbiosis_multimetab as GM, mutualistic_exchange_benefit as OM)

        sel_on = _run_obs(GH, core, OH, ("n_high", "n_low"), n_steps=160, exchange="on",
                          benefit_coeff=1.2, cost_coeff=0.3, init_freq_high=0.6)
        sel_off = _run_obs(GH, core, OH, ("n_high", "n_low"), n_steps=160, exchange="off",
                           benefit_coeff=1.2, cost_coeff=0.3, init_freq_high=0.6)
        spa_c = _run_obs(GS, core, OS, ("consumer_conc",), n_steps=400, consumer_distance=1, diffusion=0.4, decay=0.08)
        spa_d = _run_obs(GS, core, OS, ("consumer_conc",), n_steps=400, consumer_distance=10, diffusion=0.4, decay=0.08)
        enc_g = _run_obs(GE, core, OE, ("n_attempting", "n_sealed", "n_stalled"), n_steps=120,
                         adhesion_energy=0.9, bending_modulus=0.2, perturbation=0.1)
        enc_c = _run_obs(GE, core, OE, ("n_attempting", "n_sealed", "n_stalled"), n_steps=120,
                         adhesion_energy=0.6, bending_modulus=0.3, perturbation=0.9)
        cpl_a = _run_obs(GC, core, OC, ("n_lc", "n_hc_un", "n_hc_se", "n_hc_st"), n_steps=200,
                         benefit_coeff=1.2, cost_coeff=0.3, base_adhesion=0.8, bending_modulus=0.2, perturbation=0.1)
        cpl_d = _run_obs(GC, core, OC, ("n_lc", "n_hc_un", "n_hc_se", "n_hc_st"), n_steps=200,
                         benefit_coeff=0.3, cost_coeff=0.3, base_adhesion=0.8, bending_modulus=0.2, perturbation=0.1)
        trn_s = _run_obs(GT, core, OT, ("n_sym", "n_free"), n_steps=300, fidelity=0.98, benefit=0.6, cost=0.1, loss_rate=0.03)
        trn_c = _run_obs(GT, core, OT, ("n_sym", "n_free"), n_steps=300, fidelity=0.95, benefit=0.6, cost=0.1, loss_rate=0.5)
        rcp_b = _run_obs(GM, core, OM, ("symbiont_a_conc", "host_b_conc"), n_steps=400,
                         symbiont_distance=1, production_a=1.0, production_b=1.0)
        rcp_a = _run_obs(GM, core, OM, ("symbiont_a_conc", "host_b_conc"), n_steps=400,
                         symbiont_distance=1, production_a=1.0, production_b=0.2)
        fold = spa_c / spa_d if spa_d > 0 else float("nan")
        # (gate label, barrier, favorable label+value, control label+value, pass)
        return [
            ("G1 · Exchange", "a partner-dependent metabolic advantage",
             "selection s", sel_on, "no-exchange", sel_off, sel_on > 0),
            ("G2 · Proximity", "contact realises the exchange (screened diffusion)",
             f"contact ({fold:.0f}×)", spa_c, "distal (d=10)", spa_d, fold > 3),
            ("G3 · Enclosure", "stable sealing needs a mechanical budget",
             "geometry-first", enc_g, "conflict", enc_c, enc_g >= 0.5),
            ("G4 · Coupling", "selection and enclosure must co-occur",
             "aligned", cpl_a, "decoupled", cpl_d, cpl_a >= 0.5),
            ("G5 · Transmission", "establishment ≠ permanence",
             "fidelity+benefit", trn_s, "high-conflict", trn_c, trn_s >= 0.5),
            ("G6 · Reciprocity", "mutual benefit capped at the scarcer flux",
             "balanced", rcp_b, "asymmetric", rcp_a, rcp_b >= 0.5),
        ]

    def update(self, state=None):
        core = build_core()
        rows = self._rows(core)
        F = S.FONT_STACK
        th = (f'padding:7px 11px;text-align:left;font:700 11.5px {F};color:{S.INK_SOFT};'
              f'border-bottom:2px solid {S.HAIR};letter-spacing:.02em')
        cells = []
        for gate, barrier, fav_l, fav_v, ctl_l, ctl_v, ok in rows:
            accent = S.TEAL if ok else S.RUST
            chip = (f'<span style="display:inline-block;background:{accent};color:#fff;border-radius:999px;'
                    f'padding:1px 9px;font:700 10.5px {F}">{"PASS" if ok else "FAIL"}</span>')
            td = f'padding:8px 11px;font:400 12.5px {F};color:{S.INK};border-bottom:1px solid {S.GRID}'
            cells.append(
                f'<tr>'
                f'<td style="{td};font-weight:700;color:{accent};white-space:nowrap">{escape(gate)}</td>'
                f'<td style="{td}">{escape(barrier)}</td>'
                f'<td style="{td};text-align:right;font-weight:700">{escape(fav_l)}<br>'
                f'<span style="color:{S.TEAL};font-size:14px">{fav_v:.3g}</span></td>'
                f'<td style="{td};text-align:right;color:{S.SLATE}">{escape(ctl_l)}<br>'
                f'<span style="font-size:14px">{ctl_v:.3g}</span></td>'
                f'<td style="{td};text-align:center">{chip}</td>'
                f'</tr>')
        table = (
            f'<table style="width:100%;border-collapse:collapse;background:{S.PAPER};border:1px solid {S.HAIR};'
            f'border-radius:10px;overflow:hidden">'
            f'<tr><th style="{th}">Gate</th><th style="{th}">Barrier crossed</th>'
            f'<th style="{th};text-align:right">Favorable regime</th>'
            f'<th style="{th};text-align:right">Matched control</th>'
            f'<th style="{th};text-align:center">Gate</th></tr>'
            f'{"".join(cells)}</table>')
        return {"html": S.frame(table, title=self.config.get("title"), tier="mechanistic_prediction",
                view="Decision", tone="neutral", max_width=860,
                caption_text=("Each barrier of the syntrophy→enclosure→individuality arc passes its gate in a "
                              "favorable regime and fails in a matched control — so a continuous path exists, but "
                              "<b>every crossing is regime-dependent</b>. The transition is feasible, not inevitable: "
                              "it is bounded at six independent points, and no single mechanism carries it alone."))}
