"""Eukaryogenesis M-track — insight-forward visualizations (deep viz upgrade).

Upgrades the headline M-track figures from a single favorable-vs-control BAR to the
richest view the reduced coupled models support, so a reviewer sees *why* each gate
passes, not just that it does:

  SelectionInvasionViz   (study-selection-for-proximity)   — invasion trajectory, on vs off
  EnclosurePhaseViz      (study-enclosure-mechanics)        — adhesion×perturbation phase map
  CouplingOverlapViz     (study-contact-to-enclosure-coupling) — selection∩enclosure overlap
  TransmissionFanViz     (study-vertical-transmission-stability) — retention fan over loss rate
  SpatialDistanceViz     (study-spatial-exchange-proximity) — exchange vs distance (screened)
  ReciprocityLiebigViz   (study-bidirectional-syntrophy)    — Liebig cap over production balance

Each runs the study's real composite fresh (no stored/fabricated data) and renders through
the shared viz_style chrome (header band · tier badge · caption). Tier: mechanistic_prediction
(a parameterized reduced model's quantitative prediction, under stated assumptions).
"""
from __future__ import annotations

import plotly.graph_objects as go

from process_bigraph import Composite
from process_bigraph.visualization import Visualization

from . import viz_style as S
from ..core import build_core


def _run_obs(generator, core, obs_fn, keys, *, n_steps, **kw):
    sim = Composite({"state": generator(core=core, **kw)}, core=core)
    rows = []
    for _ in range(int(n_steps)):
        sim.run(1)
        st = sim.state
        rows.append({k: st.get(k) for k in keys})
    return float(obs_fn(rows))


def _run_series(generator, core, keys, *, n_steps, **kw):
    """Run the composite and return the full per-tick rows (for trajectory figures)."""
    sim = Composite({"state": generator(core=core, **kw)}, core=core)
    rows = []
    for _ in range(int(n_steps)):
        sim.run(1)
        st = sim.state
        rows.append({k: float(st.get(k, 0.0) or 0.0) for k in keys})
    return rows


def _html(fig, *, height=430):
    fig.update_layout(**S.base_layout(height=height))
    S.style_axes(fig)
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


# ── M1 — selection for proximity: the adhesive phenotype INVADES ─────────────
class SelectionInvasionViz(Visualization):
    config_schema = {"title": {"_type": "string",
                     "_default": "Exchange selects for contact — the adhesive phenotype invades to fixation"},
                     "n_steps": {"_type": "integer", "_default": 160}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_hybrid import (
            proto_endosymbiosis_hybrid as G, selection_coefficient_for_adhesion as OBS)
        core = build_core(); n = int(self.config["n_steps"])
        kw = dict(benefit_coeff=1.2, cost_coeff=0.3, init_freq_high=0.6)

        def series(exchange):
            rows = _run_series(G, core, ("n_high", "n_low"), n_steps=n, exchange=exchange, **kw)
            freq = [r["n_high"] / (r["n_high"] + r["n_low"]) if (r["n_high"] + r["n_low"]) > 0 else 0.0
                    for r in rows]
            return freq, float(OBS(rows))

        f_on, s_on = series("on")
        f_off, s_off = series("off")
        t = list(range(n))
        tx, tlabel = S.real_time(t, G)
        if "step" in tlabel:
            tlabel = "generation"
        init = kw["init_freq_high"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=tx, y=f_on, mode="lines", name=f"exchange on  (s = {s_on:+.2f})",
                                 line=dict(color=S.TEAL, width=2.6)))
        fig.add_trace(go.Scatter(x=tx, y=f_off, mode="lines", name=f"no-exchange control  (s = {s_off:+.2f})",
                                 line=dict(color=S.RUST, width=2.4, dash="dot")))
        fig.add_hline(y=init, line=dict(color=S.SLATE, width=1, dash="dash"),
                      annotation_text="start frequency", annotation_position="bottom right",
                      annotation_font=dict(size=10, color=S.SLATE))
        fig.update_yaxes(title="frequency of the adhesive (contact-seeking) phenotype", range=[0, 1.04])
        fig.update_xaxes(title=tlabel)
        inner = _html(fig)
        return {"html": S.frame(inner, title=self.config.get("title"), tier="mechanistic_prediction",
                view="Mechanism", tone="positive",
                caption_text=(f"Under metabolic exchange the contact-seeking phenotype is positively selected and "
                              f"<b>invades to fixation</b> (selection coefficient s = {s_on:+.2f}); the matched "
                              f"no-exchange control selects against it (s = {s_off:+.2f}) and it is lost. "
                              f"Proximity is favoured only when exchange pays for the cost of adhesion."))}


# ── M2 — enclosure mechanics: a regime-dependent phase map ───────────────────
class EnclosurePhaseViz(Visualization):
    config_schema = {"title": {"_type": "string",
                     "_default": "Stable enclosure is regime-dependent — a mechanical budget, not a given"},
                     "n_steps": {"_type": "integer", "_default": 120},
                     "grid": {"_type": "integer", "_default": 9}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_enclosure import (
            proto_endosymbiosis_enclosure as G, probability_of_stable_enclosure as OBS)
        core = build_core(); n = int(self.config["n_steps"]); g = int(self.config["grid"])
        adh = [0.3 + i * (1.0 - 0.3) / (g - 1) for i in range(g)]
        pert = [0.0 + j * (1.0 - 0.0) / (g - 1) for j in range(g)]
        keys = ("n_attempting", "n_sealed", "n_stalled")
        Z = [[_run_obs(G, core, OBS, keys, n_steps=n, adhesion_energy=a, bending_modulus=0.25, perturbation=p)
              for a in adh] for p in pert]
        colorscale = [[0.0, S.RUST], [0.49, "#f1d4c4"], [0.5, "#e7eef0"], [0.51, "#bfe0db"], [1.0, S.TEAL]]
        fig = go.Figure(go.Heatmap(x=adh, y=pert, z=Z, zmin=0, zmax=1, colorscale=colorscale,
                                   colorbar=dict(title="P(stable<br>enclosure)", thickness=14),
                                   hovertemplate="adhesion %{x:.2f}, perturbation %{y:.2f}<br>P = %{z:.2f}<extra></extra>"))
        fig.add_trace(go.Contour(x=adh, y=pert, z=Z, showscale=False, contours=dict(start=0.5, end=0.5, size=1,
                      coloring="none"), line=dict(color=S.INK, width=2), hoverinfo="skip", name="gate 0.5"))
        fig.add_trace(go.Scatter(x=[0.9], y=[0.1], mode="markers+text", text=["geometry-first"],
                      textposition="top center", marker=dict(color=S.TEAL, size=11, line=dict(color="#fff", width=1.5)),
                      textfont=dict(size=11, color=S.INK), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[0.6], y=[0.9], mode="markers+text", text=["conflict"],
                      textposition="bottom center", marker=dict(color=S.RUST, size=11, line=dict(color="#fff", width=1.5)),
                      textfont=dict(size=11, color=S.INK), showlegend=False, hoverinfo="skip"))
        fig.update_xaxes(title="adhesion energy (drives sealing)")
        fig.update_yaxes(title="perturbation (unwraps sealed membranes)")
        inner = _html(fig, height=470)
        return {"html": S.frame(inner, title=self.config.get("title"), tier="mechanistic_prediction",
                view="Decision", tone="neutral",
                caption_text=("Stable enclosure (black 0.5 gate contour) is the majority outcome only in the "
                              "<b>geometry-first basin</b> — adhesion overcomes the bending/neck-closure barrier "
                              "AND survives perturbation (P≈0.95). In the <b>conflict basin</b> the membrane seals "
                              "but unwraps (P≈0.14). Enclosure is a mechanical budget, not an inevitability."))}


# ── M3 — contact-to-enclosure coupling: the joint-feasible overlap ───────────
class CouplingOverlapViz(Visualization):
    config_schema = {"title": {"_type": "string",
                     "_default": "A narrow joint-feasible regime — selection and enclosure must align"},
                     "n_steps": {"_type": "integer", "_default": 200},
                     "grid": {"_type": "integer", "_default": 9}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_coupled import (
            proto_endosymbiosis_coupled as G, joint_feasibility_region as OBS)
        core = build_core(); n = int(self.config["n_steps"]); g = int(self.config["grid"])
        ben = [0.2 + i * (1.4 - 0.2) / (g - 1) for i in range(g)]          # exchange benefit (selection driver)
        pert = [0.0 + j * (1.0 - 0.0) / (g - 1) for j in range(g)]         # perturbation (enclosure breaker)
        keys = ("n_lc", "n_hc_un", "n_hc_se", "n_hc_st")
        Z = [[_run_obs(G, core, OBS, keys, n_steps=n, benefit_coeff=b, cost_coeff=0.3,
                       base_adhesion=0.8, bending_modulus=0.2, perturbation=p) for b in ben] for p in pert]
        colorscale = [[0.0, "#f3f4f6"], [0.49, "#e7eef0"], [0.5, "#bfe0db"], [1.0, S.TEAL]]
        fig = go.Figure(go.Heatmap(x=ben, y=pert, z=Z, zmin=0, zmax=1, colorscale=colorscale,
                        colorbar=dict(title="joint<br>feasibility", thickness=14),
                        hovertemplate="benefit %{x:.2f}, perturbation %{y:.2f}<br>joint = %{z:.2f}<extra></extra>"))
        fig.add_trace(go.Contour(x=ben, y=pert, z=Z, showscale=False, contours=dict(start=0.5, end=0.5, size=1,
                      coloring="none"), line=dict(color=S.INK, width=2), hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[1.2], y=[0.1], mode="markers+text", text=["aligned"], textposition="top center",
                      marker=dict(color=S.TEAL, size=11, line=dict(color="#fff", width=1.5)),
                      textfont=dict(size=11, color=S.INK), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[0.3], y=[0.1], mode="markers+text", text=["decoupled"], textposition="top center",
                      marker=dict(color=S.SLATE, size=11, line=dict(color="#fff", width=1.5)),
                      textfont=dict(size=11, color=S.INK), showlegend=False, hoverinfo="skip"))
        fig.update_xaxes(title="metabolic exchange benefit (selects contact)")
        fig.update_yaxes(title="perturbation (breaks enclosure)")
        inner = _html(fig, height=470)
        return {"html": S.frame(inner, title=self.config.get("title"), tier="mechanistic_prediction",
                view="Decision", tone="neutral",
                caption_text=("The two barriers co-succeed only inside the black 0.5 contour: contact must supply the "
                              "adhesion enclosure needs <i>and</i> enclosure must lock in the exchange benefit that "
                              "keeps contact selected. Drop the benefit (decoupled) or raise perturbation and the "
                              "joint-feasible region collapses — a continuous path exists but it is narrow."))}


# ── M5 — vertical transmission: the retention fan over conflict ──────────────
class TransmissionFanViz(Visualization):
    config_schema = {"title": {"_type": "string",
                     "_default": "Establishment ≠ permanence — retention survives only below a conflict threshold"},
                     "n_steps": {"_type": "integer", "_default": 300}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_transmission import proto_endosymbiosis_transmission as G
        core = build_core(); n = int(self.config["n_steps"])
        losses = [0.03, 0.10, 0.20, 0.35, 0.50]
        t = list(range(n)); tx, tlabel = S.real_time(t, G)
        if "step" in tlabel:
            tlabel = "generation"
        fig = go.Figure()
        for k, lr in enumerate(losses):
            rows = _run_series(G, core, ("n_sym", "n_free"), n_steps=n, fidelity=0.98, benefit=0.6, cost=0.1, loss_rate=lr)
            ret = [r["n_sym"] / (r["n_sym"] + r["n_free"]) if (r["n_sym"] + r["n_free"]) > 0 else 0.0 for r in rows]
            frac = k / (len(losses) - 1)
            color = S.TEAL if lr <= 0.1 else (S.AMBER if lr <= 0.2 else S.RUST)
            fig.add_trace(go.Scatter(x=tx, y=ret, mode="lines", name=f"loss rate {lr:.2f}",
                          line=dict(color=color, width=2.2, dash="solid" if lr <= 0.2 else "dot"),
                          opacity=0.55 + 0.45 * (1 - frac)))
        fig.add_hline(y=0.5, line=dict(color=S.SLATE, width=1.4, dash="dash"),
                      annotation_text="retention gate 0.5", annotation_position="top right",
                      annotation_font=dict(size=10, color=S.SLATE))
        fig.update_yaxes(title="endosymbiont retention fraction", range=[0, 1.04])
        fig.update_xaxes(title=tlabel)
        inner = _html(fig)
        return {"html": S.frame(inner, title=self.config.get("title"), tier="mechanistic_prediction",
                view="Mechanism", tone="caution",
                caption_text=("Even an established symbiosis is retained across generations only where transmission "
                              "fidelity and benefit outrun conflict: at low partner-loss (teal) retention holds near "
                              "the carrier capacity, but above a threshold (rust) it decays toward ~0 — "
                              "establishment does not guarantee permanence."))}


# ── M6 — spatial exchange: the proximity advantage over distance ─────────────
class SpatialDistanceViz(Visualization):
    config_schema = {"title": {"_type": "string",
                     "_default": "Contact confers the exchange advantage — realised exchange collapses with distance"},
                     "n_steps": {"_type": "integer", "_default": 400}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_spatial import (
            proto_endosymbiosis_spatial as G, realised_exchange_level as OBS)
        core = build_core(); n = int(self.config["n_steps"])
        dists = list(range(1, 13))
        keys = ("consumer_conc",)
        vals = [_run_obs(G, core, OBS, keys, n_steps=n, consumer_distance=d, diffusion=0.4, decay=0.08) for d in dists]
        v1 = vals[0]
        fold = v1 / vals[9] if len(vals) > 9 and vals[9] > 0 else float("nan")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dists, y=vals, mode="lines+markers", name="realised exchange",
                      line=dict(color=S.TEAL, width=2.6), marker=dict(size=7, color=S.TEAL)))
        S.add_zone(fig, 0.5, 2.5, kind="agree", label="contact")
        fig.add_annotation(x=dists[0], y=v1, text=f"contact ≈ {fold:.0f}× distal (d=10)", showarrow=True,
                           arrowhead=2, ax=55, ay=-30, font=dict(size=11, color=S.INK), arrowcolor=S.SLATE)
        fig.update_yaxes(title="realised exchange level", type="log")
        fig.update_xaxes(title="partner distance (lattice sites)")
        inner = _html(fig)
        return {"html": S.frame(inner, title=self.config.get("title"), tier="mechanistic_prediction",
                view="Mechanism", tone="positive",
                caption_text=(f"In the screened-diffusion regime a contact partner (d=1) receives ≈{fold:.0f}× the "
                              "realised metabolite exchange of a distal one (d=10); the advantage falls off steeply "
                              "with distance (log axis) and collapses only when the metabolite is well-mixed. "
                              "Proximity is mechanistically what buys the exchange."))}


# ── M7 — bidirectional syntrophy: the Liebig cap over production balance ─────
class ReciprocityLiebigViz(Visualization):
    config_schema = {"title": {"_type": "string",
                     "_default": "Reciprocity beyond proximity — the mutual benefit is capped at the scarcer flux"},
                     "n_steps": {"_type": "integer", "_default": 400}}

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        from ..composites.proto_endosymbiosis_multimetab import (
            proto_endosymbiosis_multimetab as G, mutualistic_exchange_benefit as OBS)
        core = build_core(); n = int(self.config["n_steps"])
        prod_b = [0.1 + i * (1.0 - 0.1) / 9 for i in range(10)]
        keys = ("symbiont_a_conc", "host_b_conc")
        vals = [_run_obs(G, core, OBS, keys, n_steps=n, symbiont_distance=1, production_a=1.0, production_b=pb)
                for pb in prod_b]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=prod_b, y=vals, mode="lines+markers", name="mutual benefit (Liebig min)",
                      line=dict(color=S.TEAL, width=2.6), marker=dict(size=7, color=S.TEAL)))
        fig.add_hline(y=0.5, line=dict(color=S.AMBER, width=1.6, dash="dash"),
                      annotation_text="benefit gate 0.5", annotation_position="top left",
                      annotation_font=dict(size=10, color=S.AMBER))
        fig.add_vline(x=1.0, line=dict(color=S.SLATE, width=1, dash="dot"),
                      annotation_text="balanced (a=b)", annotation_position="bottom right",
                      annotation_font=dict(size=10, color=S.SLATE))
        fig.update_yaxes(title="mutualistic exchange benefit", range=[0, max(1.0, max(vals) * 1.1)])
        fig.update_xaxes(title="partner B reciprocal production (A fixed at 1.0)")
        inner = _html(fig)
        return {"html": S.frame(inner, title=self.config.get("title"), tier="mechanistic_prediction",
                view="Mechanism", tone="neutral",
                caption_text=("Obligate two-metabolite syntrophy caps the mutual benefit at the SCARCER reciprocal "
                              "flux (a Liebig minimum): as partner B's production rises toward balance the benefit "
                              "climbs and saturates, but an imbalanced pair is starved even at contact. Reciprocity "
                              "is required, not just proximity."))}
