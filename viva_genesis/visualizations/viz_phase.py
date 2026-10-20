"""Decision-view figures — phase maps rendered from sweep surfaces.

A trajectory viz runs ONE composite (~seconds); a phase map runs a whole sweep
(hundreds of composites, minutes). So these figures render from a
:class:`~viva_genesis.sweep.SweepResult` that was computed once — by a dedicated
sweep runner (high-res, parallel/Ray on the mini) that persists the grid, or, as a
fallback, by the viz itself at a modest resolution when it runs at canonical-run
time (rendered once into ``viz.json``, not per page-load).
"""
from __future__ import annotations

import json

import numpy as np
from process_bigraph.visualization import Visualization

from . import viz_style as S
from .viz_style import INK as _INK, TEAL as _TEAL, AMBER as _AMBER, SLATE as _SLATE, RUST as _RUST


def sweep_to_json(res) -> str:
    """Serialize a SweepResult's axes + surfaces to JSON (for persistence)."""
    return json.dumps({
        "axis_order": res.axis_order,
        "axes": {k: v.tolist() for k, v in res.axes.items()},
        "surfaces": {k: v.tolist() for k, v in res.surfaces.items()},
        "meta": res.meta,
    })


def _resolve_grid_path(path: str) -> str | None:
    """Resolve a persisted-grid path robustly: as-is, then relative to cwd, then
    relative to the workspace root (walk up for workspace.yaml). Returns the first
    existing path, or None (→ the viz computes a modest grid live)."""
    import os
    if not path:
        return None
    if os.path.isabs(path) and os.path.exists(path):
        return path
    cand = os.path.abspath(path)
    if os.path.exists(cand):
        return cand
    here = os.path.abspath(os.getcwd())
    for _ in range(8):
        if os.path.exists(os.path.join(here, "workspace.yaml")):
            cand = os.path.join(here, path)
            return cand if os.path.exists(cand) else None
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    return None


def _grid_from_json(blob: dict):
    axes = {k: np.asarray(v, float) for k, v in blob["axes"].items()}
    surfaces = {k: np.asarray(v, float) for k, v in blob["surfaces"].items()}
    return blob["axis_order"], axes, surfaces, blob.get("meta", {})


def carbon_fixation_phase_figure(fav, tut=None, *, title=None) -> str:
    """Two-panel PRIMARY decision figure for og-01: SUSTAINED reduced-carbon throughput
    over (vent pH × dissolved H₂), favourable vs the Tutolo-2026 gradient collapse, on
    shared axes and a shared colour scale. The colour is the sustained throughput; the
    white contour is the feasible boundary (throughput > 0), hatched cells are
    zero/infeasible flux, and the bold teal contour marks where flux is SUSTAINED (held
    over most of the run) rather than merely a transient thermodynamic possibility.
    ``fav``/``tut`` are SweepResults."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    ph = fav.axes["ph_vent"]
    h2 = fav.axes["h2"]
    eps = 1e-6                                               # feasible-flux floor (mol-C/s)
    # surface is indexed [ph, h2]; Contour wants z[y=h2][x=ph] → transpose, ×1e3.
    z_fav = (fav.surfaces["sustained_throughput"] * 1e3).T
    sf_fav = np.asarray(fav.surfaces.get("sustained_frac", np.zeros_like(fav.surfaces["sustained_throughput"]))).T
    tp_fav = np.asarray(fav.surfaces["sustained_throughput"]).T
    panels = [("Favourable parameterization\n(sustained gradient)", z_fav, tp_fav, sf_fav)]
    if tut is not None:
        z_tut = (tut.surfaces["sustained_throughput"] * 1e3).T
        sf_tut = np.asarray(tut.surfaces.get("sustained_frac", np.zeros_like(tut.surfaces["sustained_throughput"]))).T
        tp_tut = np.asarray(tut.surfaces["sustained_throughput"]).T
        panels.append(("Tutolo-2026 in-situ collapse\n(gradient efficiency 0.1)", z_tut, tp_tut, sf_tut))

    zmax = max(float(np.nanmax(p[1])) for p in panels)
    fig = make_subplots(rows=1, cols=len(panels),
                        subplot_titles=[p[0].replace("\n", "<br>") for p in panels],
                        horizontal_spacing=0.12, shared_yaxes=True)

    for i, (_, z, tp, sf) in enumerate(panels, start=1):
        fig.add_trace(go.Contour(
            x=ph, y=h2, z=z, zmin=0.0, zmax=zmax,
            colorscale="Viridis", showscale=(i == len(panels)),
            colorbar=dict(title="sustained<br>throughput<br>(10⁻³ mol-C s⁻¹)", len=0.9),
            contours=dict(showlabels=True, labelfont=dict(size=10, color="white")),
            line=dict(width=0.5, color="rgba(255,255,255,0.35)"),
        ), row=1, col=i)
        # feasible boundary: throughput > eps (any positive net carbon flux).
        fig.add_trace(go.Contour(x=ph, y=h2, z=tp, showscale=False,
                                 contours=dict(start=eps, end=eps, coloring="lines"),
                                 line=dict(color="#f8fafc", width=1.8),
                                 hoverinfo="skip"), row=1, col=i)
        # SUSTAINED-vs-thermodynamic-possibility: teal contour where flux is held over
        # ≥ half the run (sustained_frac ≥ 0.5), not a transient feasibility blip.
        fig.add_trace(go.Contour(x=ph, y=h2, z=sf, showscale=False,
                                 contours=dict(start=0.5, end=0.5, coloring="lines"),
                                 line=dict(color=_TEAL, width=2.6, dash="dash"),
                                 hoverinfo="skip"), row=1, col=i)
        # zero / infeasible-flux region explicitly marked (ΔG′ ≥ 0, or no gradient/H₂).
        zero = np.where(tp <= eps, 1.0, np.nan)
        fig.add_trace(go.Heatmap(x=ph, y=h2, z=zero, showscale=False,
                                 colorscale=[[0, "rgba(100,116,139,0.33)"], [1, "rgba(100,116,139,0.33)"]],
                                 hoverinfo="skip"), row=1, col=i)
        # favourable operating point (Preiner-style): pH 9.5, H2 5 mM.
        fig.add_trace(go.Scatter(
            x=[9.5], y=[5.0e-3], mode="markers+text", text=["favourable<br>operating point"],
            textposition="top center", textfont=dict(size=10, color=_INK),
            marker=dict(symbol="star", size=15, color=_AMBER,
                        line=dict(width=1.2, color=_INK)), showlegend=False,
        ), row=1, col=i)
        fig.update_yaxes(type="log", title_text=("dissolved H₂ (M)" if i == 1 else None),
                         row=1, col=i)
        fig.update_xaxes(title_text="vent pH (alkaline side; ocean = 6.0)", row=1, col=i)

    fig.update_layout(**S.base_layout(height=460, width=470 * len(panels),
                                      margin=dict(t=54, b=70, l=70, r=20), showlegend=False))
    cap = ("<b>Sustained modeled carbon throughput occupies a restricted dissolved-H₂ × vent-pH "
           "regime, conditional on catalyst activity and gradient maintenance.</b> Colour is the "
           "modeled sustained reduced-carbon throughput (open-flow vent reactor); the white contour is "
           "the feasible boundary (any positive net flux) and the teal dashed contour is where flux is "
           "SUSTAINED over ≥ half the run &mdash; distinct from a merely thermodynamically possible "
           "transient. Grey-shaded cells are zero / infeasible flux (ΔG′ ≥ 0, or a no-gradient / "
           "no-catalyst / no-H₂ control). The Tutolo-2026 collapse (right) contracts the sustained "
           "region on the same axes. Limit: a modeled landscape, not an experimental reproduction; "
           "replicate/parameter uncertainty bands and lab-regime overlays are not yet attached.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The carbon-fixation landscape"),
                   phase="Campaign I", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


def protometabolism_gain_figure(res, *, title=None) -> str:
    """og-02 Decision view (PRIMARY): the protometabolic persistence landscape over
    (washout × feed CO₂). **Left:** the settled amplification gain (dimensionless) with
    the gain=1 line — a NECESSARY but not sufficient condition, NOT by itself evidence of
    autocatalysis. **Right:** net carbon throughput with the washout boundary (flux → 0).
    The bold teal contour on both panels is the COMBINED gate — gain > 1 AND positive
    sustained net flux — the only region where amplification and sustained throughput
    coexist. OAA abundance alone is deliberately NOT the colour of the decision panels.
    ``res`` is a SweepResult / grid view with ``gain`` and ``net_flux`` surfaces."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    feed = res.axes["feed_CO2"]
    wash = res.axes["k_wash"]
    net = res.surfaces["net_flux"] * 1e3            # 10⁻³ mol-C/s, indexed [feed, wash]
    net_raw = np.asarray(res.surfaces["net_flux"])
    gain = np.asarray(res.surfaces["gain"])
    eps = 1e-6                                       # positive-sustained-flux floor
    # combined gate: gain > 1 AND net flux > 0 (sustained throughput). Encode as a field
    # that is 1 inside the gate, so its 0.5 contour is the combined-gate boundary.
    combined = np.where((gain > 1.0) & (net_raw > eps), 1.0, 0.0)

    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.12,
                        subplot_titles=("Settled amplification gain (dimensionless)",
                                        "Net carbon throughput (10⁻³ mol-C s⁻¹)"))
    # LEFT: gain itself (not OAA abundance), diverging about the gain=1 threshold.
    gmax = float(np.nanmax(np.abs(gain - 1.0))) or 1.0
    fig.add_trace(go.Contour(x=wash, y=feed, z=gain, colorscale="RdBu_r", ncontours=16,
                             zmid=1.0, zmin=1.0 - gmax, zmax=1.0 + gmax,
                             colorbar=dict(title="gain<br>(dimensionless)", len=0.9, x=0.44),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="#1e293b")),
                             line=dict(width=0.4, color="rgba(100,116,139,0.3)")), row=1, col=1)
    # gain = 1 line (necessary, not sufficient).
    fig.add_trace(go.Contour(x=wash, y=feed, z=gain, showscale=False,
                             contours=dict(start=1, end=1, coloring="lines"),
                             line=dict(color="#1e293b", width=1.6, dash="dot"),
                             hoverinfo="skip"), row=1, col=1)
    # RIGHT: net throughput + washout boundary (flux → 0).
    fig.add_trace(go.Contour(x=wash, y=feed, z=net, colorscale="Inferno", ncontours=14, showscale=True,
                             colorbar=dict(title="net flux<br>(10⁻³ mol-C s⁻¹)", len=0.9),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=2)
    fig.add_trace(go.Contour(x=wash, y=feed, z=net_raw, showscale=False,
                             contours=dict(start=eps, end=eps, coloring="lines"),
                             line=dict(color="#f8fafc", width=1.8),
                             hoverinfo="skip"), row=1, col=2)
    # the COMBINED gate boundary (gain>1 AND sustained flux>0) on both panels.
    for c in (1, 2):
        fig.add_trace(go.Contour(x=wash, y=feed, z=combined, showscale=False,
                                 contours=dict(start=0.5, end=0.5, coloring="lines"),
                                 line=dict(color=_TEAL, width=2.8, dash="dash"),
                                 hoverinfo="skip"), row=1, col=c)
        fig.add_trace(go.Scatter(x=[0.05], y=[2.0e-3], mode="markers+text",
                                 text=["operating<br>point"], textposition="top center",
                                 textfont=dict(size=9, color=_INK),
                                 marker=dict(symbol="star", size=14, color=_AMBER,
                                             line=dict(width=1.1, color=_INK)), showlegend=False), row=1, col=c)
        fig.update_xaxes(type="log", title_text="washout / dilution k_wash (1/s)", row=1, col=c)
    fig.update_yaxes(type="log", title_text="feed CO₂ (M)", row=1, col=1)

    fig.update_layout(**S.base_layout(height=450, width=940, margin=dict(t=54, b=60, l=70, r=20),
                                      showlegend=False))
    cap = ("<b>Autocatalytic gain and sustained throughput coexist only in a bounded CO₂-feed × "
           "washout window.</b> Left colour is the settled amplification GAIN (the gain=1 dotted line is "
           "necessary, not sufficient); right colour is net carbon throughput, with the white washout "
           "boundary where flux → 0. The teal dashed contour on both panels is the COMBINED gate &mdash; "
           "gain &gt; 1 AND positive sustained net flux &mdash; and OAA abundance is deliberately NOT the "
           "decision colour, since a transient OAA rise is not by itself self-sustaining autocatalysis. "
           "Limit: gain here is the settled amplification; whether it persists after the transient (rather "
           "than being carried by source terms) is tracked as the separate og-autocatalysis line.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The protometabolic persistence landscape"),
                   phase="Campaign II", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class ProtometabolismGainPhaseMap(Visualization):
    """og-02 Decision view: the protometabolic ignition landscape over
    (washout × feed CO₂) — the bounded region where the real libRoadRunner rTCA
    network persists + self-amplifies, with the gain=1 autocatalytic threshold.
    Renders from a persisted grid (``grid_json``) or computes a modest grid live."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign II — the protometabolic ignition landscape"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 12},
        "n_steps": {"_type": "integer", "_default": 60},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import protometabolism_gain_phase_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                blob = json.load(f)
            res = _ResultView(*_grid_from_json(blob["gain"] if "gain" in blob else blob))
        else:
            n = int(self.config["n_grid"])
            res = protometabolism_gain_phase_map(feed_CO2=(1.0e-4, 1.0e-2, n),
                                                 k_wash=(2.0e-3, 1.0, n),
                                                 n_steps=int(self.config["n_steps"]), n_jobs=1)
        return {"html": protometabolism_gain_figure(res, title=self.config["title"])}


def pore_ignition_figure(gain_grid, traj, enrichment, dilute, enriched, k_wash, *, title=None) -> str:
    """og-03 headline: the thermophoretic trap's localization moves the dilute vent
    feed ACROSS og-02's ignition threshold — a metabolizing individual appears in the
    pore but not in the well-mixed ocean. Left: the og-02 ignition landscape with the
    dilute→enriched crossing. Right: the OAA trajectories (well-mixed dead vs pore
    ignites). ``gain_grid`` is the og-02 grid view; ``traj`` = {t, oaa_mixed, oaa_pore}."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.13,
                        subplot_titles=("Crossing the ignition threshold",
                                        "Does a metabolizing individual appear?"))
    # --- left: og-02 ignition landscape + the crossing ---
    feed = gain_grid.axes["feed_CO2"]
    wash = gain_grid.axes["k_wash"]
    oaa = np.log10(np.clip(gain_grid.surfaces["oaa_pool"] * 1e3, 1e-4, None))
    gain = gain_grid.surfaces["gain"]
    fig.add_trace(go.Contour(x=wash, y=feed, z=oaa, colorscale="Viridis", ncontours=12,
                             colorbar=dict(title="log₁₀<br>OAA (mM)", len=0.9, x=0.44),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=1)
    fig.add_trace(go.Contour(x=wash, y=feed, z=gain, showscale=False,
                             contours=dict(start=1, end=1, coloring="lines"),
                             line=dict(color="#f8fafc", width=2.2, dash="dash"), hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=[k_wash, k_wash], y=[dilute, enriched], mode="lines",
                             line=dict(color=_AMBER, width=2.5), showlegend=False,
                             hoverinfo="skip"), row=1, col=1)
    fig.add_annotation(x=np.log10(k_wash), y=np.log10(enriched), ax=np.log10(k_wash), ay=np.log10(dilute),
                       xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2,
                       arrowwidth=2, arrowcolor=_AMBER, row=1, col=1)
    fig.add_trace(go.Scatter(x=[k_wash], y=[dilute], mode="markers+text", text=["well-mixed<br>(dilute)"],
                             textposition="middle right", textfont=dict(size=9, color=_INK),
                             marker=dict(size=12, color=_SLATE, line=dict(width=1, color=_INK)),
                             showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=[k_wash], y=[enriched], mode="markers+text",
                             text=[f"in pore<br>(×{enrichment:.0f}, capped)"], textposition="top center",
                             textfont=dict(size=9, color=_INK),
                             marker=dict(symbol="star", size=15, color=_TEAL, line=dict(width=1.1, color=_INK)),
                             showlegend=False), row=1, col=1)
    fig.update_xaxes(type="log", title_text="washout k_wash (1/s)", row=1, col=1)
    fig.update_yaxes(type="log", title_text="feed CO₂ (M)", row=1, col=1)
    # --- right: the OAA trajectories ---
    t = traj["t"]
    fig.add_trace(go.Scatter(x=t, y=[v * 1e3 for v in traj["oaa_mixed"]], mode="lines",
                             line=dict(color=_SLATE, width=2.5, dash="dot"), name="well-mixed ocean"), row=1, col=2)
    fig.add_trace(go.Scatter(x=t, y=[v * 1e3 for v in traj["oaa_pore"]], mode="lines",
                             line=dict(color=_TEAL, width=3), name="inside the pore"), row=1, col=2)
    fig.update_xaxes(title_text=traj.get("t_label", "time (steps)"), row=1, col=2)
    fig.update_yaxes(title_text="autocatalytic hub OAA (mM)", row=1, col=2)

    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=70, r=20),
                                      legend=dict(orientation="h", y=1.02, x=1.0, xanchor="right",
                                                  font=dict(size=10))))
    cap = (
        f"A reduced, enrichment-capped illustration (&times;{enrichment:.0f}, within the 60&times; cap, "
        "not a graded result): the pore's localization lifts the dilute feed across og-02's ignition "
        "threshold (dashed) while the same chemistry stays dead in the well-mixed ocean &mdash; so the "
        "metabolizing individual is a product of <i>localization</i>, not of new reactions. The graded "
        "localization result is the pore-localization frontier (Decision view); this couples it to the "
        "og-02 network to show the consequence."
    )
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Localization lifts the feed across the ignition threshold"),
                   phase="Campaign III", view="Mechanism", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="caution")


class PoreIgnitionCoupling(Visualization):
    """og-03 Decision/Mechanism view: couples the real thermophoretic trap to the
    real og-02 network. The pore's enrichment lifts the dilute vent feed across the
    ignition threshold, so a metabolizing individual appears in the pore but not in
    the well-mixed ocean. Loads the og-02 gain grid (``grid_json``) or computes one."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign III — localization makes the individual"},
        "grid_json": {"_type": "string", "_default": ""},
        "pore_length": {"_type": "float", "_default": 1.5e-3},
        "porosity": {"_type": "float", "_default": 0.6},
        "dilute_feed": {"_type": "float", "_default": 5.0e-5},
        "enrichment_cap": {"_type": "float", "_default": 60.0},
        "k_wash": {"_type": "float", "_default": 0.05},
        "n_steps": {"_type": "integer", "_default": 60},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from process_bigraph import Composite, gather_emitter_results

        from ..composites.protometabolism import protometabolic_network
        from ..composites.thermophoretic_concentration import thermophoretic_concentration
        from ..core import build_core
        from ..phase_maps import protometabolism_gain_phase_map

        core = build_core()
        # real trap enrichment
        tdoc = thermophoretic_concentration(core, pore_length=float(self.config["pore_length"]),
                                            porosity=float(self.config["porosity"]))
        tsim = Composite({"state": tdoc}, core=core); tsim.run(10)
        E = float(gather_emitter_results(tsim)[("emitter",)][-1]["enrichment_factor"])
        dilute = float(self.config["dilute_feed"])
        enriched = dilute * min(E, float(self.config["enrichment_cap"]))
        # run og-02 at both feeds → OAA trajectories
        n = int(self.config["n_steps"])
        traj = {"t": list(range(n + 1)), "oaa_mixed": [], "oaa_pore": []}
        for feed, key in ((dilute, "oaa_mixed"), (enriched, "oaa_pore")):
            doc = protometabolic_network(core, feed_CO2=feed, feed_pyruvate=feed * 0.05)
            sim = Composite({"state": doc}, core=core)
            sim.run(n)
            rows = gather_emitter_results(sim)[("emitter",)]
            traj[key] = [r.get("OAA", 0.0) for r in rows]
            traj["t"], traj["t_label"] = S.real_time(
                [r.get("global_time", i) for i, r in enumerate(rows)], protometabolic_network)
        # og-02 ignition landscape (persisted grid or a modest live grid)
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                blob = json.load(f)
            grid = _ResultView(*_grid_from_json(blob["gain"] if "gain" in blob else blob))
        else:
            grid = protometabolism_gain_phase_map(feed_CO2=(1e-4, 1e-2, 12), k_wash=(2e-3, 1.0, 12),
                                                  n_steps=50, n_jobs=1)
        return {"html": pore_ignition_figure(grid, traj, min(E, float(self.config["enrichment_cap"])),
                                             dilute, enriched, float(self.config["k_wash"]),
                                             title=self.config["title"])}


def pore_ignition_threshold_figure(demo: dict, meta: dict, *, title=None) -> str:
    """og-spatial-concentration PRIMARY: the enrichment→ignition BRIDGE, read from the
    committed og-30 matched pore-vs-control artifact (``gate_b_spatial.json`` →
    ``ignition_demo``). Both arms are fed IDENTICAL input chemistry (base feed held
    equal); the structured pore's thermophoretic enrichment lifts the pore-LOCAL feed
    above the network's amplification threshold, so the coupled reaction network
    ignites in the pore but not in the matched well-mixed control. Endpoint values
    (net productive carbon flux, enrichment, persistent species) from the real
    composite runs — NOT a re-simulation at page load."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    pore, ctrl = demo.get("pore", {}), demo.get("control", {})
    base_feed = float(meta.get("demo_base_feed", pore.get("feed_CO2", 0.0)))
    enr = float(pore.get("enrichment", 1.0))
    pore_flux = float(pore.get("net_carbon_flux", 0.0))
    ctrl_flux = float(ctrl.get("net_carbon_flux", 0.0))
    pore_feed = float(pore.get("feed_CO2", base_feed))
    thr = 1.0e-6  # ignition metric: net_carbon_flux > 1e-6 AND network_connected
    pore_conn = bool(pore.get("network_connected"))
    ctrl_conn = bool(ctrl.get("network_connected"))

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.17,
                        subplot_titles=("Net productive carbon flux (ignition metric)",
                                        "What differs: pore-local feed under equal input"))
    # --- left: net carbon flux, pore vs matched well-mixed control, with threshold ---
    arms = ["inside the pore", "well-mixed control"]
    fluxes = [pore_flux, ctrl_flux]
    cols = [_TEAL, _SLATE]
    fig.add_trace(go.Bar(x=arms, y=fluxes, marker_color=cols, width=0.55,
                         text=[f"{pore_flux:+.2e}<br>{'connected' if pore_conn else 'not connected'}",
                               f"{ctrl_flux:+.2e}<br>{'connected' if ctrl_conn else 'not connected'}"],
                         textposition="outside", textfont=dict(size=10), showlegend=False,
                         hoverinfo="skip"), row=1, col=1)
    fig.add_hline(y=thr, line=dict(color=_RUST, width=1.8, dash="dash"), row=1, col=1)
    fig.add_annotation(x=1.4, y=thr, text=f"ignition threshold<br>(flux &gt; {thr:.0e} AND connected)",
                       showarrow=False, yshift=16, xanchor="right",
                       font=dict(size=9, color=_RUST), row=1, col=1)
    fig.add_hline(y=0.0, line=dict(color="#94a3b8", width=1), row=1, col=1)
    fig.update_yaxes(title_text="net productive carbon flux (mol-C / s)", row=1, col=1)
    # --- right: the single thing that differs — the pore-local feed (equal base feed) ---
    feed_arms = ["base feed<br>(held equal)", "well-mixed<br>control feed", f"pore-local feed<br>(&times;{enr:.0f})"]
    feeds = [base_feed, float(ctrl.get("feed_CO2", base_feed)), pore_feed]
    fig.add_trace(go.Bar(x=feed_arms, y=feeds, marker_color=[_INK, _SLATE, _TEAL], width=0.6,
                         text=[f"{base_feed:.1e} M", f"{float(ctrl.get('feed_CO2', base_feed)):.1e} M",
                               f"{pore_feed:.1e} M"], textposition="outside",
                         textfont=dict(size=10), showlegend=False, hoverinfo="skip"), row=1, col=2)
    fig.update_yaxes(title_text="CO₂ feed into the network (M)", type="log", row=1, col=2)
    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=72, r=20),
                                      showlegend=False))
    cap = (
        "Pore-local enrichment shifts the coupled reaction network across its modeled amplification "
        "threshold, unlike the matched well-mixed control. Both arms receive IDENTICAL input chemistry "
        f"(base feed {base_feed:.0e} M, held equal); the only difference is that the structured pore's "
        f"thermophoretic enrichment (&times;{enr:.0f}, from the FiPy transport solve) raises the "
        f"pore-LOCAL feed to {pore_feed:.1e} M, which carries the network's net carbon flux above the "
        "ignition metric while the stirred control stays sub-threshold and disconnected. "
        "<b>Two distinct claims, kept separate:</b> that a pore ENRICHES a dilute feed is the "
        "concentration-physics verdict of THIS study; that enrichment IGNITES the reaction network "
        "(and the bounded porosity window over which it does) is the verdict of og-network-rescue, "
        "whose committed og-30 artifact this panel reads. The causal transfer is explicit: pore "
        "concentration from FiPy sets the kinetic network's feed — it adds no new reactions."
    )
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Pore enrichment carries the network across its ignition threshold"),
                   subtitle="matched pore vs well-mixed control at equal input chemistry (committed og-30 endpoints)",
                   phase="Campaign III", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="caution")


class PoreIgnitionThresholdViz(Visualization):
    """og-spatial-concentration PRIMARY (the enrichment→ignition bridge): reads the
    committed matched pore-vs-well-mixed control artifact from og-network-rescue's
    og-30 arm (``report_json`` → ``ignition_demo``) and shows the pore crossing the
    network's ignition threshold under EQUAL input chemistry while the control does
    not. Reads committed endpoints — no simulation at page load. The full ignition
    verdict and its bounded geometry window are og-network-rescue's result; here the
    figure makes the causal payoff of enrichment explicit."""

    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        path = _resolve_grid_path(str(self.config.get("report_json", "") or ""))
        if not path:
            return {"html": "<p>matched pore-vs-control artifact (og-30 gate_b_spatial.json) not found.</p>"}
        with open(path) as f:
            blob = json.load(f)
        demo = blob.get("ignition_demo", {})
        meta = blob.get("meta", {})
        if not demo:
            return {"html": "<p>artifact has no ignition_demo block.</p>"}
        return {"html": pore_ignition_threshold_figure(demo, meta, title=self.config["title"])}


def protocell_decision_figure(arc, feas, *, title=None) -> str:
    """og-04 Decision view: (left) the retention-access plane — the compartment sweeps
    from too-closed through a viable window to too-open as permeability rises; (right)
    the salt-tolerance feasibility map — the viable ceiling rises with mixed
    amphiphiles. ``arc`` is the temperature sweep; ``feas`` the (mix × salt) sweep."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.18,
                        subplot_titles=("Access ↔ retention tradeoff (Pareto; stability coded)",
                                        "Viable salt ceiling rises with mixed amphiphiles"))
    # --- left: the access↔retention Pareto scatter, every (composition × salt) grid
    # point from the feasibility sweep. x = substrate permeability (access), y = product
    # retention; colour = co-surfactant fraction (membrane composition); filled = meets
    # the modeled stability criterion (individuality > threshold), open = fails it. The
    # feasible region (ret × acc > threshold) is shaded, so the tradeoff is explicit:
    # permeability and retention pull against each other and only a subset also stays stable.
    f_acc = np.asarray(feas.surfaces["access"], float).ravel()
    f_ret = np.asarray(feas.surfaces["retention"], float).ravel()
    f_ind = np.asarray(feas.surfaces["individuality"], float).ravel()
    _mix_ax = np.asarray(feas.axes["mix_fraction"], float)
    _salt_ax = np.asarray(feas.axes["ionic_strength"], float)
    MIXg, SALTg = np.meshgrid(_mix_ax, _salt_ax, indexing="ij")
    f_mix = MIXg.ravel()
    f_salt = SALTg.ravel()
    _pass = float(feas.meta.get("viable_threshold", 0.1))
    # shaded feasible region: retention × access > threshold (the stability hyperbola)
    _xs = np.linspace(max(_pass, 1e-3), 1.0, 120)
    _yhyp = np.clip(_pass / _xs, 0.0, 1.02)
    fig.add_trace(go.Scatter(x=np.r_[_xs, _xs[::-1]], y=np.r_[_yhyp, np.full_like(_xs, 1.02)[::-1]],
                             fill="toself", fillcolor="rgba(13,148,136,0.10)", mode="lines",
                             line=dict(width=0), hoverinfo="skip", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=_xs, y=_yhyp, mode="lines", line=dict(color=_TEAL, width=1.6, dash="dash"),
                             hoverinfo="skip", showlegend=False), row=1, col=1)
    _stable = f_ind > _pass
    for _msk, _sym, _lbl in ((_stable, "circle", "meets stability"),
                             (~_stable, "circle-open", "fails stability")):
        if not _msk.any():
            continue
        fig.add_trace(go.Scatter(
            x=f_acc[_msk], y=f_ret[_msk], mode="markers", name=_lbl,
            marker=dict(size=7, symbol=_sym, color=f_mix[_msk], colorscale="Viridis",
                        cmin=float(_mix_ax.min()), cmax=float(_mix_ax.max()),
                        colorbar=dict(title="co-surfactant<br>fraction", len=0.9, x=0.44,
                                      thickness=9, title_font=dict(size=10), tickfont=dict(size=9)),
                        line=dict(width=0.8, color="#334155")),
            hovertext=[f"mix {m:.2f}, salt {s:.2f} M<br>indiv {i:.2f}"
                       for m, s, i in zip(f_mix[_msk], f_salt[_msk], f_ind[_msk])],
            hoverinfo="text"), row=1, col=1)
    fig.add_annotation(x=0.98, y=1.0, text=f"feasible<br>(ret×acc > {_pass:g})", showarrow=False,
                       xanchor="right", font=dict(size=9, color=_TEAL), row=1, col=1)
    for x, y, t, col in [(0.22, 0.92, "single FA<br>(tight, starves)", _SLATE),
                         (0.92, 0.25, "too open<br>(leaks)", _RUST)]:
        fig.add_annotation(x=x, y=y, text=t, showarrow=False, font=dict(size=9, color=col), row=1, col=1)
    fig.update_xaxes(title_text="substrate permeability / access", range=[0, 1.02], row=1, col=1)
    fig.update_yaxes(title_text="internal-product retention", range=[0, 1.02], row=1, col=1)
    # --- right: feasibility map ---
    mix = feas.axes["mix_fraction"]
    salt = feas.axes["ionic_strength"]
    fi = feas.surfaces["individuality"]            # [mix, salt] → z[y=mix][x=salt]
    fig.add_trace(go.Contour(x=salt, y=mix, z=fi, colorscale="Viridis", ncontours=12, showscale=True,
                             zmin=0.0, zmax=max(0.5, float(np.nanmax(fi))),
                             colorbar=dict(title="individ.<br>ret×acc", len=0.9),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=2)
    # explicit viable-region PASS boundary (individuality == 0.1): inside it the
    # vesicle both retains chemistry AND imports the gradient — a usable boundary.
    _pass = float(feas.meta.get("viable_threshold", 0.1))
    fig.add_trace(go.Contour(x=salt, y=mix, z=fi, showscale=False,
                             contours=dict(start=_pass, end=_pass, coloring="lines"),
                             line=dict(color="#f8fafc", width=2.6, dash="dash"),
                             hoverinfo="skip"), row=1, col=2)
    fig.add_annotation(x=float(salt.min()), y=float(mix.max()), text=f"viable (individ. > {_pass:g})",
                       showarrow=False, xanchor="left", yshift=6,
                       font=dict(size=9, color=_TEAL), row=1, col=2)
    fig.add_vline(x=0.35, line=dict(color="#f8fafc", width=1.5, dash="dot"), row=1, col=2)
    fig.add_annotation(x=0.35, y=float(mix.min()), text="seawater", showarrow=False, yshift=10,
                       yanchor="bottom", font=dict(size=9, color=_SLATE), row=1, col=2)
    fig.update_xaxes(title_text="ionic strength (M)", row=1, col=2)
    fig.update_yaxes(title_text="co-surfactant fraction", row=1, col=2)

    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=72, l=70, r=20),
                                      showlegend=True,
                                      legend=dict(orientation="h", y=-0.2, x=0.22, xanchor="center",
                                                  font=dict(size=9))))
    cap = ("Membrane compositions trade substrate access against internal-product retention; only a subset "
           "also meets stability criteria. Left: each point is a (composition × salinity) grid cell from the "
           "phenomenological protocell model — x is substrate permeability (access), y is product retention, "
           "colour is co-surfactant fraction (composition). Filled markers meet the modeled stability "
           f"criterion (individuality = retention × access > {_pass:g}); open markers fail it; the feasible "
           "region is shaded. Right: the viable salt ceiling rises with mixed amphiphiles (Jordan 2019). "
           "<b>These are modeled permeability / retention proxies, not observed vesicles</b> — the figure "
           "does not assert physical vesicle formation; the real Martini-MD bilayer/vesicle calibration is "
           "in the protocell-window figure and the og-32 / og-32b MD figures.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Access ↔ retention: a Pareto tradeoff, stability coded"),
                   phase="Campaign IV", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class ProtocellPhaseMap(Visualization):
    """og-04 Decision view: the retention-access plane (3 regimes) + the salt-tolerance
    feasibility map (mixed amphiphiles lift the viable salt ceiling). Computed from
    sweeps of the real protocell composite."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign IV — a boundary that retains without isolating"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_temp": {"_type": "integer", "_default": 24},
        "n_grid": {"_type": "integer", "_default": 14},
        "n_steps": {"_type": "integer", "_default": 15},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import protocell_feasibility_map, protocell_retention_access_arc
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                blob = json.load(f)
            arc = _ResultView(*_grid_from_json(blob["arc"]))
            feas = _ResultView(*_grid_from_json(blob["feas"]))
        else:
            ns = int(self.config["n_steps"])
            arc = protocell_retention_access_arc(temperature=(285.0, 360.0, int(self.config["n_temp"])),
                                                 n_steps=ns)
            n = int(self.config["n_grid"])
            feas = protocell_feasibility_map(mix_fraction=(0.0, 0.6, n), ionic_strength=(0.05, 1.2, n),
                                             n_steps=ns)
        return {"html": protocell_decision_figure(arc, feas, title=self.config["title"])}


def bioenergetic_provenance_figure(fav, weak, *, title=None) -> str:
    """og-05 Decision view: (left) the energy-provenance trajectory — the useful
    disequilibrium shifts from the external geochemical gradient to internally
    maintained power as the environment declines; (right) gradient dependence — the
    efficient pump survives the collapse, the weak pump does not (Sojo). ``fav`` /
    ``weak`` are the emitter row lists for the two arms."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from ..composites.bioenergetic_internalization import bioenergetic_internalization

    def col(rows, k):
        return [float(r.get(k, 0.0)) for r in rows]

    t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(fav)],
                            bioenergetic_internalization)
    wt, _ = S.real_time([r.get("global_time", i) for i, r in enumerate(weak)],
                        bioenergetic_internalization)
    ext = col(fav, "external_power")
    intl = col(fav, "internal_power")
    frac_ext = [e / (e + n) if (e + n) > 1e-30 else 0.0 for e, n in zip(ext, intl)]
    frac_int = [1.0 - f if (e + n) > 1e-30 else 0.0 for f, e, n in zip(frac_ext, ext, intl)]
    vext = col(fav, "electric_potential")

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.2,
                        specs=[[{"secondary_y": True}, {"secondary_y": False}]],
                        subplot_titles=("Energy provenance: external → internal",
                                        "Gradient dependence (the Sojo constraint)"))
    # --- left: stacked provenance fractions + declining gradient ---
    fig.add_trace(go.Scatter(x=t, y=[f * 100 for f in frac_ext], mode="lines", name="external gradient",
                             stackgroup="prov", line=dict(width=0.5, color=_AMBER),
                             fillcolor="rgba(217,119,6,0.55)"), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=[f * 100 for f in frac_int], mode="lines", name="internally maintained",
                             stackgroup="prov", line=dict(width=0.5, color=_TEAL),
                             fillcolor="rgba(13,148,136,0.55)"), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=vext, mode="lines", name="external pmf (V)",
                             line=dict(color=_INK, width=2, dash="dot")), row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="share of useful free energy (%)", range=[0, 100], row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="external pmf (V)", row=1, col=1, secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text=tlabel, row=1, col=1)
    # --- right: survivors, efficient vs weak pump ---
    fig.add_trace(go.Scatter(x=t, y=col(fav, "survivors"), mode="lines", name="efficient pump",
                             line=dict(color=_TEAL, width=3)), row=1, col=2)
    fig.add_trace(go.Scatter(x=wt,
                             y=col(weak, "survivors"), mode="lines", name="weak-pump control",
                             line=dict(color=_RUST, width=2.5, dash="dash")), row=1, col=2)
    fig.add_trace(go.Scatter(x=t, y=col(fav, "internalization"), mode="lines", name="internalization",
                             line=dict(color=_SLATE, width=1.5, dash="dot")), row=1, col=2)
    fig.update_yaxes(title_text="surviving population fraction", range=[-0.02, 1.05], row=1, col=2)
    fig.update_xaxes(title_text=tlabel, row=1, col=2)

    fig.update_layout(**S.base_layout(
        height=450, width=960, margin=dict(t=48, b=60, l=70, r=60),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center", font=dict(size=9))))
    cap = ("Modeled. As the geochemical gradient collapses, the useful free energy shifts from external "
           "(amber) to internally pumped (teal) &mdash; an additive budget in consistent units against a "
           "matched weak-pump control. The efficient pump internalizes and the modeled lineage persists; "
           "the weak pump cannot beat its maintenance cost and collapses &mdash; the gradient becomes a "
           "resource, not the scaffold. This is persistence of modeled replicators, not a demonstration of "
           "biochemical energy autonomy.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Energy provenance — external to internal"),
                   phase="Campaign V", view="Mechanism", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class BioenergeticProvenanceViz(Visualization):
    """og-05 Decision view: the energy-provenance trajectory (external → internal) +
    the gradient-dependence of survival (efficient vs weak pump), from the real
    replicator composite run under a declining external gradient."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign V — the organism begins to own its energy"},
        "n_steps": {"_type": "integer", "_default": 40},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from process_bigraph import Composite, gather_emitter_results

        from ..composites.bioenergetic_internalization import bioenergetic_internalization
        from ..core import build_core
        core = build_core()
        n = int(self.config["n_steps"])

        def run(eff):
            sim = Composite({"state": bioenergetic_internalization(core, catalyst_efficiency=eff)}, core=core)
            sim.run(n)
            return gather_emitter_results(sim)[("emitter",)]

        return {"html": bioenergetic_provenance_figure(run(1.0), run(0.3), title=self.config["title"])}


class CarbonFixationPhaseMap(Visualization):
    """og-01 Decision view: the carbon-fixation landscape over (vent pH × H₂),
    favourable vs the Tutolo gradient collapse, rendered from a parameter sweep of
    the real eQuilibrator+FiPy composite in its open-flow regime.

    Renders from a persisted grid (``grid_json`` path in config) when present;
    otherwise computes a modest grid live (at canonical-run time → cached once in
    viz.json)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign I — the carbon-fixation landscape"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 10},
        "n_steps": {"_type": "integer", "_default": 40},
        "dilution_rate": {"_type": "float", "_default": 2.0},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import carbon_fixation_phase_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                blobs = json.load(f)
            fav = _ResultView(*_grid_from_json(blobs["favourable"]))
            tut = _ResultView(*_grid_from_json(blobs["tutolo"])) if "tutolo" in blobs else None
        else:
            n = int(self.config["n_grid"])
            kw = dict(ph_vent=(7.0, 11.0, n), h2=(1.0e-4, 2.0e-2, n),
                      dilution_rate=float(self.config["dilution_rate"]),
                      n_steps=int(self.config["n_steps"]), n_jobs=1)
            fav = carbon_fixation_phase_map(gradient_efficiency=1.0, **kw)
            tut = carbon_fixation_phase_map(gradient_efficiency=0.1, **kw)
        return {"html": carbon_fixation_phase_figure(fav, tut, title=self.config["title"])}


def _tree_layout(nodes, *, max_nodes=520):
    """Lay out a lineage tree for plotting: x = birth generation, y assigned so
    children sit near their parent. Subsamples to ``max_nodes`` (keeping whole
    generations from the root) so a 10k-node tree stays renderable. Returns
    ``(xs, ys, phis, edge_x, edge_y)``."""
    if not nodes:
        return [], [], [], [], []
    by_gen: dict = {}
    for n in nodes:
        by_gen.setdefault(int(n["gen"]), []).append(n)
    gens = sorted(by_gen)
    # Keep early generations whole; stop once we'd exceed the node budget.
    kept, total = {}, 0
    for g in gens:
        rows = by_gen[g]
        if total + len(rows) > max_nodes and kept:
            break
        for n in rows:
            kept[int(n["id"])] = n
        total += len(rows)
    # y-position: order siblings next to each other by walking generations in id order.
    pos: dict = {}
    for g in sorted({int(n["gen"]) for n in kept.values()}):
        rows = sorted((n for n in kept.values() if int(n["gen"]) == g), key=lambda n: int(n["id"]))
        for k, n in enumerate(rows):
            # anchor near the parent's y when the parent is kept, else spread evenly
            par = kept.get(int(n["parent"]))
            base = pos[int(par["id"])][1] if par else (k - len(rows) / 2.0)
            pos[int(n["id"])] = (g, base + (k - len(rows) / 2.0) * 0.04)
    xs = [pos[i][0] for i in kept]
    ys = [pos[i][1] for i in kept]
    phis = [float(kept[i]["phi"]) for i in kept]
    edge_x: list = []
    edge_y: list = []
    for i, n in kept.items():
        p = kept.get(int(n["parent"]))
        if p is not None:
            edge_x += [pos[int(p["id"])][0], pos[i][0], None]
            edge_y += [pos[int(p["id"])][1], pos[i][1], None]
    return xs, ys, phis, edge_x, edge_y


def heredity_lineage_figure(tree, herit_pairs, phase, *, title=None) -> str:
    """og-06 three-view figure. **World** (left): the agent-based lineage TREE of the
    RNA-like template module, every node a real individual coloured by its chemical
    phenotype function φ. **Mechanism** (top-right): parent↔offspring φ — a tight
    diagonal for a heritable module vs the flat cloud of the non-heritable control
    (the realized-heritability signature). **Decision** (bottom-right): the Eigen
    error-threshold phase map over (per-site fidelity × template length) — functional
    persistence with the pass/fail boundary, and the length-independent compositional /
    hybrid modules marked where a long template already fails.

    ``tree`` = {module, nodes}; ``herit_pairs`` = {module: [[parent_phi, off_phi], …]};
    ``phase`` = the heredity_error_threshold_map SweepResult (or a duck-typed view)."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=2, cols=2, column_widths=[0.52, 0.48], row_heights=[0.5, 0.5],
        horizontal_spacing=0.1, vertical_spacing=0.14,
        specs=[[{"rowspan": 2}, {}], [None, {}]],
        subplot_titles=("World — the lineage tree (nodes coloured by function φ)",
                        "Mechanism — heredity: offspring vs parent φ",
                        "Decision — the Eigen error threshold (persistence)"))

    # --- World: the lineage tree ------------------------------------------------
    xs, ys, phis, ex, ey = _tree_layout(tree.get("nodes") or [])
    fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", line=dict(color="rgba(100,116,139,0.28)", width=0.6),
                             hoverinfo="skip", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers", showlegend=False,
        marker=dict(size=5, color=phis, colorscale="Viridis", cmin=0, cmax=1,
                    colorbar=dict(title="φ", len=0.45, y=0.78, x=0.46, thickness=10)),
        hovertemplate="gen %{x}<br>φ=%{marker.color:.2f}<extra></extra>"), row=1, col=1)
    fig.update_xaxes(title_text="generation", row=1, col=1)
    fig.update_yaxes(showticklabels=False, row=1, col=1)

    # --- Mechanism: parent↔offspring φ (heritability) ---------------------------
    colmap = {"template": _TEAL, "compositional": _AMBER, "non-heritable": _RUST, "hybrid": "#7c3aed"}
    for mod, pairs in (herit_pairs or {}).items():
        if not pairs:
            continue
        arr = np.asarray(pairs, float)
        idx = np.random.default_rng(0).choice(len(arr), size=min(len(arr), 600), replace=False)
        sl = float(np.polyfit(arr[:, 0], arr[:, 1], 1)[0]) if arr[:, 0].std() > 1e-6 else float("nan")
        fig.add_trace(go.Scatter(
            x=arr[idx, 0], y=arr[idx, 1], mode="markers",
            name=f"{mod} (h={sl:.2f})", legendgroup=mod,
            marker=dict(size=4, color=colmap.get(mod, _SLATE), opacity=0.45)), row=1, col=2)
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=_INK, width=1, dash="dot"),
                             name="h=1 (perfect)", showlegend=True), row=1, col=2)
    fig.update_xaxes(title_text="parent φ", range=[0, 1], row=1, col=2)
    fig.update_yaxes(title_text="offspring φ", range=[0, 1], row=1, col=2)

    # --- Decision: the error-threshold persistence map --------------------------
    f_axis = np.asarray(phase.axes["per_site_fidelity"], float)
    l_axis = np.asarray(phase.axes["length"], float)
    Z = np.asarray(phase.surfaces["persistence"], float)   # shape (fidelity, length)
    thr = float(phase.meta.get("persist_threshold", 0.35))
    fig.add_trace(go.Heatmap(
        x=l_axis, y=f_axis, z=Z, colorscale="Viridis", zmin=0, zmax=float(max(Z.max(), thr * 2)),
        colorbar=dict(title="persist.", len=0.45, y=0.22, x=1.0, thickness=10),
        hovertemplate="L=%{x:.0f}, f=%{y:.3f}<br>persistence=%{z:.2f}<extra></extra>"), row=2, col=2)
    # the pass/fail boundary (persistence == threshold)
    fig.add_trace(go.Contour(
        x=l_axis, y=f_axis, z=Z, showscale=False, contours=dict(start=thr, end=thr, size=1,
            coloring="none"), line=dict(color="#f8fafc", width=2.2),
        hoverinfo="skip"), row=2, col=2)
    # non-template modules: horizontal bands (length-independent) where they persist
    refs = phase.meta.get("reference_modules") or {}
    for mod, rec in refs.items():
        if mod == "non-heritable" or (rec.get("persistence", 0) <= thr):
            continue
        fig.add_trace(go.Scatter(
            x=[l_axis.min(), l_axis.max()], y=[f_axis.min(), f_axis.min()],
            mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False), row=2, col=2)
        fig.add_annotation(x=l_axis.max(), y=f_axis.min() + 0.004, xref="x3", yref="y3",
                           text=f"{mod}: persists at any length", showarrow=False,
                           font=dict(size=9, color=colmap.get(mod, _SLATE)), xanchor="right")
    fig.update_xaxes(title_text="template length (sites)", row=2, col=2)
    fig.update_yaxes(title_text="per-site fidelity", row=2, col=2)

    fig.update_layout(**S.base_layout(
        height=620, margin=dict(l=60, r=70, t=50, b=55),
        legend=dict(orientation="h", y=1.02, x=0.56, font=dict(size=10))))
    cap = ("Across simulated generations, offspring chemical state retains parent-state information in the "
           "heritable regime relative to a randomized-inheritance control. These are ACTUAL sampled "
           "lineages from the agent-based model, not a decorative schematic. <b>World</b>: the real lineage "
           "tree, each node an individual coloured by its chemical phenotype φ (colour encodes φ, not an "
           "arbitrary line style); tree edges trace parent→offspring descent. <b>Mechanism</b>: offspring φ "
           "vs parent φ, with <b>h</b> = the ordinary-least-squares slope of offspring φ regressed on "
           "parent φ (realized heritability): h ≈ 1 is faithful inheritance, h ≈ 0 is none, and <b>h &gt; 1 "
           "does NOT mean more-than-perfect inheritance</b> — it is slope inflation from selection plus "
           "finite-sample noise when parent φ has little spread, and should be read as 'strongly heritable, "
           "slope poorly constrained'. The <b>non-heritable control randomizes inheritance</b> (offspring φ "
           "drawn independently of the parent) — the required control for the parent-state-retention claim: "
           "it collapses to a flat cloud (h ≈ 0). <b>Decision</b>: the Eigen error-threshold map; "
           "compositional / hybrid heredity persist at ANY length, so heredity need not presume a long, "
           "high-fidelity template.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Heredity as an inherited lineage (sampled lineages, not a schematic)"),
                   phase="Campaign VI", view="Decision", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1100)


class HeredityLineageTree(Visualization):
    """og-06 Decision view: the agent-based heredity lineage. Runs the real lineage
    model live (template tree + the non-heritable control for heritability) and a
    modest error-threshold phase map, rendered once into viz.json. Loads a persisted
    grid from ``grid_json`` when present (fast)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign VI — heredity as an inherited lineage"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 9},
        "n_gen": {"_type": "integer", "_default": 40},
        "tree_capacity": {"_type": "integer", "_default": 36},
        "tree_n_gen": {"_type": "integer", "_default": 15},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..heredity.lineage import simulate_lineage
        from ..phase_maps import heredity_error_threshold_map
        # World tree + Mechanism pairs: a small, readable template tree + the controls.
        tcap = int(self.config["tree_capacity"])
        tgen = int(self.config["tree_n_gen"])
        tree_run = simulate_lineage("template", per_site_fidelity=0.99, length=30,
                                    capacity=tcap, n_gen=tgen, seed=1)
        tree = {"module": "template", "nodes": tree_run["nodes"]}
        herit_pairs = {
            "template": tree_run["po_pairs"],
            "non-heritable": simulate_lineage("non-heritable", length=30, capacity=tcap,
                                              n_gen=tgen, seed=1)["po_pairs"],
        }
        # Decision map: persisted grid if available, else a modest live grid.
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                phase = _ResultView(*_grid_from_json(json.load(f)))
        else:
            n = int(self.config["n_grid"])
            phase = heredity_error_threshold_map(
                per_site_fidelity=(0.90, 0.995, n), length=(6, 44, n),
                n_gen=int(self.config["n_gen"]))
        return {"html": heredity_lineage_figure(tree, herit_pairs, phase,
                                                title=self.config["title"])}


def metacommunity_phase_figure(res, *, parasite=None, replicates=None, title=None) -> str:
    """og-07 Decision view (PRIMARY): the robustness GAIN over an isolated baseline.

    **(1,1)** the metacommunity-robustness landscape over (cross-feeding exchange_rate ×
    inter-compartment diversity) with the emergence boundary (robustness == threshold) —
    the FULL parameter range is shown, including the low-exchange / low-diversity corner
    where robustness never emerges. **(1,2)** the primary claim: the redundancy GAIN
    (connected minus the matched isolated counterfactual) with the LUCA-overlap boundary
    contour overlaid (reported, not targeted). When ``parasite`` and ``replicates`` are
    supplied the figure becomes 2×2 and adds **(2,1)** the parasite regime — robustness
    gain over (exchange_rate × parasite_load), so the heritable-cost axis is explicit —
    and **(2,2)** the replicate variation of the canonical community-vs-best-single
    productivity margin (mean ± s.d. over stochastic seeds). ``res`` carries
    ``robustness`` / ``isolated_robustness`` / ``luca_overlap`` over (exchange × diversity);
    ``parasite`` carries the same over (exchange × parasite_load); ``replicates`` is the
    og-36 ``gate_e_ecology.json`` stochastic block."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    ex = np.asarray(res.axes["exchange_rate"], float)
    div = np.asarray(res.axes["diversity"], float)
    rob = np.asarray(res.surfaces["robustness"], float)              # [exchange, diversity]
    iso = np.asarray(res.surfaces.get("isolated_robustness", np.zeros_like(rob)), float)
    luca = np.asarray(res.surfaces.get("luca_overlap", np.zeros_like(rob)), float)
    gain = rob - iso
    thr = float(res.meta.get("robust_emerge_threshold", 0.5))
    op_ex, op_div = 0.3, 0.75                                        # canonical operating point

    expanded = parasite is not None or replicates is not None
    if expanded:
        fig = make_subplots(
            rows=2, cols=2, horizontal_spacing=0.14, vertical_spacing=0.17,
            subplot_titles=("Robustness (functional redundancy) — full range",
                            "Robustness GAIN over the isolated baseline (connected − isolated)",
                            "Parasite regime — gain over (exchange × parasite load)",
                            "Replicate variation — community vs best single lineage"))
    else:
        fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.13, shared_yaxes=True,
                            subplot_titles=("Robustness (functional redundancy) — full range",
                                            "Robustness GAIN over the isolated baseline"))
    # --- (1,1): robustness landscape + emergence boundary (full range incl. failures) ---
    fig.add_trace(go.Contour(x=div, y=ex, z=rob, colorscale="Viridis", ncontours=14,
                             zmin=0.0, zmax=1.0,
                             colorbar=dict(title="robustness<br>(redundancy)", len=0.43 if expanded else 0.9,
                                           x=0.44, y=0.79 if expanded else 0.5),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=1)
    fig.add_trace(go.Contour(x=div, y=ex, z=rob, showscale=False,
                             contours=dict(start=thr, end=thr, coloring="lines"),
                             line=dict(color="#f8fafc", width=2.4, dash="dash"),
                             hoverinfo="skip"), row=1, col=1)
    # --- (1,2): the connected-vs-isolated redundancy gain (diverging), + LUCA boundary ---
    gmax = max(float(np.nanmax(np.abs(gain))), 0.1)
    fig.add_trace(go.Heatmap(x=div, y=ex, z=gain, colorscale="RdBu", zmid=0.0,
                             zmin=-gmax, zmax=gmax,
                             colorbar=dict(title="robustness<br>gain", len=0.43 if expanded else 0.9,
                                           x=1.0, y=0.79 if expanded else 0.5),
                             hovertemplate="div=%{x:.2f}, exch=%{y:.2f}<br>gain=%{z:.2f}<extra></extra>"), row=1, col=2)
    fig.add_trace(go.Contour(x=div, y=ex, z=luca, showscale=False, ncontours=6,
                             contours=dict(coloring="lines", showlabels=True,
                                           labelfont=dict(size=9, color=_INK)),
                             line=dict(color=_INK, width=1.1), hoverinfo="skip"), row=1, col=2)
    for c in (1, 2):
        fig.add_trace(go.Scatter(x=[op_div], y=[op_ex], mode="markers+text",
                                 text=["operating<br>point"], textposition="top center",
                                 textfont=dict(size=9, color=_INK),
                                 marker=dict(symbol="star", size=14, color=_AMBER,
                                             line=dict(width=1.1, color=_INK)), showlegend=False), row=1, col=c)
        fig.update_xaxes(title_text="inter-compartment diversity", row=1, col=c)
    fig.update_yaxes(title_text="cross-feeding exchange rate", row=1, col=1)

    # --- (2,1): the parasite regime — gain over (exchange × parasite_load) ---
    if parasite is not None:
        pex = np.asarray(parasite.axes["exchange_rate"], float)
        pl = np.asarray(parasite.axes["parasite_load"], float)
        prob = np.asarray(parasite.surfaces["robustness"], float)        # [exchange, parasite_load]
        piso = np.asarray(parasite.surfaces.get("isolated_robustness", np.zeros_like(prob)), float)
        pgain = prob - piso
        pmax = max(float(np.nanmax(np.abs(pgain))), 0.1)
        fig.add_trace(go.Heatmap(x=pl, y=pex, z=pgain, colorscale="RdBu", zmid=0.0,
                                 zmin=-pmax, zmax=pmax,
                                 colorbar=dict(title="robustness<br>gain", len=0.43, x=0.44, y=0.2),
                                 hovertemplate="parasite=%{x:.2f}, exch=%{y:.2f}<br>gain=%{z:.2f}<extra></extra>"),
                      row=2, col=1)
        fig.update_xaxes(title_text="parasite load (heritable drain)", row=2, col=1)
        fig.update_yaxes(title_text="cross-feeding exchange rate", row=2, col=1)

    # --- (2,2): replicate variation of the canonical productivity margin ---
    if replicates is not None:
        sto = replicates.get("stochastic", {}) if isinstance(replicates, dict) else {}
        comm = sto.get("community", {})
        best = sto.get("best_single", {})
        c_mean, c_sd = float(comm.get("mean", 0.0)), float(comm.get("sd", 0.0))
        b_mean, b_sd = float(best.get("mean", 0.0)), float(best.get("sd", 0.0))
        nseeds = int((replicates.get("meta", {}) or {}).get("n_seeds", 0))
        frac_pos = sto.get("frac_seeds_positive")
        ext = comm.get("extinction_frac")
        fig.add_trace(go.Bar(
            x=["community", "best single lineage"], y=[c_mean, b_mean],
            error_y=dict(type="data", array=[c_sd, b_sd], visible=True, color=_INK, thickness=1.4),
            marker_color=[_TEAL, _SLATE], showlegend=False,
            text=[f"{c_mean:.0f}±{c_sd:.0f}", f"{b_mean:.0f}±{b_sd:.0f}"], textposition="outside",
            hovertemplate="%{x}: %{y:.0f}<extra></extra>"), row=2, col=2)
        fig.update_yaxes(title_text=f"cumulative productivity<br>(mean ± s.d., {nseeds} seeds)", row=2, col=2)
        sub = []
        if frac_pos is not None:
            sub.append(f"margin &gt; 0 in {float(frac_pos)*100:.0f}% of seeds")
        if ext is not None:
            sub.append(f"community extinction in {float(ext)*100:.0f}% of seeds")
        if sub:
            fig.add_annotation(x=0.5, y=1.02, xref="x4 domain", yref="y4 domain", xanchor="center",
                               yanchor="bottom", showarrow=False, font=dict(size=9, color=_SLATE),
                               text=" · ".join(sub))

    if expanded:
        fig.update_layout(**S.base_layout(height=860, width=980, margin=dict(t=56, b=60, l=75, r=30),
                                          showlegend=False))
    else:
        fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=70, r=20),
                                          showlegend=False))
    cap = ("The primary claim is the robustness GAIN over a matched isolated baseline (top-right, "
           "connected &minus; isolated), <b>not</b> richness: &lsquo;robustness&rsquo; here is functional "
           "redundancy (shared-function coverage), a distinct quantity from species richness, functional "
           "breadth, or parasite load, each of which carries its own units. The modeled transfer is "
           "metabolite / nutrient cross-feeding (with a horizontal-transfer channel), not transmission of "
           "heritable genomes. Gain is positive only in a restricted high-diversity, sufficient-exchange "
           "region (top panels); it erodes as parasite load rises (bottom-left), and across stochastic "
           "replicates the community&rsquo;s productivity margin is positive but more variable than the "
           "best single lineage (bottom-right). Black contours = anaerobic-LUCA reconstruction overlap, a "
           "reported boundary, not a target.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    frame_kw = {"max_width": 1100} if expanded else {}
    return S.frame(inner, title=(title or "Robustness gain over the isolated baseline"),
                   phase="Campaign VII", view="Decision", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", **frame_kw)


class MetacommunityPhaseMap(Visualization):
    """og-07 Decision view: the cross-feeding metacommunity robustness-emergence
    boundary over (exchange_rate × diversity) + the connected-vs-isolated redundancy
    gain, with the anaerobic LUCA-overlap boundary overlaid. Renders from a persisted
    grid (``grid_json``) or computes a modest grid live."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign VII — where cross-feeding robustness emerges"},
        "grid_json": {"_type": "string", "_default": ""},
        "parasite_grid_json": {"_type": "string", "_default": ""},
        "replicates_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 12},
        "n_steps": {"_type": "integer", "_default": 40},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import metacommunity_robustness_phase_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                blob = json.load(f)
            res = _ResultView(*_grid_from_json(blob))
        else:
            n = int(self.config["n_grid"])
            res = metacommunity_robustness_phase_map(
                exchange_rate=(0.02, 0.8, n), diversity=(0.05, 1.0, n),
                n_steps=int(self.config["n_steps"]), n_jobs=1)
        # Optional replot panels: the parasite-load regime grid + the stochastic
        # replicate block (committed artifacts; nothing recomputed here).
        parasite = None
        p_resolved = _resolve_grid_path(str(self.config.get("parasite_grid_json", "") or ""))
        if p_resolved:
            with open(p_resolved) as f:
                parasite = _ResultView(*_grid_from_json(json.load(f)))
        replicates = None
        r_resolved = _resolve_grid_path(str(self.config.get("replicates_json", "") or ""))
        if r_resolved:
            with open(r_resolved) as f:
                replicates = json.load(f)
        return {"html": metacommunity_phase_figure(res, parasite=parasite, replicates=replicates,
                                                    title=self.config["title"])}


class _ResultView:
    """Minimal duck-typed SweepResult for rendering from a persisted grid."""

    def __init__(self, axis_order, axes, surfaces, meta):
        self.axis_order, self.axes, self.surfaces, self.meta = axis_order, axes, surfaces, meta


# ----------------------------------------------------------------------------
# og-08 — escape from the vent : the off-gradient survival frontier
# ----------------------------------------------------------------------------
_OFFGRID_SET_COLORS = {"full": _TEAL, "-pump": _AMBER, "-importer": "#7c3aed",
                       "-heredity": _RUST, "none": _SLATE}


def off_gradient_phase_figure(phase, trajectories, *, title=None) -> str:
    """og-08 Decision view. **Left:** the survival frontier — persistence over
    (environmental-support level × innovation-set); the pass region reaches support→0
    only for the FULL set, and each single knockout is lifted off the gradient (a
    higher minimum support). **Right:** the escape time-course — as geological support
    is withdrawn, the full set persists while every knockout collapses, so the minimum
    robust innovation set is {pump, importer, heredity}. ``phase`` is the
    off_gradient_phase_map SweepResult (or a duck-typed view); ``trajectories`` =
    {set_label: {t, survivors, support}}."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    labels = list(phase.meta.get("innovation_sets")
                  or ["full", "-pump", "-importer", "-heredity", "none"])
    support = np.asarray(phase.axes["support"], float)
    Z = np.asarray(phase.surfaces["persistence"], float)        # shape (support, set)
    frontier = phase.meta.get("frontier") or {}
    thr = float(phase.meta.get("persist_threshold", 0.5))
    set_idx = list(range(len(labels)))

    fig = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.17, column_widths=[0.48, 0.52],
        subplot_titles=("Survival frontier (persistence vs support × innovation set)",
                        "Escape: persistence as geological support is withdrawn"))

    # --- left: the phase map + the survival frontier -----------------------------
    fig.add_trace(go.Heatmap(
        x=set_idx, y=support, z=Z, colorscale="Viridis", zmin=0, zmax=1,
        colorbar=dict(title="persist.", len=0.9, x=0.42, thickness=9,
                      title_font=dict(size=10), tickfont=dict(size=9)),
        hovertemplate="%{customdata}<br>support=%{y:.2f}<br>persistence=%{z:.2f}<extra></extra>",
        customdata=np.array([[labels[j] for j in set_idx] for _ in support])), row=1, col=1)
    # the frontier line: minimum support at which each set persists (None → off the top)
    fx, fy = [], []
    for j, lab in enumerate(labels):
        fv = frontier.get(lab)
        fx.append(j)
        fy.append(float(fv) if fv is not None else float(support.max()) + 1.0)
    fig.add_trace(go.Scatter(
        x=fx, y=fy, mode="lines+markers", line=dict(color="#f8fafc", width=2.5, dash="dot"),
        marker=dict(size=11, color="#f8fafc", line=dict(width=1.2, color=_INK)),
        name="survival frontier", showlegend=False,
        hovertemplate="%{text}: min support %{y:.2f}<extra></extra>",
        text=labels), row=1, col=1)
    # mark the full set reaching support→0 (autonomy)
    if frontier.get(labels[0]) is not None and float(frontier[labels[0]]) <= support.min() + 1e-9:
        fig.add_annotation(x=0, y=support.min(), text="autonomous<br>(persists to 0)", showarrow=True,
                           arrowhead=2, ax=38, ay=-28, font=dict(size=9, color=_TEAL), row=1, col=1)
    fig.update_xaxes(tickmode="array", tickvals=set_idx, ticktext=labels,
                     title_text="innovation set", row=1, col=1)
    fig.update_yaxes(title_text="environmental support (1 = vent, 0 = off-gradient)", row=1, col=1)

    # --- right: the escape time-course -------------------------------------------
    for lab in labels:
        tr = (trajectories or {}).get(lab)
        if not tr:
            continue
        fig.add_trace(go.Scatter(
            x=tr["t"], y=tr["survivors"], mode="lines", name=lab,
            line=dict(color=_OFFGRID_SET_COLORS.get(lab, _SLATE),
                      width=3 if lab == "full" else 2,
                      dash="solid" if lab == "full" else "dash")), row=1, col=2)
    any_tr = next((t for t in (trajectories or {}).values() if t), None)
    if any_tr:
        fig.add_trace(go.Scatter(
            x=any_tr["t"], y=any_tr["support"], mode="lines", name="support (withdrawn)",
            line=dict(color=_INK, width=1.5, dash="dot"), opacity=0.5), row=1, col=2)
    fig.add_hline(y=thr, line=dict(color=_SLATE, width=1, dash="dot"), row=1, col=2)
    fig.update_xaxes(title_text="time (support withdrawn over the run)", row=1, col=2)
    fig.update_yaxes(title_text="surviving fraction", range=[-0.03, 1.05], row=1, col=2)

    fig.update_layout(**S.base_layout(
        height=460, width=980, margin=dict(t=48, b=60, l=75, r=20),
        legend=dict(orientation="h", y=-0.2, x=0.74, xanchor="center", font=dict(size=9))))
    cap = ("Endpoint = surviving fraction once geological support is fully withdrawn (support &rarr; 0, "
           f"persistence threshold {thr:.2f}, dotted). Under this controlled withdrawal the FULL innovation "
           "set &mdash; internal pump + resource importer + heredity &mdash; persists longer and to a lower "
           "support floor than each single-component ablation (&minus;pump / &minus;importer / &minus;heredity) "
           "in the modeled system. This is a NECESSITY test of single components: it shows each is advantageous "
           "at the margin, but on its own it CANNOT establish that the three are <i>jointly</i> necessary rather "
           "than merely advantageous &mdash; that question needs the full 2&times;2&times;2 subset lattice "
           "(see the innovation-epistasis figure), where the full set is in fact not jointly sufficient across "
           "model structures.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The survival frontier off the gradient"),
                   phase="Campaign VIII", view="Decision", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class OffGradientPhaseMap(Visualization):
    """og-08 Decision view: the off-gradient survival frontier over (environmental
    support × innovation set) + the escape time-course as support is withdrawn. Renders
    from a persisted grid (``grid_json``) or computes a modest grid live; the knockout
    trajectories are always computed live (cheap, deterministic)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign VIII — the survival frontier off the gradient"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 16},
        "n_steps": {"_type": "integer", "_default": 60},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..autonomy.off_gradient import decline_trajectory
        from ..phase_maps import _INNOVATION_SETS, off_gradient_phase_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                phase = _ResultView(*_grid_from_json(json.load(f)))
        else:
            phase = off_gradient_phase_map(support=(0.0, 1.0, int(self.config["n_grid"])),
                                           n_steps=int(self.config["n_steps"]))
        n = int(self.config["n_steps"])
        trajectories = {label: decline_trajectory(n_steps=n, **flags)
                        for label, flags in _INNOVATION_SETS}
        return {"html": off_gradient_phase_figure(phase, trajectories, title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-adv — adversarial control : vent-specificity of the carbon-fixation gate
# ----------------------------------------------------------------------------
def vent_specificity_figure(res, gate_rows=None, *, title=None) -> str:
    """og-adv Decision view: the vent-specificity of the carbon-fixation gate.

    Left — the og-01 net-carbon-flux gate over (dissolved H₂ × Fe/Ni/S catalyst
    activity); the PASS region is the vent corner, and the generic control (H₂≈0,
    no catalyst) sits far below the gate threshold. Right (when ``gate_rows`` is
    given) — each vent-specific gate's margin log₁₀(value/threshold) for the vent
    vs the generic control: every bar for the generic control is below the gate
    line (rejected), every vent bar above it (passes)."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    h2 = res.axes["h2"]
    cat = res.axes["catalyst_active"]
    thr = float(res.meta.get("gate_threshold", 1.0e-6))
    pf = res.surfaces["peak_flux"]                       # indexed [h2, catalyst]
    z = np.log10(np.clip(pf.T, 1e-15, None))             # z[y=catalyst][x=h2]

    have_bars = bool(gate_rows)
    fig = make_subplots(
        rows=1, cols=2 if have_bars else 1,
        column_widths=[0.5, 0.5] if have_bars else [1.0],
        horizontal_spacing=0.22,
        subplot_titles=(["Carbon-fixation gate over (H₂ × catalyst)",
                         "Every vent-specific gate rejects the control"]
                        if have_bars else ["Carbon-fixation gate over (H₂ × catalyst)"]))

    fig.add_trace(go.Contour(
        x=h2, y=cat, z=z, colorscale="Viridis", ncontours=16,
        colorbar=dict(title=dict(text="log₁₀ peak net C-flux", side="right",
                                 font=dict(size=10)),
                      len=0.9,
                      x=0.42 if have_bars else 1.02,
                      thickness=9 if have_bars else 14,
                      tickfont=dict(size=9)),
        contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
        line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=1)
    # the gate threshold as a bold boundary: pass region is above/right of it.
    fig.add_trace(go.Contour(
        x=h2, y=cat, z=z, showscale=False,
        contours=dict(start=np.log10(thr), end=np.log10(thr), coloring="lines"),
        line=dict(color="#f8fafc", width=2.6, dash="dash"), hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=[float(h2[-1])], y=[float(cat[-1])], mode="markers+text", text=["vent<br>(passes)"],
        textposition="bottom left", textfont=dict(size=10, color=_INK),
        marker=dict(symbol="star", size=15, color=_AMBER, line=dict(width=1.2, color=_INK)),
        showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=[float(h2[0])], y=[float(cat[0])], mode="markers+text",
        text=["generic control<br>(rejected)"], textposition="top right",
        textfont=dict(size=10, color=_RUST),
        marker=dict(symbol="x", size=13, color=_RUST, line=dict(width=1.2, color=_INK)),
        showlegend=False), row=1, col=1)
    fig.update_xaxes(type="log", title_text="dissolved H₂ (M)", row=1, col=1)
    fig.update_yaxes(title_text="Fe/Ni/S catalyst activity", row=1, col=1)

    if have_bars:
        labels = [g["label"] for g in gate_rows]
        m_vent = [float(np.log10(max(g["vent"], 1e-300) / g["threshold"])) for g in gate_rows]
        m_ctrl = [float(np.log10(max(g["generic"], 1e-300) / g["threshold"])) for g in gate_rows]
        fig.add_trace(go.Bar(y=labels, x=m_vent, orientation="h", name="vent",
                             marker_color=_TEAL), row=1, col=2)
        fig.add_trace(go.Bar(y=labels, x=m_ctrl, orientation="h", name="generic control",
                             marker_color=_RUST), row=1, col=2)
        fig.add_vline(x=0.0, line=dict(color=_INK, width=1.6), row=1, col=2)
        fig.update_xaxes(title_text="gate margin  log₁₀(value / threshold)", row=1, col=2)
        fig.update_layout(barmode="group", legend=dict(orientation="h", y=1.12, x=0.72))

    fig.update_layout(**S.base_layout(
        height=470, width=980 if have_bars else 560, margin=dict(t=48, b=60, l=80, r=30),
        showlegend=have_bars,
        legend=dict(orientation="h", y=1.12, x=0.72)))
    cap = ("Carbon-fixation gate margins depend jointly on dissolved-H₂ availability and Fe/Ni/S catalyst "
           "activity; the generic-control condition fails the prespecified threshold everywhere in the "
           "evaluated range (the full range is shown, including the failing low-H₂ / no-catalyst corner). "
           "<b>Inferential limit:</b> this all-negative &lsquo;generic&rsquo; control removes H₂, the Fe/Ni/S "
           "catalyst AND the pore gradient all at once, so a single lumped failure is NOT evidence that the "
           "vent is specifically required &mdash; it cannot attribute the failure to any one ingredient. "
           "Vent-specificity therefore remains a bounded, hedged claim until a proper factorial ablation "
           "(H₂ on/off × Fe/Ni/S on/off × pore-gradient on/off, with effect sizes and interactions) is run; "
           "the present grid varies only two of these and lumps the rest into one corner.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Vent-specificity of the gates"),
                   phase="Adversarial control", view="Decision", tier="null_control",
                   caption_text=cap, caption_prefix="How to read", tone="caution")


class VentSpecificityMap(Visualization):
    """og-adv Decision view: vent-specificity of the carbon-fixation gate over
    (dissolved H₂ × Fe/Ni/S catalyst), plus the per-gate rejection of the generic
    control. Renders from a persisted grid (``grid_json`` — whose meta carries the
    per-gate ``gate_rows``) or computes a modest grid live (contour only)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Adversarial control — vent-specificity of the gates"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 12},
        "n_steps": {"_type": "integer", "_default": 40},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import vent_specificity_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        gate_rows = None
        if resolved:
            with open(resolved) as f:
                blob = json.load(f)
            res = _ResultView(*_grid_from_json(blob))
            gate_rows = res.meta.get("gate_rows")
        else:
            n = int(self.config["n_grid"])
            res = vent_specificity_map(h2=(1.0e-9, 2.0e-2, n), catalyst_active=(0.0, 1.0, n),
                                       n_steps=int(self.config["n_steps"]), n_jobs=1)
        return {"html": vent_specificity_figure(res, gate_rows=gate_rows, title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-res — nitrogen as a limiting resource : the C:N supply-ratio landscape
# ----------------------------------------------------------------------------
def nitrogen_assimilation_phase_figure(res, *, title=None) -> str:
    """og-res Decision view: does reduced nitrogen keep pace with carbon? **Left**: the
    C:N supply-ratio landscape over (nitrate supply x FeS activity) with the keeps-pace
    boundary (C:N == threshold) and the favourable operating point; reduced N keeps pace
    only where BOTH the nitrate feed is sufficient AND the FeS catalyst is active.
    **Right**: the sustained ammonium-production rate, with the carbon-demand-matched
    contour (production = c_demand / cn_target) overlaid — the same keeps-pace frontier
    read on the supply side. ``res`` is a SweepResult / grid view with ``cn_ratio``,
    ``keeps_pace``, ``nh4_production`` and ``nh4_pool`` surfaces."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    supply = np.asarray(res.axes["no3_supply"], float)
    fes = np.asarray(res.axes["fes_activity"], float)
    cn = np.asarray(res.surfaces["cn_ratio"], float)                 # [supply, fes]
    prod = np.asarray(res.surfaces.get("nh4_production", np.zeros_like(cn)), float)
    thr = float(res.meta.get("cn_keeps_pace_threshold", 8.0))
    c_demand = float((res.meta.get("fixed") or {}).get("c_demand", 1.0e-4))
    cn_target = float((res.meta.get("fixed") or {}).get("cn_target", 5.0))
    # carbon-demand-matched production (mol/s): where reduced-N supply just meets demand.
    prod_match = c_demand / max(cn_target, 1e-6)
    op_supply, op_fes = 2.0e-5, 1.0                                  # favourable operating point

    z_cn = np.log10(np.clip(cn, 1.0, None))                          # log — spans decades
    z_prod = np.log10(np.clip(prod * 1e6, 1e-3, None))               # umol/s, log

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.13, shared_yaxes=True,
                        subplot_titles=("C:N supply ratio (does reduced N keep pace?)",
                                        "Sustained ammonium production (umol/s)"))
    # --- left: C:N landscape + the keeps-pace boundary ---
    fig.add_trace(go.Contour(x=fes, y=supply, z=z_cn, colorscale="Viridis_r", ncontours=16,
                             colorbar=dict(title="log10<br>C:N", len=0.9, x=0.44),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=1)
    fig.add_trace(go.Contour(x=fes, y=supply, z=cn, showscale=False,
                             contours=dict(start=thr, end=thr, coloring="lines"),
                             line=dict(color="#f8fafc", width=2.6, dash="dash"),
                             hoverinfo="skip"), row=1, col=1)
    # --- right: reduced-N production + the carbon-demand-matched frontier ---
    fig.add_trace(go.Contour(x=fes, y=supply, z=z_prod, colorscale="Inferno", ncontours=16, showscale=True,
                             colorbar=dict(title="log10<br>umol/s", len=0.9),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=2)
    fig.add_trace(go.Contour(x=fes, y=supply, z=prod, showscale=False,
                             contours=dict(start=prod_match, end=prod_match, coloring="lines"),
                             line=dict(color="#f8fafc", width=2.4, dash="dash"),
                             hoverinfo="skip"), row=1, col=2)
    for c in (1, 2):
        fig.add_trace(go.Scatter(x=[op_fes], y=[op_supply], mode="markers+text",
                                 text=["operating point"], textposition="middle left",
                                 textfont=dict(size=9, color=_INK),
                                 marker=dict(symbol="star", size=14, color=_AMBER,
                                             line=dict(width=1.1, color=_INK)), showlegend=False), row=1, col=c)
        fig.update_xaxes(title_text="FeS catalyst activity", row=1, col=c)
    fig.update_yaxes(type="log", title_text="nitrate supply (M/s)", row=1, col=1)

    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=75, r=20),
                                      showlegend=False))
    cap = ("Modeled. Reduced nitrogen keeps pace with carbon only where the (supplied) nitrate feed is "
           "sufficient AND the FeS catalyst is active (dashed = keeps-pace boundary, "
           f"C:N = {thr:.0f}). Above the feed/activity frontier the C:N supply ratio blows up and nitrogen "
           "&mdash; not carbon or energy &mdash; becomes limiting first. The no-FeS / no-H2 controls sit "
           "off-scale at zero production. The nitrate feed is a model parameter, not a claim that nitrate "
           "was abundant in the relevant early-Earth setting, and a matched C:N supply ratio is not by "
           "itself sufficient reduced-N flux.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Nitrogen as a limiting resource"),
                   phase="Resource limitation", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class NitrogenAssimilationPhaseMap(Visualization):
    """og-res Decision view: the C:N supply-ratio landscape over (nitrate supply x FeS
    activity) + the sustained ammonium-production surface, with the keeps-pace boundary
    where reduced N meets the carbon-fixation demand. Renders from a persisted grid
    (``grid_json``) or computes a modest grid live."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign I — nitrogen as a limiting resource"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 12},
        "n_steps": {"_type": "integer", "_default": 100},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import nitrogen_assimilation_phase_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                blob = json.load(f)
            res = _ResultView(*_grid_from_json(blob))
        else:
            n = int(self.config["n_grid"])
            res = nitrogen_assimilation_phase_map(
                no3_supply=(2.0e-6, 1.0e-4, n), fes_activity=(0.05, 1.0, n),
                n_steps=int(self.config["n_steps"]), n_jobs=1)
        return {"html": nitrogen_assimilation_phase_figure(res, title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-res-phosphorus — the phosphorus bottleneck : reactive-P availability map
# ----------------------------------------------------------------------------
def phosphorus_availability_figure(res, *, title=None) -> str:
    """og-res-phosphorus Decision view: the reactive-P availability landscape over
    (phosphate source × pore/thermal enrichment). Left: the settled reactive-P pool
    (µM, log) with the net-availability boundary (production = loss) and the carbon
    co-concentration floor overlaid — their intersection is the PASS region (reactive
    P wins AND co-concentrates with carbon). Right: the precipitated (mineral-bound)
    fraction — where phosphate is lost to the sink before it is useful. ``res`` is a
    SweepResult / grid view."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    supply = res.axes["phosphate_supply"]
    enr = res.axes["pore_enrichment"]
    # surfaces indexed [supply, enr] -> Contour wants z[y=supply][x=enr].
    rp = res.surfaces["reactive_pool"] * 1.0e6                 # µM
    net = res.surfaces["net_available"]
    precip = res.surfaces["precipitated_fraction"]
    z_rp = np.log10(np.clip(rp, 1e-4, None))
    floor = float(res.meta.get("carbon_coconc_floor", 10.0))

    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.12,
                        subplot_titles=("Reactive-P available (µM — log)",
                                        "Phosphate lost to the mineral sink (precipitated fraction)"))
    fig.add_trace(go.Contour(x=enr, y=supply, z=z_rp, colorscale="Viridis", ncontours=14,
                             colorbar=dict(title="log₁₀<br>reactive P<br>(µM)", len=0.9, x=0.44),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=1)
    fig.add_trace(go.Contour(x=enr, y=supply, z=precip, colorscale="Inferno_r", ncontours=14,
                             showscale=True, colorbar=dict(title="precipitated<br>fraction", len=0.9),
                             zmin=0.0, zmax=1.0,
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=2)
    # availability boundary (net = 0: reactive-P production = precipitation loss) + the
    # carbon co-concentration floor. The PASS region is to the right of BOTH.
    for c in (1, 2):
        fig.add_trace(go.Contour(x=enr, y=supply, z=net, showscale=False,
                                 contours=dict(start=0, end=0, coloring="lines"),
                                 line=dict(color="#f8fafc", width=2.4, dash="dash"),
                                 hoverinfo="skip"), row=1, col=c)
        fig.add_vline(x=floor, line=dict(color=_AMBER, width=2, dash="dot"), row=1, col=c)
        fig.update_xaxes(title_text="pore / thermal enrichment (×)", row=1, col=c)
    fig.update_yaxes(type="log", title_text="phosphate source (M)", row=1, col=1)

    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=70, r=20),
                                      showlegend=False))
    cap = ("Modeled. Reactive P is available only in a bounded region &mdash; enough pore enrichment that "
           "condensation/activation outpace precipitation. Dashed = availability threshold (production = "
           "loss); dotted amber = the enrichment at which the same og-03 pore co-concentrates carbon. "
           "PASS = right of both; left of the dashed line phosphate precipitates before it is useful. The "
           "condensed/activated-P pathway is a modeled kinetic partition, not demonstrated prebiotic "
           "polyphosphate chemistry.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The phosphorus bottleneck — reactive-P availability landscape"),
                   phase="Resource limitation", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class PhosphorusAvailabilityMap(Visualization):
    """og-res-phosphorus Decision view: the reactive-P availability landscape over
    (phosphate source × pore/thermal enrichment) — the bounded region where the real
    libRoadRunner P-speciation network produces reactive P faster than phosphate
    precipitates AND the pore co-concentrates carbon. Renders from a persisted grid
    (``grid_json``) or computes a modest grid live."""

    config_schema = {
        "title": {"_type": "string", "_default": "The phosphorus bottleneck — reactive-P availability landscape"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 12},
        "n_steps": {"_type": "integer", "_default": 100},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import phosphorus_availability_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                blob = json.load(f)
            inner = blob["phosphorus"] if "phosphorus" in blob else blob
            res = _ResultView(*_grid_from_json(inner))
        else:
            n = int(self.config["n_grid"])
            res = phosphorus_availability_map(phosphate_supply=(1.0e-6, 1.0e-3, n),
                                              pore_enrichment=(1.0, 60.0, n),
                                              n_steps=int(self.config["n_steps"]), n_jobs=1)
        return {"html": phosphorus_availability_figure(res, title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-proto-energetics — an energy currency before modern pumping
# ----------------------------------------------------------------------------
def energy_phase_figure(res, *, title=None) -> str:
    """og-proto-energetics Decision view: the free-energy-capture phase map over
    (geochemical free-energy drive × coupling efficiency). **Left:** the charged
    fraction maintained under load, with the PASS boundary (currency maintained above
    threshold) dashed and the carrier-bond gate (the drive must clear the bond)
    marked. **Right:** the captured stored-work fraction — what share of the
    geochemical free energy becomes transferable usable work. ``res`` is the
    proto_energetics_map SweepResult (or a duck-typed view)."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    drive = np.asarray(res.axes["drive_free_energy"], float)
    eta = np.asarray(res.axes["coupling_efficiency"], float)
    # surfaces indexed [drive, eta]; Contour wants z[y][x] with x=eta, y=drive → as-is.
    charge = np.asarray(res.surfaces["charge_fraction"], float)
    stored = np.asarray(res.surfaces.get("stored_work_fraction", np.zeros_like(charge)), float)
    thr = float(res.meta.get("energy_currency_threshold", 0.25))
    bond = float(res.meta.get("carrier_bond_kjmol", 35.0))
    carrier = str(res.meta.get("carrier", "thioester")).replace("_", " ")
    op_drive, op_eta = 50.0, 0.6                                   # canonical operating point

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.13, shared_yaxes=True,
                        subplot_titles=("Currency maintained under load (charged fraction)",
                                        "Captured as transferable work (stored-work fraction)"))
    # --- left: the charged-fraction landscape + the viability boundary ---
    fig.add_trace(go.Contour(x=eta, y=drive, z=charge, colorscale="Viridis", ncontours=14,
                             zmin=0.0, zmax=max(0.5, float(np.nanmax(charge))),
                             colorbar=dict(title="charged<br>fraction", len=0.9, x=0.44),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=1)
    fig.add_trace(go.Contour(x=eta, y=drive, z=charge, showscale=False,
                             contours=dict(start=thr, end=thr, coloring="lines"),
                             line=dict(color="#f8fafc", width=2.4, dash="dash"),
                             hoverinfo="skip"), row=1, col=1)
    # the thermodynamic gate: below the carrier bond the drive cannot charge it
    fig.add_hline(y=bond, line=dict(color=_RUST, width=1.6, dash="dot"), row=1, col=1)
    fig.add_annotation(x=eta.min(), y=bond, xanchor="left", yanchor="top",
                       text=f"{carrier} bond ({bond:.0f} kJ/mol)",
                       showarrow=False, font=dict(size=9, color=_RUST), row=1, col=1)
    # --- right: the stored-work (capture efficiency) landscape ---
    fig.add_trace(go.Contour(x=eta, y=drive, z=stored, colorscale="Tealgrn", ncontours=14,
                             zmin=0.0, zmax=max(0.5, float(np.nanmax(stored))),
                             colorbar=dict(title="stored-work<br>fraction", len=0.9),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="#0f172a")),
                             line=dict(width=0.4, color="rgba(15,23,42,0.18)")), row=1, col=2)
    fig.add_hline(y=bond, line=dict(color=_RUST, width=1.6, dash="dot"), row=1, col=2)
    for c in (1, 2):
        fig.add_trace(go.Scatter(x=[op_eta], y=[op_drive], mode="markers+text",
                                 text=["operating<br>point"], textposition="top center",
                                 textfont=dict(size=9, color=_INK),
                                 marker=dict(symbol="star", size=14, color=_AMBER,
                                             line=dict(width=1.1, color=_INK)), showlegend=False), row=1, col=c)
        fig.update_xaxes(title_text="coupling efficiency", row=1, col=c)
    fig.update_yaxes(title_text="geochemical free-energy drive ΔG (kJ/mol)", row=1, col=1)

    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=75, r=20),
                                      showlegend=False))
    cap = ("Modeled. A pre-ATP carrier is only a currency where the geochemical drive clears the carrier "
           "bond (red dotted gate) AND the coupling is efficient enough to hold it charged against load + "
           "hydrolysis (dashed = viability boundary). The amber star is the canonical operating point "
           "(final charged fraction ~0.39; ~47% of tapped free energy captured as transferable work by a "
           "closed destination ledger); the surrounding field is the SWEPT drive × coupling range, so those "
           "point values are specific to that operating point, not universal (charged fraction spans 0 to "
           "~0.6 across the grid). Right: the fraction of geochemical free energy that becomes transferable "
           "usable work &mdash; the rest is dissipated. No-coupling / no-drive controls sit at zero (the "
           "grid-edge ablations).")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Proto-energetics — capturing free energy into a transferable currency"),
                   phase="Proto-energetics", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class ProtoEnergeticsMap(Visualization):
    """og-proto-energetics Decision view: the free-energy-capture phase map over
    (geochemical free-energy drive × coupling efficiency) — the bounded region where a
    transferable energy currency is maintained above threshold under endergonic load,
    with the carrier-bond thermodynamic gate and the captured stored-work fraction.
    Renders from a persisted grid (``grid_json``) or computes a modest grid live."""

    config_schema = {
        "title": {"_type": "string", "_default": "Proto-energetics — capturing free energy into a transferable currency"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 14},
        "n_steps": {"_type": "integer", "_default": 60},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import proto_energetics_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                blob = json.load(f)
            res = _ResultView(*_grid_from_json(blob))
        else:
            n = int(self.config["n_grid"])
            res = proto_energetics_map(drive_free_energy=(15.0, 70.0, n),
                                       coupling_efficiency=(0.05, 1.0, n),
                                       n_steps=int(self.config["n_steps"]), n_jobs=1)
        return {"html": energy_phase_figure(res, title=self.config["title"])}


def energy_provenance_figure(rows, *, title=None) -> str:
    """og-proto-energetics Mechanism view — the energy-provenance panel. (Left) the
    free-energy ledger as stacked SHARES of the input geochemical free energy: the
    fraction captured as transferable currency (delivered work + still stored) vs the
    fraction dissipated (uncoupled drive + discharge inefficiency + hydrolysis), with
    the overall capture efficiency traced. (Right) the cumulative ledger in kJ/liter
    (input, work, stored, dissipated), showing input accounted to machine precision.
    ``rows`` is the favourable-run emitter row list."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from ..composites.proto_energetics import proto_energetics

    def col(k):
        return [float(r.get(k, 0.0)) for r in rows]

    t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)], proto_energetics)
    inp = col("energy_input"); work = col("energy_work")
    stored = col("energy_stored"); diss = col("energy_dissipated")
    cap_frac = [(w + s) / i * 100 if i > 1e-30 else 0.0 for w, s, i in zip(work, stored, inp)]
    diss_frac = [d / i * 100 if i > 1e-30 else 0.0 for d, i in zip(diss, inp)]

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
                        specs=[[{"secondary_y": True}, {"secondary_y": False}]],
                        subplot_titles=("Where the geochemical free energy goes",
                                        "The free-energy ledger (kJ/liter)"))
    # --- left: stacked provenance shares of the input free energy ---
    fig.add_trace(go.Scatter(x=t, y=cap_frac, mode="lines", name="captured as currency",
                             stackgroup="prov", line=dict(width=0.5, color=_TEAL),
                             fillcolor="rgba(13,148,136,0.55)"), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=diss_frac, mode="lines", name="dissipated",
                             stackgroup="prov", line=dict(width=0.5, color=_SLATE),
                             fillcolor="rgba(100,116,139,0.45)"), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=col("energy_stored_work_fraction"), mode="lines",
                             name="capture efficiency", line=dict(color=_AMBER, width=2.4, dash="dot")),
                  row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="share of input free energy (%)", range=[0, 100], row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="capture efficiency", range=[0, 1], row=1, col=1, secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text=tlabel, row=1, col=1)
    # --- right: the cumulative ledger ---
    fig.add_trace(go.Scatter(x=t, y=inp, mode="lines", name="input (drive)",
                             line=dict(color=_INK, width=2.6)), row=1, col=2)
    fig.add_trace(go.Scatter(x=t, y=work, mode="lines", name="useful work",
                             line=dict(color=_TEAL, width=2.4)), row=1, col=2)
    fig.add_trace(go.Scatter(x=t, y=stored, mode="lines", name="stored in pool",
                             line=dict(color=_AMBER, width=2.0)), row=1, col=2)
    fig.add_trace(go.Scatter(x=t, y=diss, mode="lines", name="dissipated",
                             line=dict(color=_SLATE, width=2.0, dash="dash")), row=1, col=2)
    fig.update_yaxes(title_text="cumulative free energy (kJ/liter)", row=1, col=2)
    fig.update_xaxes(title_text=tlabel, row=1, col=2)

    fig.update_layout(**S.base_layout(
        height=450, width=960, margin=dict(t=48, b=60, l=70, r=60),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center", font=dict(size=9))))
    cap = ("Modeled, at the canonical operating point. Every kilojoule of tapped geochemical free energy is "
           "accounted: a bounded fraction (~47% here) is captured as transferable currency (teal &mdash; "
           "delivered work plus the pool still charged), the rest dissipated (uncoupled drive, discharge "
           "loss, hydrolysis). Right: input = work + stored + dissipated, held to machine precision &mdash; "
           "free-energy accounting is the stage's conservation invariant. This is energy-currency "
           "bookkeeping, not a demonstration of biochemical energy autonomy.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Proto-energetics — the energy-provenance ledger"),
                   phase="Proto-energetics", view="Mechanism", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class ProtoEnergeticsProvenanceViz(Visualization):
    """og-proto-energetics Mechanism view: the energy-provenance panel — the fraction
    of input geochemical free energy stored as transferable currency vs dissipated,
    plus the conserved cumulative ledger — from the real proto_energetics composite
    run at the favourable operating point."""

    config_schema = {
        "title": {"_type": "string", "_default": "Proto-energetics — the energy-provenance ledger"},
        "n_steps": {"_type": "integer", "_default": 60},
        "drive_free_energy": {"_type": "float", "_default": 50.0},
        "coupling_efficiency": {"_type": "float", "_default": 0.6},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from process_bigraph import Composite, gather_emitter_results

        from ..composites.proto_energetics import proto_energetics
        from ..core import build_core
        core = build_core()
        sim = Composite({"state": proto_energetics(
            core, drive_free_energy=float(self.config["drive_free_energy"]),
            coupling_efficiency=float(self.config["coupling_efficiency"]))}, core=core)
        sim.run(int(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": energy_provenance_figure(rows, title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-growth-division — metabolism → osmotic growth & division : the viable band
# ----------------------------------------------------------------------------
def growth_division_phase_figure(res, *, title=None) -> str:
    """og-growth-division Decision view: the bounded viable growth→division band.
    **Left:** the number of divisions over (network throughput × membrane permeability)
    — chemistry drives net growth to DIVISION only in a bounded band (white dashed =
    the band boundary, divisions == 1). **Right:** the physical-fate regime map — the
    same band sits between STARVATION (too permeable: the product leaks out, the
    osmotic pressure never builds, nothing grows) and LYSIS (too impermeable: the
    pressure spikes past the membrane's burst tension). The operating point (★) is the
    canonical favorable run. ``res`` is a SweepResult / grid view with ``divisions``,
    ``outcome``, ``net_growth`` and ``peak_pressure`` surfaces."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    thr = np.asarray(res.axes["network_throughput"], float)          # y
    perm = np.asarray(res.axes["membrane_permeability"], float)      # x
    div = np.asarray(res.surfaces["divisions"], float)               # [throughput, perm]
    outcome = np.asarray(res.surfaces.get("outcome", np.zeros_like(div)), float)
    log_thr, log_perm = np.log10(thr), np.log10(perm)
    op_thr, op_perm = 1.0e-19, 1.0e-9                                # canonical operating point
    viable_frac = float(res.meta.get("viable_fraction", np.mean(div >= 1.0)))

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.14,
                        subplot_titles=("Divisions over throughput × permeability",
                                        "Physical fate: starve · divide · lyse"))
    # --- left: the division-count landscape + the viable-band boundary ---
    fig.add_trace(go.Heatmap(
        x=log_perm, y=log_thr, z=div, colorscale="Tealgrn", zmin=0.0,
        colorbar=dict(title="divisions", len=0.9, x=0.44),
        hovertemplate="log10 P=%{x:.2f}, log10 J=%{y:.2f}<br>divisions=%{z:.0f}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Contour(
        x=log_perm, y=log_thr, z=div, showscale=False,
        contours=dict(start=1.0, end=1.0, coloring="lines"),
        line=dict(color="#f8fafc", width=2.4, dash="dash"), hoverinfo="skip"), row=1, col=1)
    # --- right: the physical-fate regime map (discrete outcome code) ---
    fate_colorscale = [[0.0, _AMBER], [0.33, _AMBER], [0.34, "#9ca3af"], [0.49, "#9ca3af"],
                       [0.5, _TEAL], [0.74, _TEAL], [0.75, _RUST], [1.0, _RUST]]
    fig.add_trace(go.Heatmap(
        x=log_perm, y=log_thr, z=outcome, colorscale=fate_colorscale, zmin=0.0, zmax=3.0,
        colorbar=dict(title="fate", tickvals=[0.4, 1.1, 1.9, 2.6],
                      ticktext=["starve", "grow", "divide", "lyse"], len=0.9),
        hovertemplate="log10 P=%{x:.2f}, log10 J=%{y:.2f}<br>fate=%{z:.0f}<extra></extra>"), row=1, col=2)
    for c in (1, 2):
        fig.add_trace(go.Scatter(
            x=[np.log10(op_perm)], y=[np.log10(op_thr)], mode="markers+text",
            text=["operating<br>point"], textposition="top center",
            textfont=dict(size=9, color=_INK),
            marker=dict(symbol="star", size=14, color="#fde68a",
                        line=dict(width=1.1, color=_INK)), showlegend=False), row=1, col=c)
        fig.update_xaxes(title_text="log₁₀ membrane permeability (m/s)", row=1, col=c)
    fig.update_yaxes(title_text="log₁₀ network throughput (mol/s)", row=1, col=1)

    fig.update_layout(**S.base_layout(height=460, width=980, margin=dict(t=48, b=62, l=78, r=20),
                                      showlegend=False))
    cap = ("Modeled. A protocell's chemistry changes its physical fate: product accumulation &rarr; osmotic "
           "pressure &rarr; solvent influx &rarr; volume growth &rarr; a MODEL-IMPOSED division rule (a "
           "fission event fired at an osmotic/size threshold, NOT emergent mechanical scission). Sustained "
           f"net growth reaching that DIVISION threshold is a BOUNDED viable band ({viable_frac * 100:.0f}% "
           "of the grid, dashed boundary) &mdash; too permeable starves (the product leaks before the "
           "osmotic pressure can build), too impermeable lyses (the pressure bursts the membrane). A "
           "threshold crossing is not physical reproduction, heredity or autonomy.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Metabolism → growth & division — the viable band"),
                   phase="Growth & division", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class GrowthDivisionMap(Visualization):
    """og-growth-division Decision view: the bounded viable growth→division band over
    (network throughput × membrane permeability) + the physical-fate regime map
    (starve · divide · lyse). Renders from a persisted grid (``grid_json``) or computes
    a modest grid live."""

    config_schema = {
        "title": {"_type": "string", "_default": "Metabolism → growth & division — the viable band"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 14},
        "n_steps": {"_type": "integer", "_default": 100},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import growth_division_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                res = _ResultView(*_grid_from_json(json.load(f)))
        else:
            n = int(self.config["n_grid"])
            res = growth_division_map(
                network_throughput=(1.0e-21, 1.0e-18, n),
                membrane_permeability=(1.0e-10, 1.0e-4, n),
                n_steps=int(self.config["n_steps"]), n_jobs=1)
        return {"html": growth_division_phase_figure(res, title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-00 — vent reactor baseline : the Lost City habitability window + the engine
# ----------------------------------------------------------------------------
def vent_habitability_figure(res, *, title=None) -> str:
    """og-00 Decision view (PRIMARY): the Lost City habitability window over (olivine
    reaction rate × flow velocity). Three panels show the three prespecified habitability
    criteria, each a MODEL OUTPUT tested against a field window: settled outlet
    temperature (40–91 °C), settled outlet pH (9.0–10.8) and the serpentinization H₂
    source flux (> 0). The bold teal contour on every panel is the COMBINED habitability
    PASS boundary (all three criteria met simultaneously); inside it a bounded regime is
    habitable, outside one or more constraints fail. Grey ✕ cells are simulations that
    failed / fell outside PHREEQC validity and are MASKED (not painted as a value); small
    grey dots mark the actual swept parameter samples. ``res`` is the
    vent_habitability_phase_map SweepResult."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    olv = np.asarray(res.axes["olivine_rate"], float)        # y
    flow = np.asarray(res.axes["flow_velocity"], float)      # x (log)
    T = np.asarray(res.surfaces["temperature_C"], float)     # [olivine, flow]
    pH = np.asarray(res.surfaces["pH"], float)
    h2 = np.asarray(res.surfaces.get("h2_flux", np.full_like(T, np.nan)), float)
    hab = np.nan_to_num(np.asarray(res.surfaces["habitable"], float), nan=0.0)
    win = res.meta.get("window", {})
    t_lo, t_hi = win.get("T_C", [40.0, 91.0])
    ph_lo, ph_hi = win.get("pH", [9.0, 10.8])
    op = res.meta.get("operating_point", {})
    op_o = float(op.get("olivine_rate", 0.15)); op_f = float(op.get("flow_velocity", 1.0e-3))

    # MASK failed / out-of-range simulations instead of painting them as extreme real
    # values: a NaN in any settled field means PHREEQC fell outside 0–100 °C validity or
    # the point washed out. Those cells are left blank on the surfaces and overlaid with a
    # grey ✕, so a reader never mistakes a masked failure for a measured extreme.
    failed = ~np.isfinite(T) | ~np.isfinite(pH)
    T_m = np.where(failed, np.nan, T)
    pH_m = np.where(failed, np.nan, pH)
    h2_m = np.where(failed, np.nan, h2)
    # H₂ flux on a log colour scale (positive is the "reducing-power present" criterion).
    h2_pos = np.where(np.isfinite(h2_m) & (h2_m > 0), h2_m, np.nan)
    z_h2 = np.log10(np.clip(h2_pos, 1e-12, None))
    FF, OO = np.meshgrid(flow, olv)                          # sample-grid coordinates
    fx, oy = FF.ravel(), OO.ravel()
    ff_fail, oo_fail = FF[failed], OO[failed]

    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.085,
                        subplot_titles=("Criterion 1 — settled outlet T (°C)<br>window 40–91 °C",
                                        "Criterion 2 — settled outlet pH<br>window 9.0–10.8 (dimensionless)",
                                        "Criterion 3 — serpentinization H₂<br>source flux (mol s⁻¹, log) > 0"))
    # --- panel 1: temperature, window edges ---
    fig.add_trace(go.Contour(x=flow, y=olv, z=T_m, colorscale="Inferno", ncontours=16, connectgaps=False,
                             colorbar=dict(title="outlet T<br>(°C)", len=0.86, x=0.283, thickness=10),
                             contours=dict(showlabels=True, labelfont=dict(size=8, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.25)")), row=1, col=1)
    for edge in (t_lo, t_hi):
        fig.add_trace(go.Contour(x=flow, y=olv, z=T_m, showscale=False, connectgaps=False,
                                 contours=dict(start=edge, end=edge, coloring="lines"),
                                 line=dict(color="#e2e8f0", width=1.6, dash="dot"),
                                 hoverinfo="skip"), row=1, col=1)
    # --- panel 2: pH, window edges ---
    fig.add_trace(go.Contour(x=flow, y=olv, z=pH_m, colorscale="Viridis", ncontours=16, connectgaps=False,
                             colorbar=dict(title="outlet pH<br>(dimensionless)", len=0.86, x=0.638, thickness=10),
                             contours=dict(showlabels=True, labelfont=dict(size=8, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.25)")), row=1, col=2)
    for edge in (ph_lo, ph_hi):
        fig.add_trace(go.Contour(x=flow, y=olv, z=pH_m, showscale=False, connectgaps=False,
                                 contours=dict(start=edge, end=edge, coloring="lines"),
                                 line=dict(color="#e2e8f0", width=1.6, dash="dot"),
                                 hoverinfo="skip"), row=1, col=2)
    # --- panel 3: H₂ source flux (the binding constraint), log colour, >0 criterion ---
    fig.add_trace(go.Contour(x=flow, y=olv, z=z_h2, colorscale="Cividis", ncontours=14, connectgaps=False,
                             colorbar=dict(title="log₁₀ H₂ flux<br>(mol s⁻¹)", len=0.86, x=0.995, thickness=10),
                             contours=dict(showlabels=True, labelfont=dict(size=8, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.25)")), row=1, col=3)

    # combined PASS boundary + swept-sample dots + masked-failure ✕ + baseline ★, all panels.
    for c in (1, 2, 3):
        fig.add_trace(go.Contour(x=flow, y=olv, z=hab, showscale=False,
                                 contours=dict(start=0.5, end=0.5, coloring="lines"),
                                 line=dict(color=_TEAL, width=2.8, dash="dash"),
                                 hoverinfo="skip"), row=1, col=c)
        fig.add_trace(go.Scatter(x=fx, y=oy, mode="markers", marker=dict(symbol="circle",
                                 size=2.6, color="rgba(226,232,240,0.55)"), hoverinfo="skip",
                                 showlegend=False), row=1, col=c)
        if ff_fail.size:
            fig.add_trace(go.Scatter(x=ff_fail.ravel(), y=oo_fail.ravel(), mode="markers",
                                     marker=dict(symbol="x", size=6, color="#94a3b8",
                                                 line=dict(width=1.0, color="#475569")),
                                     name="failed / out-of-range (masked)",
                                     hovertext="simulation failed / outside PHREEQC validity",
                                     hoverinfo="text", showlegend=(c == 1)), row=1, col=c)
        fig.add_trace(go.Scatter(x=[op_f], y=[op_o], mode="markers+text",
                                 text=["baseline<br>(51 °C, pH 9.4)"], textposition="top center",
                                 textfont=dict(size=8, color=_INK),
                                 marker=dict(symbol="star", size=14, color=_AMBER,
                                             line=dict(width=1.2, color=_INK)), showlegend=False), row=1, col=c)
        fig.update_xaxes(type="log", title_text="flow velocity (m/s)", row=1, col=c)
    fig.update_yaxes(title_text="olivine reaction rate (mol/step)", row=1, col=1)

    fig.update_layout(**S.base_layout(
        height=470, width=1180, margin=dict(t=66, b=66, l=66, r=16), showlegend=True,
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=10))))
    cap = ("<b>A bounded olivine-reaction-rate × flow regime simultaneously satisfies prespecified "
           "reactor habitability criteria; outside this region one or more constraints fail.</b> "
           "Measured quantities are the three settled outlet model OUTPUTS &mdash; temperature, pH and "
           "serpentinization H₂ source flux &mdash; each tested against a Lost City field window "
           "(40&ndash;91 °C; pH 9.0&ndash;10.8; H₂ flux &gt; 0). The teal dashed contour is the combined "
           "PASS boundary (all three met); grey ✕ are masked failed/out-of-range simulations, grey dots the "
           "actual swept samples, ★ the baseline operating point. Domain: olivine rate 0.005&ndash;0.4 mol/step "
           "× flow 2&times;10⁻⁴&ndash;3&times;10⁻² m/s. Limit: a geochemical-endmember reactor habitability "
           "map, not a flow-resolved field or an origin-of-life claim; per-parameter uncertainty is reported "
           "separately in the calibration arm.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The Lost City habitability window"),
                   phase="Campaign 0", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class VentHabitabilityMap(Visualization):
    """og-00 Decision view: the Lost City habitability window over (olivine reaction
    rate × flow velocity) — the bounded region where the real PHREEQC + FiPy vent
    settles inside the field T/pH window with a positive H₂ flux. Renders from a
    persisted grid (``grid_json``) or computes a modest grid live (slow — FiPy)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign 0 — the Lost City habitability window"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 12},
        "nx": {"_type": "integer", "_default": 20},
        "n_steps": {"_type": "integer", "_default": 30},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import vent_habitability_phase_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                res = _ResultView(*_grid_from_json(json.load(f)))
        else:
            n = int(self.config["n_grid"])
            res = vent_habitability_phase_map(olivine_rate=(0.005, 0.4, n),
                                              flow_velocity=(2.0e-4, 3.0e-2, n),
                                              nx=int(self.config["nx"]),
                                              n_steps=int(self.config["n_steps"]), n_jobs=1)
        return {"html": vent_habitability_figure(res, title=self.config["title"])}


def vent_engine_figure(rows, *, title=None) -> str:
    """og-00 Mechanism view: the serpentinization engine behind the baseline. **Left:**
    the pH the engine drives — PHREEQC's equilibrium endmember pH_eq (the Ca-OH buffer)
    vs the realized outlet pH after FiPy transport/mixing, with the gap shaded (mixing
    with cold ocean relaxes the realized pH below the full endmember). **Right:** the
    reducing power + alkalinity the engine generates — the dissolved H₂ and alkalinity
    pools building over the run, with the H₂ source flux on the right axis. ``rows`` is
    the baseline run's emitter row list (patched to also emit pH_eq)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from ..composites.vent_reactor import serpentinizing_vent_reactor

    def col(k):
        return [float(r.get(k, 0.0)) for r in rows]

    t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)],
                            serpentinizing_vent_reactor)
    ph_eq = col("pH_eq"); ph = col("pH")
    h2 = col("H2"); alk = col("alkalinity"); h2_flux = col("H2_flux")

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
                        specs=[[{"secondary_y": False}, {"secondary_y": True}]],
                        subplot_titles=("The pH the engine drives (speciation vs realized)",
                                        "Reducing power + alkalinity generated"))
    # --- left: pH_eq vs realized pH, gap shaded ---
    fig.add_trace(go.Scatter(x=t, y=ph_eq, mode="lines", name="PHREEQC endmember pH_eq",
                             line=dict(color=_RUST, width=2.6)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=ph, mode="lines", name="realized outlet pH",
                             line=dict(color=_TEAL, width=3),
                             fill="tonexty", fillcolor="rgba(100,116,139,0.18)"), row=1, col=1)
    fig.add_hrect(y0=9.0, y1=10.8, line_width=0, fillcolor="rgba(13,148,136,0.07)", row=1, col=1)
    fig.add_annotation(x=t[-1], y=10.8, text="Lost City pH window", showarrow=False, yshift=7,
                       xanchor="right", font=dict(size=9, color=_SLATE), row=1, col=1)
    fig.update_yaxes(title_text="pH", row=1, col=1)
    fig.update_xaxes(title_text=tlabel, row=1, col=1)
    # --- right: H2 + alkalinity pools + H2 flux (secondary) ---
    fig.add_trace(go.Scatter(x=t, y=[v * 1e3 for v in h2], mode="lines", name="dissolved H₂ (mM)",
                             line=dict(color=_INK, width=2.6)), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=[v * 1e3 for v in alk], mode="lines", name="alkalinity (mmol/L)",
                             line=dict(color=_AMBER, width=2.4)), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=[v * 1e6 for v in h2_flux], mode="lines", name="H₂ source flux (µmol/s)",
                             line=dict(color=_TEAL, width=2.0, dash="dot")), row=1, col=2, secondary_y=True)
    fig.update_yaxes(title_text="pool (mM / mmol·L⁻¹)", row=1, col=2, secondary_y=False)
    fig.update_yaxes(title_text="H₂ source flux (µmol/s)", row=1, col=2, secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text=tlabel, row=1, col=2)

    fig.update_layout(**S.base_layout(
        height=450, width=960, margin=dict(t=48, b=60, l=70, r=60),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center", font=dict(size=9))))
    cap = ("Peridotite serpentinization is the engine: PHREEQC's Ca-OH endmember drives the pH high (red), "
           "FiPy transport mixes in cold ocean to settle the realized outlet pH just below it (teal &mdash; "
           "the shaded gap is the mixing relaxation), inside the field window. The same reaction delivers a "
           "sustained dissolved-H₂ reducing flux and alkalinity &mdash; the free energy the downstream "
           "campaigns tap.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The serpentinization engine"),
                   phase="Campaign 0", view="Mechanism", tier="reproduction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class VentSerpentinizationEngine(Visualization):
    """og-00 Mechanism view: the serpentinization engine — the PHREEQC endmember pH_eq
    vs the FiPy-realized outlet pH (the mixing gap), and the dissolved H₂ + alkalinity
    the reaction generates — from the real coupled baseline run."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign 0 — the serpentinization engine"},
        "n_steps": {"_type": "integer", "_default": 120},
        "nx": {"_type": "integer", "_default": 40},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from process_bigraph import Composite, gather_emitter_results

        from ..composites.vent_reactor import serpentinizing_vent_reactor
        from ..core import build_core
        core = build_core()
        doc = serpentinizing_vent_reactor(core, nx=int(self.config["nx"]))
        # the baseline emitter does not carry pH_eq — add it (the store exists) so the
        # mechanism panel can show the endmember vs realized-pH gap. Composite untouched.
        doc["emitter"]["config"]["emit"]["pH_eq"] = "float"
        doc["emitter"]["inputs"]["pH_eq"] = ["chem", "pH_eq"]
        sim = Composite({"state": doc}, core=core)
        sim.run(int(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": vent_engine_figure(rows, title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-03 — dilution → localized individuals : the pore-localization phase map
# ----------------------------------------------------------------------------
def localization_figure(res, *, title=None) -> str:
    """og-03 Decision view: the pore-localization landscape over (pore porosity × pore
    length). The GRADED quantity is the accumulation Péclet, not the precise fold.
    **Left:** the reduced-model fold-enrichment the FiPy trap achieves (log), shown as
    a magnitude surface (no fold PASS line — the extreme folds are solver-sensitive).
    **Right:** the accumulation Péclet (advective trapping vs back-diffusion), with the
    localization frontier (Pe ≈ threshold) and the resolvable-Péclet line beyond which
    the reduced column over-extrapolates the resolved FEM. ``res`` is the
    pore_localization_map SweepResult / grid view."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    por = np.asarray(res.axes["porosity"], float)          # y
    L = np.asarray(res.axes["pore_length"], float)         # x (log)
    enr = np.asarray(res.surfaces["enrichment"], float)    # [porosity, pore_length]
    pec = np.asarray(res.surfaces["peclet"], float)
    e_thr = float(res.meta.get("enrichment_threshold", 1.0e6))
    pe_thr = float(res.meta.get("peclet_threshold", 18.0))
    op = res.meta.get("operating_point", {})
    op_p = float(op.get("porosity", 0.3)); op_L = float(op.get("pore_length", 5.0e-3))
    z_enr = np.log10(np.clip(enr, 1.0, None))

    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.12,
                        subplot_titles=("Fold-enrichment of the feed (log — the trap)",
                                        "Accumulation Péclet (trapping vs back-diffusion)"))
    # Resolvable-Péclet line: beyond it the reduced exp(Pe) column over-extrapolates the
    # resolved FEM (spatial-transport cross-check). No fold PASS boundary is drawn.
    pe_resolvable = float(res.meta.get("resolvable_peclet", 13.0))
    # --- left: enrichment magnitude surface (no fold pass-line) ---
    fig.add_trace(go.Contour(x=L, y=por, z=z_enr, colorscale="Viridis", ncontours=16,
                             colorbar=dict(title="log₁₀<br>enrichment<br>(×)", len=0.9, x=0.44),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=1)
    # --- right: Péclet landscape + the localization frontier (the graded quantity) ---
    fig.add_trace(go.Contour(x=L, y=por, z=pec, colorscale="Inferno", ncontours=16, showscale=True,
                             colorbar=dict(title="accumulation<br>Péclet", len=0.9),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=2)
    fig.add_trace(go.Contour(x=L, y=por, z=pec, showscale=False,
                             contours=dict(start=pe_thr, end=pe_thr, coloring="lines"),
                             line=dict(color="#f8fafc", width=2.8, dash="dash"),
                             hoverinfo="skip"), row=1, col=2)
    # resolvable-Péclet line (teal) — resolved below, solver-sensitive above
    fig.add_trace(go.Contour(x=L, y=por, z=pec, showscale=False,
                             contours=dict(start=pe_resolvable, end=pe_resolvable, coloring="lines"),
                             line=dict(color=_TEAL, width=2.2, dash="dot"),
                             hoverinfo="skip"), row=1, col=2)
    for c in (1, 2):
        fig.add_trace(go.Scatter(x=[op_L], y=[op_p], mode="markers+text",
                                 text=["favourable<br>trap"], textposition="top right",
                                 textfont=dict(size=9, color="#f8fafc"),
                                 marker=dict(symbol="star", size=15, color=_AMBER,
                                             line=dict(width=1.2, color="#f8fafc")), showlegend=False), row=1, col=c)
        fig.update_xaxes(type="log", title_text="pore length (m)", row=1, col=c)
    fig.update_yaxes(title_text="pore porosity / openness", row=1, col=1)
    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=72, r=20),
                                      showlegend=False))

    cap = (
        "A bounded pore-length &times; porosity region yields strong concentration enrichment under the "
        "chosen flow and thermal-gradient assumptions. A dilute vent feed localizes where the accumulation "
        f"Péclet crosses the frontier (white dashed, Pe &asymp; {pe_thr:.0f}) &mdash; the <b>graded quantity "
        "is the Péclet, not the precise fold</b>; a long, tight pore traps, an open / short pore washes "
        f"through. The teal dotted line marks the resolvable Péclet (&asymp; {pe_resolvable:.0f}): beyond it "
        "the favourable trap (&starf;) sits in the solver-sensitive region where the reduced column "
        "over-extrapolates the resolved FEM, so localization is robust but the extreme fold is not (see the "
        "supplementary FiPy&harr;FEM solver-sensitivity diagnostic). <b>This is an ENRICHMENT claim only</b> "
        "&mdash; physical concentration of the feed. Whether that enrichment IGNITES the reaction network is "
        "a separate claim, shown in the primary pore-ignition figure and owned by og-network-rescue."
    )
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The pore-localization frontier (keyed on Péclet)"),
                   phase="Campaign III", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="caution")


class PoreLocalizationMap(Visualization):
    """og-03 Decision view: the native pore-localization phase map over (pore porosity
    × pore length) — the bounded region where the real thermophoretic trap concentrates
    the dilute feed above the localization threshold (a metabolizing individual appears).
    Renders from a persisted grid (``grid_json``) or computes a modest grid live."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign III — the pore-localization frontier"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 12},
        "n_steps": {"_type": "integer", "_default": 15},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import pore_localization_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                res = _ResultView(*_grid_from_json(json.load(f)))
        else:
            n = int(self.config["n_grid"])
            res = pore_localization_map(porosity=(0.05, 0.95, n), pore_length=(5.0e-4, 8.0e-3, n),
                                        n_steps=int(self.config["n_steps"]), n_jobs=1)
        return {"html": localization_figure(res, title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-03 — the HONEST enrichment readout: FiPy reduced column vs resolved FEM.
# Replaces the retired ">1e6-fold" convection-enhanced headline. The robust claim
# is that localization occurs and is BOUNDED; the extreme fold is a reduced-model
# exp(Pe) extrapolation the resolved FEM does not confirm past the resolvable Peclet.
# ----------------------------------------------------------------------------
def pore_enrichment_solver_figure(data: dict, *, title: str = "") -> str:
    """og-03 Decision view (honest uncertainty): single-tracer trap enrichment vs
    accumulation Peclet, FiPy's reduced ``exp(Pe)`` column against the resolved
    dolfinx Soret field. Shades the Peclet region where the two solvers agree
    (localization is a resolved result) against the solver-sensitive region where
    FiPy keeps climbing but the resolved field saturates — so the >10^8 Baaske-
    favorable number is a reduced-model extrapolation, not a resolved enrichment."""
    import plotly.graph_objects as go

    trap = data["trap"]
    rows = sorted(trap["rows"], key=lambda r: r["accumulation_peclet"])
    pe = [r["accumulation_peclet"] for r in rows]
    fipy = [r["fipy_enrichment"] for r in rows]
    fem = [r["fenics_enrichment"] for r in rows]
    agree = [bool(r.get("agree_1dex")) for r in rows]
    # Boundary between the agreement and solver-sensitive regions (last Pe that agrees).
    pe_agree = [p for p, a in zip(pe, agree) if a]
    pe_split = (max(pe_agree) + min([p for p, a in zip(pe, agree) if not a] or [max(pe_agree)])) / 2 \
        if pe_agree and not all(agree) else (max(pe) if all(agree) else min(pe))
    fem_sat = fem[-1]

    fig = go.Figure()
    # honest-uncertainty zones
    S.add_zone(fig, min(pe), pe_split, "agree", label="solvers agree (resolved)")
    S.add_zone(fig, pe_split, max(pe) * 1.02, "sensitive", label="solver-sensitive (reduced-model extrapolation)")
    fig.add_trace(go.Scatter(x=pe, y=fipy, mode="lines+markers", name="FiPy  reduced exp(Pe) column",
                             line=dict(color=_AMBER, width=2.6), marker=dict(size=8)))
    fig.add_trace(go.Scatter(x=pe, y=fem, mode="lines+markers", name="dolfinx  resolved Soret field",
                             line=dict(color=_TEAL, width=2.6), marker=dict(size=8)))
    fig.add_hline(y=fem_sat, line=dict(color=_TEAL, width=1, dash="dot"))
    fig.add_annotation(x=max(pe), y=fem_sat, text=f"resolved field saturates ≈ {fem_sat:.0f}×",
                       showarrow=False, yshift=-14, xanchor="right",
                       font=dict(size=10, color=_TEAL, family=S.FONT_STACK))
    # the default Baaske-favorable pore (the strongest-Pe point) — the retired headline
    fig.add_annotation(x=pe[-1], y=fipy[-1], text=f"Baaske-favorable pore<br>reduced column ≈ {fipy[-1]:.0e}×",
                       showarrow=True, arrowhead=2, arrowcolor=_AMBER, ax=-70, ay=-24,
                       font=dict(size=10, color=_AMBER, family=S.FONT_STACK))
    fig.update_yaxes(type="log", title_text="single-tracer enrichment (fold, log)")
    fig.update_xaxes(title_text="accumulation Péclet")
    S.style_axes(fig)
    fig.update_layout(**S.base_layout(height=460, legend=dict(y=-0.2)))

    n_agree, n_total = trap.get("n_agree"), trap.get("n_total")
    cap = (
        "Localization is real and <b>bounded</b>: where the pore is resolvable (low Péclet) FiPy's "
        "reduced <i>exp(Pe)</i> column and the resolved dolfinx Soret field agree to within a decade "
        f"({n_agree} of {n_total} swept pores). Past the resolvable Péclet they diverge &mdash; FiPy keeps "
        "climbing toward the classical &gt;10&#8310;&ndash;10&#8312;-fold trap, while the resolved field "
        f"saturates near {fem_sat:.0f}&times; because a P1 mesh cannot resolve the sub-micron accumulation "
        "layer. The default Baaske-favorable pore sits <i>inside</i> that solver-sensitive region, so the "
        "extreme fold is a <b>reduced-model extrapolation, not a resolved result</b>. Flow-through enrichment "
        "weakens further with Péclet; the classical headline belongs to a closed / recirculating cell."
    )
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Does the trap concentrate an individual? Localization is bounded"),
                   subtitle="single-tracer enrichment — reduced column vs. resolved FEM (solver-structural uncertainty)",
                   phase="Campaign III", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="caution")


class PoreEnrichmentSolverSensitivity(Visualization):
    """og-03 Decision view: the honest single-tracer enrichment readout (FiPy reduced
    column vs. resolved dolfinx field across the pore-length / Peclet sweep). Renders
    from the committed ``spatial-transport-solver-comparison.json`` cross-check."""

    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "comparison_json": {"_type": "string",
                            "_default": "workspace/references/spatial-transport-solver-comparison.json"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        path = _resolve_grid_path(str(self.config.get("comparison_json", "") or ""))
        if not path:
            return {"html": "<p>solver-comparison artifact not found — run "
                            "scripts/compare_spatial_transport.py first.</p>"}
        with open(path) as f:
            data = json.load(f)
        return {"html": pore_enrichment_solver_figure(data, title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-04 — mineral compartments → protocells : the World (compartment + gradient)
# ----------------------------------------------------------------------------
def protocell_boundary_figure(rows, *, title=None) -> str:
    """og-04 World view: the physical compartment and the gradient crossing it, drawn
    from the real protocell run at the operating point. **Left:** a cross-section of the
    vesicle — the membrane boundary (ring) around a lumen, with inward arrows sized by
    the measured ACCESS (gradient import) and the boundary drawn tighter as RETENTION
    rises. **Right:** the radial concentration profile across the boundary — the
    external gradient substrate imported into the lumen (∝ access) and the internal
    product retained inside (∝ retention). ``rows`` is the operating-point emitter
    rows."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    r = rows[-1] if rows else {}
    retention = float(r.get("retention", 0.0))
    access = float(r.get("access", 0.0))
    individ = float(r.get("individuality_access", retention * access))
    viable = float(r.get("viable_compartments", 0.0))

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.14, column_widths=[0.46, 0.54],
                        specs=[[{"type": "xy"}, {"type": "xy"}]],
                        subplot_titles=("The compartment (membrane + lumen)",
                                        "Concentration across the boundary"))
    # --- left: vesicle cross-section ---
    th = np.linspace(0, 2 * np.pi, 200)
    R = 1.0
    wall = 0.06 + 0.12 * retention                       # a tighter wall as retention rises
    fig.add_trace(go.Scatter(x=(R + wall) * np.cos(th), y=(R + wall) * np.sin(th), mode="lines",
                             line=dict(color=_INK, width=2), fill="toself",
                             fillcolor="rgba(30,41,59,0.10)", hoverinfo="skip", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=R * np.cos(th), y=R * np.sin(th), mode="lines",
                             line=dict(color=_TEAL, width=2.4), fill="toself",
                             fillcolor="rgba(13,148,136,0.16)", hoverinfo="skip",
                             name="lumen (retained chemistry)"), row=1, col=1)
    # inward gradient-import arrows, count/length ∝ access
    n_arrow = max(1, int(round(3 + 9 * access)))
    for k in range(n_arrow):
        a = 2 * np.pi * k / n_arrow
        x1, y1 = (R + wall + 0.5) * np.cos(a), (R + wall + 0.5) * np.sin(a)
        x2, y2 = (R - 0.12) * np.cos(a), (R - 0.12) * np.sin(a)
        fig.add_annotation(x=x2, y=y2, ax=x1, ay=y1, xref="x", yref="y", axref="x", ayref="y",
                           showarrow=True, arrowhead=2, arrowwidth=1.6, arrowcolor=_AMBER, row=1, col=1)
    fig.add_annotation(x=0, y=0, text=(f"retention {retention:.2f}<br>access {access:.2f}"
                                       f"<br><b>individuality {individ:.2f}</b>"),
                       showarrow=False, font=dict(size=11, color=_INK), row=1, col=1)
    fig.add_annotation(x=0, y=-(R + wall + 0.45), text="external geochemical gradient",
                       showarrow=False, font=dict(size=9, color=_AMBER), row=1, col=1)
    fig.update_xaxes(visible=False, range=[-(R + wall + 0.7), R + wall + 0.7],
                     scaleanchor="y", scaleratio=1, row=1, col=1)
    fig.update_yaxes(visible=False, range=[-(R + wall + 0.7), R + wall + 0.7], row=1, col=1)
    # --- right: the radial concentration profile across the boundary ---
    x = np.linspace(-2.0, 2.0, 400)                      # radial coordinate (lumen centre = 0)
    edge = R                                             # membrane at |x| = R
    k_sharp = 7.0
    outside = 0.5 * (1 + np.tanh(k_sharp * (np.abs(x) - edge)))   # ~1 in ocean, ~0 in lumen
    inside = 1.0 - outside
    # imported gradient substrate: ~1 in the ocean, falls to the import efficiency
    # (access) inside the lumen — a permeable boundary lets the gradient in.
    substrate = outside + access * inside
    # internal product: held at the retention level inside the lumen, with a small
    # leak tail into the ocean that grows as retention falls.
    product = retention * inside + (1.0 - retention) * 0.4 * outside
    fig.add_trace(go.Scatter(x=x, y=substrate, mode="lines", name="imported gradient substrate",
                             line=dict(color=_AMBER, width=2.8)), row=1, col=2)
    fig.add_trace(go.Scatter(x=x, y=product, mode="lines", name="retained internal product",
                             line=dict(color=_TEAL, width=2.8)), row=1, col=2)
    for xe in (-edge, edge):
        fig.add_vrect(x0=xe - wall, x1=xe + wall, line_width=0, fillcolor="rgba(30,41,59,0.14)", row=1, col=2)
    fig.add_annotation(x=0, y=1.02, text="lumen", showarrow=False, font=dict(size=9, color=_TEAL), row=1, col=2)
    fig.add_annotation(x=1.6, y=1.02, text="ocean", showarrow=False, font=dict(size=9, color=_AMBER), row=1, col=2)
    fig.update_xaxes(title_text="radial position (membrane = shaded)", row=1, col=2)
    fig.update_yaxes(title_text="relative concentration", range=[-0.03, 1.1], row=1, col=2)

    fig.update_layout(**S.base_layout(
        height=440, width=960, margin=dict(t=48, b=56, l=40, r=20),
        legend=dict(orientation="h", y=-0.16, x=0.5, xanchor="center", font=dict(size=9))))
    cap = ("<b>Schematic of the proposed transport tradeoff: an amphiphile boundary must admit geochemical "
           "substrates while retaining internally generated products.</b> The drawn cross-section (ring + "
           "lumen) and the smooth radial concentration profiles are <b>hypothetical illustrations</b> of the "
           "concept, not resolved spatial fields. Only the scalar annotations are modeled quantities from "
           "the phenomenological protocell model at this operating point: retention {:.2f}, access {:.2f}, "
           "individuality = retention &times; access = {:.2f} ({:.0f} viable-compartment units). It depicts "
           "a boundary that would retain WITHOUT isolating — it does not assert physical vesicle "
           "formation.").format(retention, access, individ, viable)
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The compartment and the gradient — a conceptual schematic"),
                   subtitle="SCHEMATIC: hypothetical cross-section + radial profiles, annotated with modeled scalars",
                   phase="Campaign IV", view="World", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="caution")


class ProtocellBoundaryWorld(Visualization):
    """og-04 World view: the physical compartment + the gradient crossing it — a vesicle
    cross-section (membrane + lumen, inward import arrows) and the radial concentration
    profile across the boundary, drawn from the real protocell run at the operating
    point (retention / access / individuality are measured, the cross-section is a
    schematic driven by them)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign IV — the compartment and the gradient"},
        "mix_fraction": {"_type": "float", "_default": 0.4},
        "pH": {"_type": "float", "_default": 9.0},
        "ionic_strength": {"_type": "float", "_default": 0.35},
        "temperature": {"_type": "float", "_default": 318.15},
        "n_steps": {"_type": "integer", "_default": 20},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from process_bigraph import Composite, gather_emitter_results

        from ..composites.mixed_amphiphile_protocell import mixed_amphiphile_protocell
        from ..core import build_core
        core = build_core()
        doc = mixed_amphiphile_protocell(core, mix_fraction=float(self.config["mix_fraction"]),
                                         pH=float(self.config["pH"]),
                                         ionic_strength=float(self.config["ionic_strength"]),
                                         temperature=float(self.config["temperature"]))
        sim = Composite({"state": doc}, core=core)
        sim.run(int(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": protocell_boundary_figure(rows, title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-05 — environmental → internal bioenergetics : the survival phase map
# ----------------------------------------------------------------------------
def bioenergetic_survival_figure(res, *, title=None) -> str:
    """og-05 Decision view: the survival landscape over (pump catalyst efficiency ×
    gradient floor). **Left:** the final surviving fraction after the gradient collapse,
    with the PASS boundary (survivors = 0.5) dashed and the Sojo cost line (minimum pump
    efficiency to internalize) marked — the low-floor / low-efficiency corner is
    extinction. **Right:** the final internalization — WHERE the survivors truly OWN
    their energy (pump-dominated) vs ride the residual external gradient. ``res`` is the
    bioenergetic_survival_map SweepResult / grid view."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    eff = np.asarray(res.axes["catalyst_efficiency"], float)     # x
    floor = np.asarray(res.axes["gradient_floor"], float)        # y
    surv = np.asarray(res.surfaces["survivors"], float).T        # [eff, floor] -> z[y=floor][x=eff]
    intl = np.asarray(res.surfaces["internalization"], float).T
    s_thr = float(res.meta.get("survival_threshold", 0.5))
    i_thr = float(res.meta.get("internalize_threshold", 0.5))
    eff_sojo = float(res.meta.get("sojo_efficiency", 0.3))
    op = res.meta.get("operating_point", {})
    op_e = float(op.get("catalyst_efficiency", 1.0)); op_g = float(op.get("gradient_floor", 0.02))

    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.12,
                        subplot_titles=("Survival after the gradient collapse",
                                        "Owning its energy (internalization)"))
    # --- left: survival landscape + PASS boundary + Sojo cost line ---
    fig.add_trace(go.Contour(x=eff, y=floor, z=surv, colorscale="Tealgrn", ncontours=14,
                             zmin=0.0, zmax=1.0,
                             colorbar=dict(title="surviving<br>fraction", len=0.9, x=0.44),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="#0f172a")),
                             line=dict(width=0.4, color="rgba(15,23,42,0.18)")), row=1, col=1)
    fig.add_trace(go.Contour(x=eff, y=floor, z=surv, showscale=False,
                             contours=dict(start=s_thr, end=s_thr, coloring="lines"),
                             line=dict(color=_INK, width=2.6, dash="dash"),
                             hoverinfo="skip"), row=1, col=1)
    fig.add_vline(x=eff_sojo, line=dict(color=_RUST, width=1.8, dash="dot"), row=1, col=1)
    fig.add_annotation(x=eff_sojo, y=float(floor.max()), xanchor="left", yanchor="top",
                       text=f"  Sojo cost line (η≈{eff_sojo:.2f})", showarrow=False,
                       font=dict(size=9, color=_RUST), row=1, col=1)
    fig.add_annotation(x=float(eff.min()), y=float(floor.min()), xanchor="left", yanchor="bottom",
                       text="extinction", showarrow=False, font=dict(size=10, color=_RUST), row=1, col=1)
    # --- right: internalization landscape + the owns-its-energy boundary ---
    fig.add_trace(go.Contour(x=eff, y=floor, z=intl, colorscale="Viridis", ncontours=14,
                             zmin=0.0, zmax=1.0,
                             colorbar=dict(title="internaliz.<br>(pump frac)", len=0.9),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=2)
    fig.add_trace(go.Contour(x=eff, y=floor, z=intl, showscale=False,
                             contours=dict(start=i_thr, end=i_thr, coloring="lines"),
                             line=dict(color="#f8fafc", width=2.6, dash="dash"),
                             hoverinfo="skip"), row=1, col=2)
    for c in (1, 2):
        fig.add_trace(go.Scatter(x=[op_e], y=[op_g], mode="markers+text",
                                 text=["operating<br>point"], textposition="top center",
                                 textfont=dict(size=9, color=_INK),
                                 marker=dict(symbol="star", size=14, color=_AMBER,
                                             line=dict(width=1.1, color=_INK)), showlegend=False), row=1, col=c)
        fig.update_xaxes(title_text="pump catalyst efficiency η", row=1, col=c)
    fig.update_yaxes(title_text="gradient floor (V)", row=1, col=1)

    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=72, r=20),
                                      showlegend=False))
    cap = ("Modeled. As the external gradient collapses to its floor, a lineage persists either by riding a "
           "floor that never falls too far OR by internalizing &mdash; but internalizing only pays above "
           f"the Sojo cost line (η≈{eff_sojo:.2f}, red). The low-floor / low-efficiency corner (the "
           "effectively no-pump / no-gradient control at the grid edges) goes extinct. Right: only an "
           "efficient pump truly OWNS its energy (white dashed = internalization > 0.5), independent of the "
           "floor. This maps survival of MODELED replicators, not demonstrated biochemical energy autonomy.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Survival off the collapsing gradient"),
                   phase="Campaign V", view="Decision", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class BioenergeticSurvivalMap(Visualization):
    """og-05 Decision view: the survival phase map over (pump catalyst efficiency ×
    gradient floor) — the region where the population survives the gradient collapse,
    with the Sojo cost line, plus the internalization ("owns its energy") surface.
    Renders from a persisted grid (``grid_json``) or computes a modest grid live."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign V — survival off the collapsing gradient"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 14},
        "n_steps": {"_type": "integer", "_default": 40},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..phase_maps import bioenergetic_survival_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                res = _ResultView(*_grid_from_json(json.load(f)))
        else:
            n = int(self.config["n_grid"])
            res = bioenergetic_survival_map(catalyst_efficiency=(0.05, 1.3, n),
                                            gradient_floor=(0.005, 0.35, n),
                                            n_steps=int(self.config["n_steps"]), n_jobs=1)
        return {"html": bioenergetic_survival_figure(res, title=self.config["title"])}




# ============================================================================
# og-07 — ecology before LUCA : the complete three-view (World / Mechanism /
# Decision). Prefix: ecology_ / crossfeeding_.
# ============================================================================
def ecology_metacommunity_figure(world, mech, phase, *, title=None) -> str:
    """og-07 three-view figure. **World** (left): the connected-compartment
    metacommunity — a ring of pore compartments (nodes coloured by functional breadth,
    parasites ringed in red), edges = cross-feeding + horizontal transfer. **Mechanism**
    (top-right): WHY connectivity builds robustness — functional redundancy climbs with
    the cross-feeding exchange rate from the isolated counterfactual floor across the
    emergence threshold, approaching the anaerobic-LUCA overlap boundary (reported, not
    a target). **Decision** (bottom-right): the ``ecology_robustness_map`` phase map over
    (exchange_rate × parasite_load) at the canonical diversity — cross-feeding robustness
    emerges in the well-connected, low-parasite corner (PASS boundary = white dashed).

    ``world`` = {n, pos, edges, breadth, is_parasite, max_breadth}; ``mech`` =
    {exchange, robustness, isolated, luca, connected_val}; ``phase`` = the
    ecology_robustness_parasite_map SweepResult (or a duck-typed view)."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=2, cols=2, column_widths=[0.5, 0.5], row_heights=[0.5, 0.5],
        horizontal_spacing=0.16, vertical_spacing=0.17,
        specs=[[{"rowspan": 2}, {}], [None, {}]],
        subplot_titles=("World — connected metacommunity",
                        "Mechanism — connectivity builds redundancy",
                        "Decision — where robustness emerges"))

    # --- World: the cross-feeding / HGT ring network ---------------------------
    pos = world["pos"]
    ex, ey = [], []
    for i, j in world["edges"]:
        ex += [pos[i][0], pos[j][0], None]
        ey += [pos[i][1], pos[j][1], None]
    fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines",
                             line=dict(color="rgba(100,116,139,0.45)", width=1.1),
                             hoverinfo="skip", showlegend=False), row=1, col=1)
    xs = [p[0] for p in pos]
    ys = [p[1] for p in pos]
    breadth = world["breadth"]
    roles = ["parasite" if p else "cooperator" for p in world["is_parasite"]]
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers", showlegend=False,
        marker=dict(size=[16 + 5 * b for b in breadth], color=breadth, colorscale="Viridis",
                    cmin=0, cmax=max(world["max_breadth"], 1),
                    colorbar=dict(title="functional<br>breadth", len=0.42, y=0.79, x=0.37, thickness=9,
                                  title_font=dict(size=10), tickfont=dict(size=9)),
                    line=dict(width=1.2, color="#ffffff")),
        customdata=np.stack([np.array(roles), np.array(breadth)], axis=-1),
        hovertemplate="compartment %{pointNumber}<br>role: %{customdata[0]}"
                      "<br>breadth: %{customdata[1]} capabilities<extra></extra>"), row=1, col=1)
    # parasites: an open red ring over the drained compartments.
    par_idx = [i for i, p in enumerate(world["is_parasite"]) if p]
    if par_idx:
        fig.add_trace(go.Scatter(
            x=[xs[i] for i in par_idx], y=[ys[i] for i in par_idx], mode="markers",
            marker=dict(symbol="circle-open", size=[22 + 5 * breadth[i] for i in par_idx],
                        color=_RUST, line=dict(width=2.4, color=_RUST)),
            name="parasite", hoverinfo="skip"), row=1, col=1)
        fig.add_annotation(x=0.0, y=-1.32, xref="x", yref="y", showarrow=False,
                           text="red ring = parasite (drains neighbours) · edges = cross-feeding + HGT",
                           font=dict(size=9, color=_SLATE), row=1, col=1)
    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False,
                     range=[-1.45, 1.45], row=1, col=1)
    fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=False,
                     range=[-1.5, 1.4], scaleanchor="x", scaleratio=1, row=1, col=1)

    # --- Mechanism: robustness vs connectivity (exchange rate) -----------------
    exx = np.asarray(mech["exchange"], float)
    rob = np.asarray(mech["robustness"], float)
    iso = float(mech["isolated"])
    luca = float(mech["luca"])
    thr = float(phase.meta.get("robust_emerge_threshold", 0.5))
    fig.add_trace(go.Scatter(x=exx, y=rob, mode="lines+markers", name="connected",
                             line=dict(color=_TEAL, width=3),
                             marker=dict(size=6, color=_TEAL)), row=1, col=2)
    fig.add_hline(y=iso, line=dict(color=_SLATE, width=2, dash="dash"), row=1, col=2)
    fig.add_annotation(x=exx.max(), y=iso, xref="x2", yref="y2", xanchor="right", yanchor="top",
                       text=f"isolated floor ({iso:.2f})", showarrow=False,
                       font=dict(size=9, color=_SLATE))
    fig.add_hline(y=thr, line=dict(color=_INK, width=1, dash="dot"), row=1, col=2)
    fig.add_annotation(x=exx.min(), y=thr, xref="x2", yref="y2", xanchor="left", yanchor="bottom",
                       text=f"emergence ({thr:.1f})", showarrow=False,
                       font=dict(size=9, color=_INK))
    fig.add_hline(y=luca, line=dict(color=_AMBER, width=2, dash="dot"), row=1, col=2)
    fig.add_annotation(x=exx.max(), y=luca, xref="x2", yref="y2", xanchor="right", yanchor="bottom",
                       text=f"LUCA overlap ({luca:.2f}, reported)",
                       showarrow=False, font=dict(size=9, color=_AMBER))
    fig.update_xaxes(title_text="cross-feeding exchange rate (connectivity)", row=1, col=2)
    fig.update_yaxes(title_text="metacommunity robustness", range=[0, 1.02], row=1, col=2)

    # --- Decision: the (exchange × parasite_load) robustness phase map ---------
    e_axis = np.asarray(phase.axes["exchange_rate"], float)
    p_axis = np.asarray(phase.axes["parasite_load"], float)
    Z = np.asarray(phase.surfaces["robustness"], float)        # [exchange, parasite]
    fig.add_trace(go.Contour(
        x=p_axis, y=e_axis, z=Z, colorscale="Viridis", zmin=0.0, zmax=1.0, ncontours=14,
        colorbar=dict(title="robustness<br>(redundancy)", len=0.42, y=0.22, x=1.0, thickness=9,
                      title_font=dict(size=10), tickfont=dict(size=9)),
        contours=dict(showlabels=True, labelfont=dict(size=8, color="white")),
        line=dict(width=0.4, color="rgba(255,255,255,0.3)"),
        hovertemplate="parasite load=%{x:.2f}, exchange=%{y:.2f}<br>robustness=%{z:.2f}<extra></extra>"), row=2, col=2)
    fig.add_trace(go.Contour(
        x=p_axis, y=e_axis, z=Z, showscale=False,
        contours=dict(start=thr, end=thr, coloring="lines"),
        line=dict(color="#f8fafc", width=2.4, dash="dash"), hoverinfo="skip"), row=2, col=2)
    fig.add_trace(go.Scatter(x=[0.0], y=[0.3], mode="markers+text", text=["operating<br>point"],
                             textposition="top right", textfont=dict(size=9, color=_INK),
                             marker=dict(symbol="star", size=14, color=_AMBER,
                                         line=dict(width=1.1, color=_INK)), showlegend=False), row=2, col=2)
    fig.update_xaxes(title_text="parasite load (fraction draining neighbours)", row=2, col=2)
    fig.update_yaxes(title_text="exchange rate", row=2, col=2)

    fig.update_layout(**S.base_layout(height=640, margin=dict(l=40, r=80, t=50, b=60),
                                      showlegend=False))
    cap = ("The one mechanistic comparison that matters here is <b>connected vs disconnected compartments</b> "
           "at MATCHED inter-compartment diversity and equal resource budgets (Mechanism panel): the connected "
           "metacommunity&rsquo;s functional redundancy climbs from the isolated floor across the emergence "
           "threshold as the cross-feeding exchange rate rises. Read the quantities separately &mdash; functional "
           "breadth (World node colour), functional redundancy / robustness (Mechanism &amp; Decision), and "
           "parasite load (Decision axis) are distinct measures with distinct units; robustness is NOT inferred "
           "from richness alone. The modeled transfer is metabolite cross-feeding plus a horizontal channel, not "
           "transmission of heritable genomes. The anaerobic-LUCA overlap is a reported boundary, not a target.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Connected vs disconnected compartments (matched diversity & budgets)"),
                   phase="Campaign VII", view="Mechanism", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1100)


class EcologyMetacommunityThreeView(Visualization):
    """og-07 complete three-view (World network + Mechanism robustness-vs-connectivity
    + Decision robustness phase map). Runs the real cross-feeding metacommunity live for
    the World network and the Mechanism curve (pure-numpy, fast) and loads the persisted
    (exchange × parasite_load) grid (``grid_json``) for the Decision panel, computing a
    modest grid live as a fallback."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign VII — ecology before LUCA"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 12},
        "n_steps": {"_type": "integer", "_default": 40},
        "n_compartments": {"_type": "integer", "_default": 8},
        "diversity": {"_type": "float", "_default": 0.75},
        "parasite_load": {"_type": "float", "_default": 0.25},
        "seed": {"_type": "integer", "_default": 1},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import math

        import numpy as np

        from ..composites.cross_feeding_metacommunity import cross_feeding_metacommunity
        from ..core import build_core
        from ..ecology.metacommunity import CrossFeedingMetacommunityProcess, metacommunity_state
        from ..phase_maps import ecology_robustness_parasite_map
        from process_bigraph import Composite, gather_emitter_results

        core = build_core()
        n_steps = int(self.config["n_steps"])
        n_comp = int(self.config["n_compartments"])
        div = float(self.config["diversity"])
        seed = int(self.config["seed"])

        # --- World: run the real metacommunity process and read its settled state.
        # A visible parasite load so the drained compartments read in the network.
        proc = CrossFeedingMetacommunityProcess(
            config={"n_compartments": n_comp, "exchange_rate": 0.3, "diversity": div,
                    "hgt_rate": 0.1, "seed": seed,
                    "parasite_load": float(self.config["parasite_load"])}, core=core)
        for _ in range(n_steps):
            proc.update({}, 1.0)
        st = metacommunity_state(proc)
        eff = np.asarray(st["eff"], float)
        thr_cov = float(proc.config["coverage_threshold"])
        breadth = [int((eff[i] > thr_cov).sum()) for i in range(eff.shape[0])]
        pos = [(math.cos(2 * math.pi * i / n_comp), math.sin(2 * math.pi * i / n_comp))
               for i in range(n_comp)]
        edges = sorted({(min(i, j), max(i, j)) for i, nb in enumerate(proc._neighbours) for j in nb})
        world = {"n": n_comp, "pos": pos, "edges": edges, "breadth": breadth,
                 "is_parasite": [bool(x) for x in st["is_parasite"]],
                 "max_breadth": max(breadth + [1])}

        # --- Mechanism: robustness vs connectivity (exchange rate), + isolated floor.
        def _run(**kw):
            sim = Composite({"state": cross_feeding_metacommunity(core=core, **kw)}, core=core)
            sim.run(float(n_steps))
            return gather_emitter_results(sim)[("emitter",)][-1]
        exchange = list(np.linspace(0.02, 0.8, 8))
        robustness = [_run(exchange_rate=float(e), diversity=div, parasite_load=0.0,
                           seed=seed)["metacommunity_robustness"] for e in exchange]
        canon = _run(diversity=div, parasite_load=0.0, seed=seed)
        iso = _run(isolated=True, diversity=div, parasite_load=0.0, seed=seed)
        mech = {"exchange": exchange, "robustness": robustness,
                "isolated": iso["metacommunity_robustness"],
                "luca": canon["luca_capability_overlap"],
                "connected_val": canon["metacommunity_robustness"]}

        # --- Decision: the persisted (exchange × parasite_load) grid, or a live one.
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                phase = _ResultView(*_grid_from_json(json.load(f)))
        else:
            n = int(self.config["n_grid"])
            phase = ecology_robustness_parasite_map(
                exchange_rate=(0.02, 0.8, n), parasite_load=(0.0, 0.9, n),
                diversity=div, n_steps=n_steps, n_jobs=1)
        return {"html": ecology_metacommunity_figure(world, mech, phase, title=self.config["title"])}


# ============================================================================
# og-08 — escape from the vent : the complete three-view. Prefix: escape_ /
# offgradient_.
# ============================================================================
def escape_offgradient_figure(phase, trajectories, knockouts, *, title=None) -> str:
    """og-08 three-view figure. **World** (top-left): the lineage-persistence
    trajectories off-gradient — as geological support is withdrawn over the run only the
    full innovation set persists; each knockout collapses. **Mechanism** (bottom-left):
    the minimum-innovation-set knockout bars — final surviving fraction for the full set
    vs each single knockout {−pump, −importer, −heredity}; removing ANY one collapses
    persistence, so the set is irreducible. **Decision** (right): the ``escape_survival_map``
    — the survival frontier over (environmental-support × innovation set); the full set
    reaches support→0 (autonomy), each knockout is lifted off the gradient.

    ``phase`` = the off_gradient_phase_map SweepResult/view; ``trajectories`` =
    {set: {t, survivors, support}}; ``knockouts`` = {set: {survivors, machinery}}."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    labels = list(phase.meta.get("innovation_sets")
                  or ["full", "-pump", "-importer", "-heredity", "none"])
    support = np.asarray(phase.axes["support"], float)
    Z = np.asarray(phase.surfaces["persistence"], float)       # [support, set]
    frontier = phase.meta.get("frontier") or {}
    thr = float(phase.meta.get("persist_threshold", 0.5))
    set_idx = list(range(len(labels)))

    fig = make_subplots(
        rows=2, cols=2, column_widths=[0.5, 0.5], row_heights=[0.52, 0.48],
        horizontal_spacing=0.12, vertical_spacing=0.17,
        specs=[[{}, {"rowspan": 2}], [{}, None]],
        subplot_titles=("World — lineage persistence as support is withdrawn",
                        "Decision — the survival frontier off the gradient",
                        "Mechanism — each innovation is necessary (knockouts)"))

    # --- World (top-left): the escape time-course ------------------------------
    for lab in labels:
        tr = (trajectories or {}).get(lab)
        if not tr:
            continue
        fig.add_trace(go.Scatter(
            x=tr["t"], y=tr["survivors"], mode="lines", name=lab,
            legendgroup=lab,
            line=dict(color=_OFFGRID_SET_COLORS.get(lab, _SLATE),
                      width=3.2 if lab == "full" else 2,
                      dash="solid" if lab == "full" else "dash")), row=1, col=1)
    any_tr = next((t for t in (trajectories or {}).values() if t), None)
    if any_tr:
        fig.add_trace(go.Scatter(
            x=any_tr["t"], y=any_tr["support"], mode="lines", name="support (withdrawn)",
            line=dict(color=_INK, width=1.5, dash="dot"), opacity=0.5, legendgroup="support"), row=1, col=1)
    fig.add_hline(y=thr, line=dict(color=_SLATE, width=1, dash="dot"), row=1, col=1)
    fig.update_xaxes(title_text="time (geological support withdrawn over the run)", row=1, col=1)
    fig.update_yaxes(title_text="surviving fraction", range=[-0.03, 1.06], row=1, col=1)

    # --- Mechanism (bottom-left): the knockout bars ----------------------------
    ko_labels = [l for l in labels if l != "none"]
    ko_vals = [float((knockouts or {}).get(l, {}).get("survivors", 0.0)) for l in ko_labels]
    ko_colors = [_OFFGRID_SET_COLORS.get(l, _SLATE) for l in ko_labels]
    fig.add_trace(go.Bar(
        x=ko_labels, y=ko_vals, marker_color=ko_colors, showlegend=False,
        text=[f"{v:.2f}" for v in ko_vals], textposition="outside",
        hovertemplate="%{x}: survivors %{y:.2f}<extra></extra>"), row=2, col=1)
    fig.add_hline(y=thr, line=dict(color=_SLATE, width=1, dash="dot"), row=2, col=1)
    # the -heredity error-catastrophe annotation (machinery lost).
    mh = (knockouts or {}).get("-heredity", {}).get("machinery")
    if mh is not None:
        fig.add_annotation(x="-heredity", y=0.12, xref="x3", yref="y3", showarrow=True,
                           arrowhead=2, ax=0, ay=-34,
                           text=f"machinery → {mh:.2f}<br>(error catastrophe)",
                           font=dict(size=8.5, color=_RUST), row=2, col=1)
    fig.update_xaxes(title_text="innovation set", row=2, col=1)
    fig.update_yaxes(title_text="surviving fraction<br>off-gradient", range=[0, 1.15], row=2, col=1)

    # --- Decision (right, rowspan 2): the survival-frontier phase map ----------
    fig.add_trace(go.Heatmap(
        x=set_idx, y=support, z=Z, colorscale="Viridis", zmin=0, zmax=1,
        colorbar=dict(title="persist.", len=0.9, x=1.0, thickness=12),
        customdata=np.array([[labels[j] for j in set_idx] for _ in support]),
        hovertemplate="%{customdata}<br>support=%{y:.2f}<br>persistence=%{z:.2f}<extra></extra>"), row=1, col=2)
    fx, fy = [], []
    for j, lab in enumerate(labels):
        fv = frontier.get(lab)
        fx.append(j)
        fy.append(float(fv) if fv is not None else float(support.max()) + 1.0)
    fig.add_trace(go.Scatter(
        x=fx, y=fy, mode="lines+markers", line=dict(color="#f8fafc", width=2.5, dash="dot"),
        marker=dict(size=11, color="#f8fafc", line=dict(width=1.2, color=_INK)),
        name="survival frontier", showlegend=False, text=labels,
        hovertemplate="%{text}: min support %{y:.2f}<extra></extra>"), row=1, col=2)
    if frontier.get(labels[0]) is not None and float(frontier[labels[0]]) <= support.min() + 1e-9:
        fig.add_annotation(x=0, y=support.min(), text="autonomous<br>(persists to 0)", showarrow=True,
                           arrowhead=2, ax=44, ay=-30, font=dict(size=9, color=_TEAL),
                           xref="x2", yref="y2")
    fig.update_xaxes(tickmode="array", tickvals=set_idx, ticktext=labels,
                     title_text="innovation set", row=1, col=2)
    fig.update_yaxes(title_text="environmental support (1 = vent, 0 = off-gradient)", row=1, col=2)

    fig.update_layout(**S.base_layout(
        height=680, margin=dict(l=70, r=40, t=50, b=110),
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center", font=dict(size=9))))
    cap = ("All three views at once. Escaping the vent is not one innovation but an irreducible set. "
           "<b>World</b>: lineage persistence as support is withdrawn. <b>Mechanism</b>: knockouts &mdash; "
           "removing any one of {pump, importer, heredity} collapses off-gradient persistence. "
           "<b>Decision</b>: only the full set persists as geological support &rarr; 0, because the budget "
           "is co-limited (energy AND resources).")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Escape from the vent"),
                   phase="Campaign VIII", view="Decision", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1100)


class EscapeOffGradientThreeView(Visualization):
    """og-08 complete three-view (World persistence trajectories + Mechanism knockout
    bars + Decision survival-frontier phase map). The deterministic off-gradient lineage
    is cheap, so the trajectories and knockouts are always computed live; the survival-
    frontier grid loads from ``grid_json`` (or a modest live grid)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign VIII — escape from the vent"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 28},
        "n_steps": {"_type": "integer", "_default": 60},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..autonomy.off_gradient import decline_trajectory, simulate_offgradient
        from ..phase_maps import _INNOVATION_SETS, off_gradient_phase_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                phase = _ResultView(*_grid_from_json(json.load(f)))
        else:
            phase = off_gradient_phase_map(support=(0.0, 1.0, int(self.config["n_grid"])),
                                           n_steps=int(self.config["n_steps"]))
        n = int(self.config["n_steps"])
        trajectories = {label: decline_trajectory(n_steps=n, **flags)
                        for label, flags in _INNOVATION_SETS}
        # Knockouts off-gradient (support held at 0): final survivors + machinery integrity.
        knockouts = {}
        for label, flags in _INNOVATION_SETS:
            r = simulate_offgradient(0.0, n_steps=n, **flags)
            knockouts[label] = {"survivors": r["survivors"], "machinery": r["machinery"]}
        return {"html": escape_offgradient_figure(phase, trajectories, knockouts,
                                                  title=self.config["title"])}


# ============================================================================
# og-adv — the adversarial control : the complete three-view (polished gate +
# per-gate bars, plus a World trajectory panel). Prefix: vent_specificity_ /
# advcontrol_.
# ============================================================================
def advcontrol_trajectory_panel(fig, trajectories, *, row, col, gate_mM=50.0):
    """World panel for og-adv: formate (mM, log) over time — the vent is productive
    (climbs past the og-01 formate gate) while the generic control stays flat at ≈0."""
    import plotly.graph_objects as go

    vent = (trajectories or {}).get("vent") or {}
    generic = (trajectories or {}).get("generic") or {}
    if vent:
        fig.add_trace(go.Scatter(x=vent["t"], y=vent["formate_mM"], mode="lines",
                                 name="vent", line=dict(color=_TEAL, width=3)), row=row, col=col)
    if generic:
        fig.add_trace(go.Scatter(x=generic["t"], y=generic["formate_mM"], mode="lines",
                                 name="generic control",
                                 line=dict(color=_RUST, width=2.4, dash="dash")), row=row, col=col)
    fig.add_hline(y=gate_mM, line=dict(color=_INK, width=1.4, dash="dot"), row=row, col=col)
    return fig


def vent_specificity_matched_figure(trajectories, *, gate_mM=50.0, title=None) -> str:
    """og-adv reduced FIG 1 — the matched-condition control comparison ONLY: the SAME
    real carbon-fixation composite run under vent-like vs generic nonequilibrium boundary
    conditions, formate (mM, log) over time against the og-01 formate gate. The redundant
    gate-margin bars and the (H₂ × catalyst) parameter contour live on the primary
    vent-specificity map / the appendix, not here."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=1, subplot_titles=(
        "Matched conditions — vent-like vs generic nonequilibrium boundary",))
    advcontrol_trajectory_panel(fig, trajectories, row=1, col=1, gate_mM=gate_mM)
    _tlab = ((trajectories or {}).get("vent", {}).get("t_label")
             or (trajectories or {}).get("generic", {}).get("t_label") or "time (steps)")
    fig.add_annotation(x=0.5, y=0.97, xref="x domain", yref="y domain", xanchor="center",
                       text=f"og-01 formate gate ({gate_mM:.0f} mM)", showarrow=False,
                       font=dict(size=9, color=_INK))
    fig.update_xaxes(title_text=_tlab, row=1, col=1)
    fig.update_yaxes(type="log", title_text="formate (mM)", row=1, col=1)
    fig.update_layout(**S.base_layout(height=440, width=720, margin=dict(t=48, b=60, l=75, r=30),
                                      legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center",
                                                  font=dict(size=9))))
    cap = ("Matched simulations compare carbon production and gate outcomes under vent-like versus generic "
           "nonequilibrium boundary conditions (the identical composite, vent features on vs off). The "
           "generic control holds carbon production near zero while the vent climbs past the og-01 formate "
           "gate. <b>Inferential limit:</b> the generic condition removes H₂, the Fe/Ni/S catalyst and the "
           "pore gradient simultaneously, so this matched comparison is a lumped contrast, not an attribution "
           "to any single ingredient &mdash; it cannot by itself establish vent-specificity without a "
           "factorial ablation.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Matched-condition control: vent vs generic"),
                   phase="Adversarial control", view="World", tier="null_control",
                   caption_text=cap, caption_prefix="How to read", tone="caution")


def vent_specificity_threeview_figure(res, trajectories, gate_rows=None, *, title=None) -> str:
    """og-adv complete three-view figure. **World** (top-left): formate (mM, log) over
    time — the vent is productive (→ 200 mM) while the generic control stays flat at ≈0
    (the same real composite, vent features off). **Mechanism** (bottom-left): every
    vent-specific gate's margin log₁₀(value / threshold) for the vent vs the generic
    control — every generic bar below the gate line (rejected), every vent bar above it
    (passes). **Decision** (right): the og-01 carbon-flux gate over (dissolved H₂ ×
    Fe/Ni/S catalyst); the PASS region is the vent corner, the generic control sits far
    below the threshold boundary (white dashed).

    ``res`` = the vent_specificity_map SweepResult/view; ``trajectories`` =
    {"vent"/"generic": {t, formate_mM}}; ``gate_rows`` = per-gate vent/generic/threshold."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    h2 = np.asarray(res.axes["h2"], float)
    cat = np.asarray(res.axes["catalyst_active"], float)
    thr = float(res.meta.get("gate_threshold", 1.0e-6))
    pf = np.asarray(res.surfaces["peak_flux"], float)          # [h2, catalyst]
    z = np.log10(np.clip(pf.T, 1e-15, None))                   # z[y=catalyst][x=h2]

    fig = make_subplots(
        rows=2, cols=2, column_widths=[0.5, 0.5], row_heights=[0.52, 0.48],
        horizontal_spacing=0.13, vertical_spacing=0.17,
        specs=[[{}, {"rowspan": 2}], [{}, None]],
        subplot_titles=("World — vent is productive, the generic control is not",
                        "Decision — carbon-fixation gate over (H₂ × catalyst)",
                        "Mechanism — every gate rejects the generic control"))

    # --- World (top-left): formate trajectories --------------------------------
    advcontrol_trajectory_panel(fig, trajectories, row=1, col=1, gate_mM=50.0)
    fig.add_annotation(x=0.5, y=0.96, xref="x domain", yref="y domain", xanchor="center",
                       text="og-01 formate gate (50 mM)", showarrow=False,
                       font=dict(size=8.5, color=_INK))
    _tlab = ((trajectories or {}).get("vent", {}).get("t_label")
             or (trajectories or {}).get("generic", {}).get("t_label") or "time (steps)")
    fig.update_xaxes(title_text=_tlab, row=1, col=1)
    fig.update_yaxes(type="log", title_text="formate (mM)", row=1, col=1)

    # --- Mechanism (bottom-left): the per-gate rejection bars ------------------
    if gate_rows:
        labels = [g["label"] for g in gate_rows]
        m_vent = [float(np.log10(max(g["vent"], 1e-300) / g["threshold"])) for g in gate_rows]
        m_ctrl = [float(np.log10(max(g["generic"], 1e-300) / g["threshold"])) for g in gate_rows]
        fig.add_trace(go.Bar(y=labels, x=m_vent, orientation="h", name="vent",
                             marker_color=_TEAL, legendgroup="vent"), row=2, col=1)
        fig.add_trace(go.Bar(y=labels, x=m_ctrl, orientation="h", name="generic control",
                             marker_color=_RUST, legendgroup="generic control"), row=2, col=1)
        fig.add_vline(x=0.0, line=dict(color=_INK, width=1.6), row=2, col=1)
        fig.update_xaxes(title_text="gate margin  log₁₀(value / threshold)", row=2, col=1)

    # --- Decision (right, rowspan 2): the gate contour -------------------------
    fig.add_trace(go.Contour(
        x=h2, y=cat, z=z, colorscale="Viridis", ncontours=16,
        colorbar=dict(title="log₁₀ peak<br>net C-flux<br>(mol/s)", len=0.9, x=1.0, thickness=12),
        contours=dict(showlabels=True, labelfont=dict(size=8, color="white")),
        line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=2)
    fig.add_trace(go.Contour(
        x=h2, y=cat, z=z, showscale=False,
        contours=dict(start=np.log10(thr), end=np.log10(thr), coloring="lines"),
        line=dict(color="#f8fafc", width=2.6, dash="dash"), hoverinfo="skip"), row=1, col=2)
    fig.add_trace(go.Scatter(
        x=[float(h2[-1])], y=[float(cat[-1])], mode="markers+text", text=["vent<br>(passes)"],
        textposition="bottom left", textfont=dict(size=10, color=_INK),
        marker=dict(symbol="star", size=15, color=_AMBER, line=dict(width=1.2, color=_INK)),
        showlegend=False), row=1, col=2)
    fig.add_trace(go.Scatter(
        x=[float(h2[0])], y=[float(cat[0])], mode="markers+text",
        text=["generic control<br>(rejected)"], textposition="top right",
        textfont=dict(size=10, color=_RUST),
        marker=dict(symbol="x", size=13, color=_RUST, line=dict(width=1.2, color=_INK)),
        showlegend=False), row=1, col=2)
    fig.update_xaxes(type="log", title_text="dissolved H₂ (M)", row=1, col=2)
    fig.update_yaxes(title_text="Fe/Ni/S catalyst activity", row=1, col=2)

    fig.update_layout(**S.base_layout(
        height=680, margin=dict(l=70, r=40, t=50, b=110), barmode="group",
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center", font=dict(size=9))))
    cap = ("All three views at once. The SAME real composites with no sustained H₂, no Fe/Ni/S catalyst "
           "and no pore concentration fail every discriminating gate, where the vent passes all five. "
           "<b>World</b>: vent is productive, the generic control is not. <b>Mechanism</b>: every gate "
           "rejects the generic control. <b>Decision</b>: the gate PASS region is the vent corner. "
           "<b>Inferential limit:</b> the generic control removes H₂, the Fe/Ni/S catalyst and the pore "
           "gradient all at once, so this lumped all-negative control shows only that the combined vent "
           "ingredients are jointly sufficient &mdash; it does NOT attribute the failure to any single "
           "ingredient, and vent-specificity stays a bounded claim pending a factorial (H₂ × Fe/Ni/S × "
           "pore) ablation.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Vent-specificity of the gates"),
                   phase="Adversarial control", view="Decision", tier="null_control",
                   caption_text=cap, caption_prefix="How to read", tone="caution", max_width=1100)


class VentSpecificityThreeView(Visualization):
    """og-adv complete three-view (World vent-vs-generic trajectories + Mechanism
    per-gate rejection bars + Decision carbon-flux gate contour). Loads the persisted
    grid (``grid_json`` — whose meta carries the per-gate ``gate_rows``) for the contour
    and bars, and runs the real carbon-fixation composite in vent vs generic mode live
    for the World trajectory panel."""

    config_schema = {
        "title": {"_type": "string", "_default": "Adversarial control — vent-specificity of the gates"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 12},
        "n_steps": {"_type": "integer", "_default": 40},
        "traj_steps": {"_type": "integer", "_default": 50},
        "matched_only": {"_type": "boolean", "_default": False},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..adversarial import GENERIC_PARAMS, VENT_PARAMS
        from ..composites.carbon_fixation import hydrothermal_carbon_fixation
        from ..core import build_core
        from ..phase_maps import vent_specificity_map
        from process_bigraph import Composite, gather_emitter_results

        core = build_core()
        matched_only = bool(self.config.get("matched_only", False))
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        gate_rows = None
        res = None
        if not matched_only:
            if resolved:
                with open(resolved) as f:
                    blob = json.load(f)
                res = _ResultView(*_grid_from_json(blob))
                gate_rows = res.meta.get("gate_rows")
            else:
                n = int(self.config["n_grid"])
                res = vent_specificity_map(h2=(1.0e-9, 2.0e-2, n), catalyst_active=(0.0, 1.0, n),
                                           n_steps=int(self.config["n_steps"]), n_jobs=1)

        # World trajectories: the real carbon-fixation composite, vent vs generic.
        tsteps = int(self.config["traj_steps"])

        def _traj(params):
            sim = Composite({"state": hydrothermal_carbon_fixation(core=core, **params)}, core=core)
            sim.run(float(tsteps))
            rows = gather_emitter_results(sim)[("emitter",)]
            t, t_label = S.real_time([float(r.get("global_time", i)) for i, r in enumerate(rows)],
                                     hydrothermal_carbon_fixation)
            form = [max(float(r.get("formate", 0.0)) * 1e3, 1e-12) for r in rows]
            return {"t": t, "formate_mM": form, "t_label": t_label}
        trajectories = {"vent": _traj(VENT_PARAMS["carbon"]),
                        "generic": _traj(GENERIC_PARAMS["carbon"])}
        if matched_only:
            return {"html": vent_specificity_matched_figure(trajectories, title=self.config["title"])}
        return {"html": vent_specificity_threeview_figure(res, trajectories, gate_rows=gate_rows,
                                                          title=self.config["title"])}


# ----------------------------------------------------------------------------
# og-03 — multisolute co-localization phase map (Phase 4 / §4.5)
# ----------------------------------------------------------------------------
def colocalization_figure(res, *, title=None) -> str:
    """The multisolute co-localization Decision surface over (Soret strength ×
    advective Peclet): does the prebiotic MIXTURE concentrate together, or
    fractionate? **Left:** the co-localization index (min/max of the per-species
    enrichment) — 1 = every solute concentrates together, → 0 = one solute is
    pulled out while others concentrate. **Right:** the strongest single-species
    enrichment, so the two read together as strong+uniform (co-localized trap),
    strong+non-uniform (fractionating), or weak (no concentration)."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    _, axes, surfaces, meta = (res.axis_order, res.axes, res.surfaces, res.meta)
    pe = np.asarray(axes.get("peclet"))
    ss = np.asarray(axes.get("soret_scale"))
    coloc = np.asarray(surfaces.get("coloc_index"))
    maxe = np.asarray(surfaces.get("max_enrichment"))

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.16,
                        subplot_titles=("Co-localization index (min/max enrichment)",
                                        "Strongest single-species enrichment"))
    # low index = fractionating (rust) -> high = co-localized (teal)
    fig.add_trace(go.Heatmap(
        z=coloc, x=ss, y=pe, colorscale=[[0.0, _RUST], [0.5, _AMBER], [1.0, _TEAL]],
        zmin=0.0, zmax=1.0, colorbar=dict(title="coloc", x=0.44, len=0.9),
        hovertemplate="soret×%{x}, Pe=%{y}<br>coloc=%{z:.3f}<extra></extra>"),
        row=1, col=1)
    fig.add_trace(go.Heatmap(
        z=maxe, x=ss, y=pe, colorscale="Viridis",
        colorbar=dict(title="max E", x=1.01, len=0.9),
        hovertemplate="soret×%{x}, Pe=%{y}<br>max E=%{z:.2f}×<extra></extra>"),
        row=1, col=2)
    # dolfinx FEM reference audit cells (structure-agreement overlay): the real
    # 3-D solve at a few cells, confirming the surrogate's co-localize/fractionate
    # verdict (partial agreement on the exact index).
    audit = meta.get("fem_audit") if isinstance(meta, dict) else None
    if audit:
        fig.add_trace(go.Scatter(
            x=[a["soret_scale"] for a in audit], y=[a["peclet"] for a in audit],
            mode="markers+text",
            text=[f"FEM {a['fem_coloc_index']:.2f}" for a in audit],
            textposition="top center", textfont=dict(size=9, color=_INK),
            marker=dict(symbol="diamond", size=11, color="white",
                        line=dict(color=_INK, width=1.5)),
            hovertemplate="FEM audit soret×%{x}, Pe=%{y}<extra></extra>",
            showlegend=False), row=1, col=1)
    for c in (1, 2):
        fig.update_xaxes(title_text="Soret strength (× nominal)", type="log", row=1, col=c)
        fig.update_yaxes(title_text="advective Péclet", type="log", row=1, col=c)
    fig.update_layout(**S.base_layout(height=460, width=980,
                                      margin=dict(l=70, r=80, t=44, b=60), showlegend=False))
    cap = (
        "A low co-localization index where single species still concentrate means the mixture "
        "<b>fractionates</b>: different solutes concentrate to different degrees set by their Soret "
        "coefficient (low-S_T solutes such as ammonium lag the strong thermophoretic precursors). "
        "Adsorption and degradation are kinetically minor over a single pore transit, so they are not "
        "the primary driver. White diamonds are resolved-FEM audit cells. Strong + uniform = a "
        "co-localized trap; strong + non-uniform = fractionating; weak = no concentration."
    )
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Does the prebiotic mixture co-localize? It fractionates"),
                   phase="Phase 4", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class PoreColocalizationMap(Visualization):
    """og-03 Phase-4 Decision view: the multisolute co-localization phase map over
    (Soret strength × advective Peclet). Renders from a persisted grid
    (``grid_json``) or computes a modest grid live via ``colocalization_map``."""

    config_schema = {
        "title": {"_type": "string", "_default": "Multisolute co-localization frontier"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_pe": {"_type": "integer", "_default": 6},
        "n_soret": {"_type": "integer", "_default": 6},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..colocalization_map import colocalization_map
        resolved = _resolve_grid_path(str(self.config.get("grid_json", "") or ""))
        if resolved:
            with open(resolved) as f:
                res = _ResultView(*_grid_from_json(json.load(f)))
        else:
            import numpy as np
            n_pe = int(self.config["n_pe"])
            n_s = int(self.config["n_soret"])
            res = colocalization_map(
                peclets=tuple(np.geomspace(1.0, 32.0, n_pe)),
                soret_scales=tuple(np.geomspace(0.5, 8.0, n_s)))
        return {"html": colocalization_figure(res, title=self.config["title"])}


class PoreTransportAttributionViz(Visualization):
    """og-spatial-concentration transport-attribution control — the favourable thermal
    trap vs matched nulls (ΔT=0, flow=0, open-pore), read from ``report_json``
    (gradient_off_control.json). Enrichment collapses ONLY for the open-pore null: the
    reduced-model accumulation Péclet is set by pore confinement, not ΔT or flow."""

    config_schema = {
        "title": {"_type": "string", "_default": "What drives the localized enrichment? (transport attribution)"},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go
        path = _resolve_grid_path(str(self.config.get("report_json", "") or ""))
        if not path:
            return {"html": S.frame("<p>No control artifact found.</p>", title=self.config["title"])}
        with open(path) as f:
            blob = json.load(f)
        arms = blob["arms"]
        collapses = blob.get("collapses_enrichment", {})
        order = ["favorable", "gradient_off", "flow_off", "open_pore"]
        labels = {"favorable": "favourable<br>trap", "gradient_off": "ΔT = 0<br>(gradient off)",
                  "flow_off": "flow = 0<br>(no convection)", "open_pore": "open pore<br>(porosity≈1)"}
        present = [k for k in order if k in arms]
        xs = [labels[k] for k in present]
        ys = [arms[k].get("enrichment_factor") or 0.0 for k in present]
        colors = [_TEAL if k == "favorable" else (_RUST if collapses.get(k) else _SLATE) for k in present]
        fig = go.Figure(go.Bar(x=xs, y=ys, marker_color=colors,
                               text=[f"{v:.3g}×" for v in ys], textposition="outside"))
        fig.update_yaxes(type="log", title_text="enrichment factor (×, log)", showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(**S.base_layout(height=430, showlegend=False, margin=dict(l=72, r=28, t=42, b=76)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return {"html": S.frame(
            inner, title=self.config["title"],
            phase="Spatial organization", view="Control", tier="mechanistic_prediction",
            caption_prefix="How to read", tone="neutral",
            caption_text=(
                "Matched-null transport attribution for the localized enrichment, every other parameter held "
                "equal on the real FiPy ThermophoreticTrapProcess. Enrichment collapses (~10⁸× → ~1) under EACH "
                "off-null — thermal-gradient-off (ΔT→0), no-convection (flow→0) and open-pore (porosity≈1) — so "
                "the accumulation Péclet, hence the localized enrichment, depends on all three transport terms: "
                "the thermal gradient, the convective flow, and the pore confinement. Any one removed destroys "
                "the trap. Consistent with the study's Péclet-gated framing; gate/verdict unchanged. Method note: "
                "the off-nulls use a near-zero epsilon (1e-9), not 0.0 — a bare 0.0 is backfilled to the "
                "parameter default (the pbg is_empty rule) and would silently reproduce the favourable arm."))}


class NetworkControlViz(Visualization):
    """og-network-persistence no-catalyst / no-feed matched-null control, read from
    ``report_json`` (network_controls.json). Steady-state net carbon flux collapses when
    the catalyst (k_rtca→0) or the feed (→0) is removed — A1's sustained throughput is
    genuinely feed/catalyst-driven."""

    config_schema = {
        "title": {"_type": "string", "_default": "Sustained throughput requires feed + catalyst (matched nulls)"},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go
        path = _resolve_grid_path(str(self.config.get("report_json", "") or ""))
        if not path:
            return {"html": S.frame("<p>No control artifact found.</p>", title=self.config["title"])}
        with open(path) as f:
            blob = json.load(f)
        arms = blob["arms"]
        collapse = blob.get("controls_collapse", {})
        order = ["favorable", "no_catalyst", "no_feed"]
        labels = {"favorable": "favourable", "no_catalyst": "no catalyst<br>(k_rtca→0)", "no_feed": "no feed<br>(→0)"}
        present = [k for k in order if k in arms]
        xs = [labels[k] for k in present]
        ys = [max(arms[k].get("ss_net_carbon_flux") or 0.0, 1e-18) for k in present]
        colors = [_TEAL if k == "favorable" else (_RUST if collapse.get(k) else _SLATE) for k in present]
        gains = [arms[k].get("ss_autocatalytic_gain") for k in present]
        fig = go.Figure(go.Bar(x=xs, y=ys, marker_color=colors,
                               text=[f"gain {g:.2g}" if g is not None else "" for g in gains],
                               textposition="outside"))
        fig.update_yaxes(type="log", title_text="steady-state net carbon flux (mol/s, log)",
                         showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(**S.base_layout(height=420, showlegend=False, margin=dict(l=78, r=28, t=42, b=64)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return {"html": S.frame(
            inner, title=self.config["title"],
            phase="Network persistence", view="Control", tier="mechanistic_prediction",
            caption_prefix="How to read", tone="neutral",
            caption_text=(
                "Matched nulls on the real libRoadRunner protometabolic CSTR, steady-state (post-transient, "
                "last third of a 120-step run), every other parameter held equal. The favourable network sustains "
                "net carbon flux (~9e-4 mol/s) with autocatalytic gain ~3; removing the catalyst (k_rtca→0) drops "
                "the gain to ~0 and removing the feed (→0) drops the net flux to ~0 — both nulls collapse, so A1's "
                "sustained throughput genuinely requires both the catalyst and the feed (it is not a source-driven "
                "transient). Method note: the off-nulls use epsilon (1e-9), not 0.0 — a bare 0.0 is backfilled to "
                "the parameter default (pbg is_empty rule) and would reproduce the favourable arm."))}


class EnergeticsUncoupledControlViz(Visualization):
    """og-energetics uncoupled-pump matched-null control, read from ``report_json``
    (uncoupled_pump_control.json). Survivors and autonomy collapse when the pump is
    uncoupled (catalyst_efficiency→0) — the internalization benefit requires coupling."""

    config_schema = {
        "title": {"_type": "string", "_default": "The internalization benefit requires coupling (uncoupled-pump null)"},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go
        path = _resolve_grid_path(str(self.config.get("report_json", "") or ""))
        if not path:
            return {"html": S.frame("<p>No control artifact found.</p>", title=self.config["title"])}
        with open(path) as f:
            blob = json.load(f)
        arms = blob["arms"]
        fav, unc = arms.get("favorable", {}), arms.get("uncoupled", {})
        metrics = [("survivors", "survivors"), ("autonomy", "autonomy"), ("internalization", "internalization")]
        xs = [m[1] for m in metrics]
        fig = go.Figure()
        fig.add_bar(x=xs, y=[fav.get(m[0]) or 0.0 for m in metrics], name="favourable (coupled)", marker_color=_TEAL)
        fig.add_bar(x=xs, y=[unc.get(m[0]) or 0.0 for m in metrics], name="uncoupled pump", marker_color=_RUST)
        fig.update_yaxes(title_text="fraction", range=[0, 1.05], showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(**S.base_layout(height=420, barmode="group",
                                          legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"),
                                          margin=dict(l=60, r=28, t=42, b=66)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return {"html": S.frame(
            inner, title=self.config["title"],
            phase="Energy", view="Control", tier="mechanistic_prediction",
            caption_prefix="How to read", tone="neutral",
            caption_text=(
                "Matched null on the real bioenergetic-internalization selection loop over a declining external "
                "gradient, every other parameter held equal. The favourable efficient pump internalizes gradient "
                "generation and persists (survivors ~1, autonomy ~0.99); an UNCOUPLED pump (near-zero coupling "
                "efficiency) cannot internalize and the lineage collapses (survivors 0, autonomy ~0) — so the "
                "internalization/autonomy benefit requires COUPLING, not the carrier's mere presence. The formal "
                "first-law free-energy ledger (in + E0 − work − dissipated = E(t), residual ~1e-16) is closed by "
                "the proto-energetics arm. Method note: the uncoupled arm uses catalyst_efficiency=1e-6, not 0.0 "
                "(a bare 0.0 is backfilled to the default by the pbg is_empty rule)."))}


class CarbonFixationMassBalanceViz(Visualization):
    """og-carbon-fixation observed-vs-predicted yields (Preiner/Hudson) + catalyst gating
    (left) and the usable-gradient pmf favourable vs Tutolo (right), read from
    ``report_json`` (carbon_massbalance_control.json)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Yields reproduce Preiner/Hudson (catalyst-gated); the gradient bites the pmf"},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        path = _resolve_grid_path(str(self.config.get("report_json", "") or ""))
        if not path:
            return {"html": S.frame("<p>No control artifact found.</p>", title=self.config["title"])}
        with open(path) as f:
            blob = json.load(f)
        ovp = blob["obs_vs_pred_preiner_hudson"]
        species = ["formate", "acetate", "pyruvate"]
        obs = [ovp[s]["observed"] for s in species]
        pred = [ovp[s]["predicted_preiner_hudson"] for s in species]
        nocat = [blob["arms"]["no_catalyst"].get(s) or 1e-18 for s in species]
        pmf = blob.get("pmf_mV", {})

        fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.16,
                            subplot_titles=("Observed vs predicted yields (M, log)",
                                            "Usable gradient — pmf (mV)"))
        fig.add_bar(x=species, y=obs, name="observed", marker_color=_TEAL, row=1, col=1)
        fig.add_bar(x=species, y=nocat, name="no catalyst", marker_color=_RUST, row=1, col=1)
        fig.add_trace(go.Scatter(x=species, y=pred, mode="markers", name="Preiner/Hudson (predicted)",
                                 marker=dict(symbol="line-ew", size=22, line=dict(width=3, color=_INK))),
                      row=1, col=1)
        fig.update_yaxes(type="log", title_text="concentration (M)", row=1, col=1, showgrid=True, gridcolor="#eef2f7")
        fig.add_bar(x=["favourable<br>(geff=1.0)", "Tutolo-2026<br>(geff=0.1)"],
                    y=[pmf.get("favorable"), pmf.get("tutolo")], marker_color=[_TEAL, _AMBER],
                    showlegend=False, text=[f"{pmf.get('favorable'):.0f}", f"{pmf.get('tutolo'):.0f}"],
                    textposition="outside", row=1, col=2)
        fig.update_yaxes(title_text="pmf (mV)", row=1, col=2, showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(**S.base_layout(height=440, barmode="group",
                                          legend=dict(orientation="h", y=-0.2, x=0.0, font=dict(size=10)),
                                          margin=dict(l=62, r=28, t=52, b=72)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return {"html": S.frame(
            inner, title=self.config["title"],
            phase="Carbon fixation", view="Control", tier="mechanistic_prediction",
            caption_prefix="How to read", tone="neutral",
            caption_text=(
                "Left: the favourable arm's product yields (teal) land exactly on the Preiner-2020 / Hudson "
                "reference hierarchy (black ticks) — formate ~200 mM ≫ acetate ~100 µM ≫ pyruvate ~10 µM — and "
                "the no-catalyst null (rust) collapses them, so the yields are catalyst-gated. These are lab-"
                "calibrated yield CEILINGS: deterministic and invariant to CO₂/H₂/gradient, so there are no error "
                "bars (none fabricated), and the carbon 'balance' is the product-carbon partition (formate "
                "dominates ~99.9%), not a strict CO₂-feed→products conservation. Right: the usable gradient (pmf) "
                "is where the Tutolo-2026 reassessment bites — ~427 mV favourable → ~43 mV at gradient_efficiency "
                "0.1 — NOT the product concentrations. Both reproduce og-carbon-fixation's existing claims; no "
                "gate change. (Nulls rely on the composite's internal clamp of catalyst_active 0→1e-6.)"))}


class VentGridConvergenceViz(Visualization):
    """og-vent-environment grid-convergence control, read from ``report_json``
    (grid_convergence_control.json). Left: relative change of the outlet observables vs
    the finest mesh across nx (is nx=40 converged?). Right: the converged outlet
    speciation against the Lost City literature windows."""

    config_schema = {
        "title": {"_type": "string", "_default": "The vent reactor is grid-converged at nx=40, in the Lost City window"},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        path = _resolve_grid_path(str(self.config.get("report_json", "") or ""))
        if not path:
            return {"html": S.frame("<p>No control artifact found.</p>", title=self.config["title"])}
        with open(path) as f:
            blob = json.load(f)
        conv = blob["convergence_rel_to_finest"]          # {nx(str): {obs: rel}}
        nxs = sorted(int(k) for k in conv)
        obs_keys = [("temperature_C", "T", _RUST), ("pH", "pH", _TEAL), ("H2", "H₂", _AMBER)]
        fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.15,
                            subplot_titles=("Convergence — |Δ| vs finest mesh (nx=160)",
                                            "Converged outlet vs Lost City window"))
        for key, lbl, col in obs_keys:
            ys = [max(conv[str(nx)].get(key) or 0.0, 1e-9) for nx in nxs]
            fig.add_trace(go.Scatter(x=nxs, y=ys, mode="lines+markers", name=lbl,
                                     line=dict(color=col, width=2.2)), row=1, col=1)
        fig.add_hline(y=0.01, line=dict(color=_SLATE, width=1.2, dash="dot"), row=1, col=1)
        fig.add_vline(x=40, line=dict(color=_INK, width=1.2, dash="dash"), row=1, col=1)
        fig.update_xaxes(title_text="mesh resolution nx", row=1, col=1)
        fig.update_yaxes(type="log", title_text="relative change vs nx=160", row=1, col=1,
                         showgrid=True, gridcolor="#eef2f7")
        # right: converged outlet value vs its literature window (normalized to the window)
        lit = blob["lostcity_literature_check"]
        conv_out = lit["converged_outlet"]
        wins = lit["windows"]
        rows = [("temperature_C", wins["temperature_C"], "T (°C)"), ("pH", wins["pH"], "pH")]
        for i, (key, win, lbl) in enumerate(rows):
            lo, hi = win
            fig.add_trace(go.Scatter(x=[lo, hi], y=[lbl, lbl], mode="lines",
                                     line=dict(color="rgba(13,148,136,0.35)", width=14), showlegend=False,
                                     hovertext=f"Lost City {lo}–{hi}"), row=1, col=2)
            fig.add_trace(go.Scatter(x=[conv_out[key]], y=[lbl], mode="markers",
                                     marker=dict(symbol="diamond", size=13, color=_INK),
                                     showlegend=False, hovertext=f"model {conv_out[key]:.2f}"), row=1, col=2)
        fig.update_xaxes(title_text="value (T in °C / pH)", row=1, col=2)
        fig.update_layout(**S.base_layout(height=430, legend=dict(orientation="h", y=-0.2, x=0.0),
                                          margin=dict(l=60, r=28, t=52, b=64)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        conv40 = blob.get("nx40_converged_under_1pct")
        return {"html": S.frame(
            inner, title=self.config["title"],
            phase="Geological engine", view="Control", tier="mechanistic_prediction",
            caption_prefix="How to read", tone="neutral",
            caption_text=(
                "Left: the relative change of each outlet observable (T, pH, H₂) versus the finest mesh (nx=160) "
                f"as the FiPy cross-section resolution nx increases. nx=40 — the study's choice (dashed line) — "
                f"sits {'below' if conv40 else 'ABOVE'} the 1% line (dotted) on every observable, so the vent "
                "reactor is grid-converged there (not under-resolved). Right: the converged outlet speciation "
                "(T ~50 °C, mineral-buffered pH ~9.4, positive H₂) lands inside the Lost City literature windows "
                "(green bands; Kelley/Proskurowski/Seyfried). PHREEQC held charge balance exactly (|imbalance| 0) "
                "across the whole sweep. A confirming diagnostic — resolution + calibration are sound; no gate change."))}


class PhosphorusSensitivityViz(Visualization):
    """og-nutrient-bottlenecks P-availability sensitivity, read from ``report_json``
    (phosphorus_sensitivity.json). Heatmap of net reactive-P production over the
    mineral-sink (loss_rate) × concentration (pore_enrichment) grid, with the net=0
    availability contour; pore concentration rescues P from the precipitation sink."""

    config_schema = {
        "title": {"_type": "string", "_default": "Reactive-P availability across the mineral sink × pore concentration"},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import numpy as np
        import plotly.graph_objects as go
        path = _resolve_grid_path(str(self.config.get("report_json", "") or ""))
        if not path:
            return {"html": S.frame("<p>No sweep artifact found.</p>", title=self.config["title"])}
        with open(path) as f:
            blob = json.load(f)
        loss = blob["axes"]["loss_rate"]
        enrich = blob["axes"]["pore_enrichment"]
        # z[i,j] = net_reactive_P at loss[i], enrich[j]  (µM/s-scaled for readability)
        cell = {(g["loss_rate"], g["pore_enrichment"]): g for g in blob["grid"]}
        z = [[(cell[(lr, pe)]["net_reactive_P"] or 0.0) * 1e6 for pe in enrich] for lr in loss]
        fig = go.Figure(go.Heatmap(
            x=[f"{e:g}" for e in enrich], y=[f"{l:g}" for l in loss], z=z,
            colorscale="RdBu", zmid=0.0,
            colorbar=dict(title="net reactive-P<br>(×10⁻⁶ /s)"),
            hovertemplate="enrich=%{x}  loss=%{y}<br>net reactive-P=%{z:.3g}e-6<extra></extra>"))
        fig.update_xaxes(title_text="pore enrichment (1 = open-pore control)")
        fig.update_yaxes(title_text="mineral-sink loss rate k_prec (1/s)")
        frac = blob.get("availability_region_fraction")
        fig.update_layout(**S.base_layout(height=440, margin=dict(l=70, r=30, t=46, b=64)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return {"html": S.frame(
            inner, title=self.config["title"],
            phase="Nutrient bottlenecks", view="Sensitivity", tier="mechanistic_prediction",
            caption_prefix="How to read", tone="neutral",
            caption_text=(
                "Net reactive-phosphorus production (blue = available, net > 0; red = precipitation-dominated, "
                "net < 0) over the two knobs the P-speciation model actually has — the mineral-sink loss rate "
                "k_prec (precipitation/adsorption) and the pore enrichment (concentration; enrichment=1 is the "
                f"open-pore control). Reactive P is available across most of the grid "
                f"({int(round((frac or 0)*100))}% of cells); the bottleneck is the low-enrichment / high-sink "
                "corner, where phosphate precipitates before it activates — pore concentration is what rescues "
                "P from the mineral sink. Total phosphorus is conserved across the sweep (max |mass residual| "
                "~2e-6). Honesty note: pH is NOT a parameter of this composite, so pH-sensitivity is not "
                "representable here without a model change (flagged as future work); this is mineral-sink × "
                "concentration (× temperature in the artifact), not a pH sweep. Deterministic ODE — no seeds, "
                "no error bars."))}


class SelfMaintainingDeficitViz(Visualization):
    """og-self-maintaining-individual central negative result, read from ``report_json``
    (self_maintaining.json). Quantifies how many orders the endogenously-produced
    amphiphile pool falls short of its CAC across conditions — endogenous closure is
    refuted; even the most generous arm is orders short, and the chemistry→membrane
    ablation locates the broken edge."""

    config_schema = {
        "title": {"_type": "string", "_default": "Endogenous self-maintenance does not close — the amphiphile deficit"},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go
        path = _resolve_grid_path(str(self.config.get("report_json", "") or ""))
        if not path:
            return {"html": S.frame("<p>No artifact found.</p>", title=self.config["title"])}
        with open(path) as f:
            blob = json.load(f)
        conds = blob.get("conditions", {})

        def od(key):
            return (conds.get(key, {}) or {}).get("orders_short_of_cac")

        # headline bars: the two corners × (no-gain, built-in-gain rescue control) + the broken-edge ablation
        bars = [
            ("canonical<br>no gain", od("canonical:full_no_gain"), _TEAL),
            ("canonical<br>+built-in gain", od("canonical:full_built_in_gain"), _AMBER),
            ("favourable corner<br>no gain", od("b_corner:full_no_gain"), _TEAL),
            ("favourable corner<br>+built-in gain", od("b_corner:full_built_in_gain"), _AMBER),
            ("chem→mem<br>ablated", od("canonical:ablate_chem_to_mem"), _RUST),
        ]
        bars = [(lbl, v, c) for lbl, v, c in bars if v is not None]
        fig = go.Figure(go.Bar(
            x=[b[0] for b in bars], y=[b[1] for b in bars], marker_color=[b[2] for b in bars],
            text=[f"{b[1]:.1f}" for b in bars], textposition="outside"))
        fig.add_hline(y=0.0, line=dict(color=_INK, width=2),
                      annotation_text="CAC cleared → membrane can form (closure)", annotation_position="top left")
        fig.update_yaxes(title_text="orders of magnitude the amphiphile pool is SHORT of CAC",
                         showgrid=True, gridcolor="#eef2f7", rangemode="tozero")
        fig.update_layout(**S.base_layout(height=450, showlegend=False, margin=dict(l=66, r=28, t=48, b=84)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return {"html": S.frame(
            inner, title=self.config["title"],
            phase="Chemical individuality", view="Decisive result", tier="mechanistic_prediction",
            caption_prefix="How to read", tone="caution",
            caption_text=(
                "The central negative result (verdict: refuted). Each bar is how many orders of magnitude the "
                "amphiphile pool the chemistry ACTUALLY produces falls short of its critical aggregation "
                "concentration — the y=0 line is where a membrane could form (closure). Endogenous closure fails "
                "in EVERY condition: ~6.9 orders short at the canonical point, and even the most generous arm — "
                "the favourable operating-window corner WITH a built-in production/retention gain (a rescue "
                "control, not endogenous closure) — is still ~3 orders short and forms no real membrane "
                "(retention is earned but membrane_real stays False; a 0.905 retention 'if earned' is the false "
                "closure this study forbids). Ablating the chemistry→membrane edge drops the pool ~25.9 orders, "
                "locating the broken edge: the chemistry simply does not deliver enough long-chain amphiphile. "
                "Real AmphiphileChainExtensionProcess output, external feeds held equal across arms; endogenous "
                "chemistry→membrane self-maintenance is not demonstrated (the broader individuality-emergence "
                "question stays open)."))}


class OperatingWindowRegimeViz(Visualization):
    """og-operating-window regime-marked view, read from ``report_json``
    (operating_window.json). Best enriched+retained pool vs the Soret coefficient, with
    the consumable threshold and the defensible/extrapolated regime boundary — so the
    narrow qualifying corner does not read as a broad rescue."""

    config_schema = {
        "title": {"_type": "string", "_default": "The operating window is a narrow corner at the defensible Soret edge"},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go
        path = _resolve_grid_path(str(self.config.get("report_json", "") or ""))
        if not path:
            return {"html": S.frame("<p>No artifact found.</p>", title=self.config["title"])}
        with open(path) as f:
            blob = json.load(f)
        soret = blob["axes"]["soret_coeff"]
        es = blob["enriched_surface_M"]
        best = [max(max(row) for row in plane) for plane in es]   # best over ΔT × feed per soret
        thr = blob.get("consumable_threshold_M", 1e-6)
        s_def = blob.get("defensible_soret_max", 0.01)
        vol_all = blob.get("overlap_volume_all")
        vol_def = blob.get("overlap_volume_defensible")
        colors = [_TEAL if s <= s_def else _SLATE for s in soret]

        fig = go.Figure()
        # defensible / extrapolated shading
        fig.add_vrect(x0=min(soret), x1=s_def, fillcolor="rgba(13,148,136,0.07)", line_width=0,
                      annotation_text="defensible (C2–C3 small molecule)", annotation_position="top left")
        fig.add_vrect(x0=s_def, x1=max(soret), fillcolor="rgba(100,116,139,0.10)", line_width=0,
                      annotation_text="extrapolated (large-biomolecule scale)", annotation_position="top right")
        fig.add_trace(go.Scatter(x=soret, y=best, mode="lines+markers",
                                 marker=dict(size=11, color=colors, line=dict(width=1, color=_INK)),
                                 line=dict(color=_INK, width=1.5), showlegend=False,
                                 text=[f"{v:.2g} M" for v in best], textposition="top center"))
        fig.add_hline(y=thr, line=dict(color=_RUST, width=2, dash="dash"),
                      annotation_text=f"consumable threshold {thr:g} M", annotation_position="bottom right")
        fig.add_vline(x=s_def, line=dict(color=_INK, width=1.4, dash="dot"))
        fig.update_xaxes(type="log", title_text="Soret coefficient S_T (per K) — the dominant, unmeasured parameter")
        fig.update_yaxes(type="log", title_text="best enriched + retained pool (M)")
        fig.update_layout(**S.base_layout(height=450, margin=dict(l=70, r=30, t=54, b=66)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        pct_all = f"{(vol_all or 0)*100:.0f}%" if vol_all is not None else "?"
        pct_def = f"{(vol_def or 0)*100:.0f}%" if vol_def is not None else "?"
        return {"html": S.frame(
            inner, title=self.config["title"],
            phase="Operating window", view="Decisive result", tier="mechanistic_prediction",
            caption_prefix="How to read", tone="caution",
            caption_text=(
                "Best enriched + retained functional pool (max over the ΔT × feed sweep) vs the Soret coefficient "
                "S_T. The pool clears the consumable threshold (red dashed, 1e-6 M) ONLY at the upper defensible "
                f"edge (S_T ≈ {s_def:g}/K → ~6.3e-6 M); below it the pool is short (~4–7e-7 M). The large apparent "
                "rescue at S_T = 0.03–0.1/K sits in the EXTRAPOLATED regime (grey) — a large-biomolecule Soret "
                "scale that is NOT defensible for C2–C3 precursors. So the simultaneous window is a NARROW corner, "
                f"not a broad rescue: it covers only {pct_def} of the defensible Soret range vs {pct_all} of the "
                "full swept space. S_T is the dominant parameter (Morris rank) and is UNMEASURED for C2–C3 at the "
                "vent — the discriminating experiment is to measure it; whether S_T(C2–C3) reaches ~1e-2/K decides "
                "the rescue. Verdict: qualified (a window exists, but hinges on this unmeasured quantity)."))}
