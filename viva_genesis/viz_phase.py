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
    """Two-panel decision figure for og-01: sustained carbon throughput over
    (vent pH × dissolved H₂), favourable vs the Tutolo-2026 gradient collapse,
    on shared axes and a shared colour scale. ``fav``/``tut`` are SweepResults."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    ph = fav.axes["ph_vent"]
    h2 = fav.axes["h2"]
    # surface is indexed [ph, h2]; Contour wants z[y=h2][x=ph] → transpose, ×1e3.
    z_fav = (fav.surfaces["sustained_throughput"] * 1e3).T
    panels = [("Favourable parameterization\n(sustained gradient)", z_fav)]
    if tut is not None:
        z_tut = (tut.surfaces["sustained_throughput"] * 1e3).T
        panels.append(("Tutolo-2026 in-situ collapse\n(gradient efficiency 0.1)", z_tut))

    zmax = max(float(np.nanmax(p[1])) for p in panels)
    fig = make_subplots(rows=1, cols=len(panels),
                        subplot_titles=[p[0].replace("\n", "<br>") for p in panels],
                        horizontal_spacing=0.12, shared_yaxes=True)

    for i, (_, z) in enumerate(panels, start=1):
        fig.add_trace(go.Contour(
            x=ph, y=h2, z=z, zmin=0.0, zmax=zmax,
            colorscale="Viridis", showscale=(i == len(panels)),
            colorbar=dict(title="sustained<br>throughput<br>(10⁻³ mol-C/s)", len=0.9),
            contours=dict(showlabels=True, labelfont=dict(size=10, color="white")),
            line=dict(width=0.5, color="rgba(255,255,255,0.35)"),
        ), row=1, col=i)
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

    fig.update_layout(**S.base_layout(height=440, width=460 * len(panels),
                                      margin=dict(t=48, b=60, l=70, r=20), showlegend=False))
    cap = ("Where geological free energy sustains reduced-carbon production (open-flow vent "
           "reactor). Dark = productive region fails; the no-gradient / no-catalyst / no-H₂ "
           "controls sit off-scale at zero.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The carbon-fixation landscape"),
                   phase="Campaign I", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


def protometabolism_gain_figure(res, *, title=None) -> str:
    """og-02 Decision view: the protometabolic ignition landscape — settled OAA hub
    pool + net throughput over (washout × feed CO₂), with the autocatalytic
    threshold (gain=1) overlaid. ``res`` is a SweepResult / grid view."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    feed = res.axes["feed_CO2"]
    wash = res.axes["k_wash"]
    oaa = res.surfaces["oaa_pool"] * 1e3            # mM, indexed [feed, wash] → z[y=feed][x=wash]
    net = res.surfaces["net_flux"] * 1e3            # 10⁻³ mol-C/s
    gain = res.surfaces["gain"]
    z_oaa = np.log10(np.clip(oaa, 1e-4, None))

    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.12,
                        subplot_titles=("Autocatalytic hub (OAA, mM — log)",
                                        "Net carbon throughput (10⁻³ mol-C/s)"))
    fig.add_trace(go.Contour(x=wash, y=feed, z=z_oaa, colorscale="Viridis", ncontours=14,
                             colorbar=dict(title="log₁₀<br>OAA (mM)", len=0.9, x=0.44),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=1)
    fig.add_trace(go.Contour(x=wash, y=feed, z=net, colorscale="Inferno", ncontours=14, showscale=True,
                             colorbar=dict(title="net flux", len=0.9),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=2)
    # autocatalytic threshold (gain = 1) on both panels.
    for c in (1, 2):
        fig.add_trace(go.Contour(x=wash, y=feed, z=gain, showscale=False,
                                 contours=dict(start=1, end=1, coloring="lines"),
                                 line=dict(color="#f8fafc", width=2.2, dash="dash"),
                                 hoverinfo="skip"), row=1, col=c)
        fig.add_trace(go.Scatter(x=[0.05], y=[2.0e-3], mode="markers+text",
                                 text=["operating<br>point"], textposition="top center",
                                 textfont=dict(size=9, color=_INK),
                                 marker=dict(symbol="star", size=14, color=_AMBER,
                                             line=dict(width=1.1, color=_INK)), showlegend=False), row=1, col=c)
        fig.update_xaxes(type="log", title_text="washout / dilution k_wash (1/s)", row=1, col=c)
    fig.update_yaxes(type="log", title_text="feed CO₂ (M)", row=1, col=1)

    fig.update_layout(**S.base_layout(height=450, width=940, margin=dict(t=48, b=60, l=70, r=20),
                                      showlegend=False))
    cap = ("The rTCA network ignites in a bounded region &mdash; enough geological CO₂ in, "
           "slow enough washout. Dashed line = the autocatalytic threshold (gain=1); beyond it "
           "the loop cannot outpace dilution and the hub washes out.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The protometabolic ignition landscape"),
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
        from .phase_maps import protometabolism_gain_phase_map
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
                             textposition="bottom center", textfont=dict(size=9, color=_INK),
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
    fig.update_xaxes(title_text="time (s)", row=1, col=2)
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

        from .composites.protometabolism import protometabolic_network
        from .composites.thermophoretic_concentration import thermophoretic_concentration
        from .core import build_core
        from .phase_maps import protometabolism_gain_phase_map

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
            traj["t"] = [r.get("global_time", i) for i, r in enumerate(rows)]
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


def protocell_decision_figure(arc, feas, *, title=None) -> str:
    """og-04 Decision view: (left) the retention-access plane — the compartment sweeps
    from too-closed through a viable window to too-open as permeability rises; (right)
    the salt-tolerance feasibility map — the viable ceiling rises with mixed
    amphiphiles. ``arc`` is the temperature sweep; ``feas`` the (mix × salt) sweep."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    acc = arc.surfaces["access"]
    ret = arc.surfaces["retention"]
    ind = arc.surfaces["individuality"]
    ipk = int(np.argmax(ind))

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.13,
                        subplot_titles=("Retention vs access (permeability rising with T)",
                                        "Viable salt ceiling rises with mixed amphiphiles"))
    # --- left: retention-access plane with 3 regimes ---
    fig.add_shape(type="rect", x0=0.0, x1=0.55, y0=0.55, y1=1.02, line=dict(width=0),
                  fillcolor="rgba(100,116,139,0.10)", row=1, col=1)
    fig.add_shape(type="rect", x0=0.55, x1=1.02, y0=0.0, y1=0.55, line=dict(width=0),
                  fillcolor="rgba(185,28,28,0.08)", row=1, col=1)
    fig.add_shape(type="rect", x0=0.55, x1=1.02, y0=0.55, y1=1.02, line=dict(width=0),
                  fillcolor="rgba(13,148,136,0.12)", row=1, col=1)
    fig.add_trace(go.Scatter(x=acc, y=ret, mode="lines+markers",
                             marker=dict(size=7, color=ind, colorscale="Viridis", cmin=0,
                                         cmax=float(np.nanmax(ind)) or 1.0,
                                         colorbar=dict(title="individ.<br>ret×acc", len=0.9, x=0.44),
                                         line=dict(width=0.5, color="#334155")),
                             line=dict(color="#cbd5e1", width=1), showlegend=False,
                             hovertext=[f"T={t:.0f}K" for t in arc.axes["temperature"]], hoverinfo="text"), row=1, col=1)
    fig.add_trace(go.Scatter(x=[acc[ipk]], y=[ret[ipk]], mode="markers+text", text=["viable<br>optimum"],
                             textposition="bottom left", textfont=dict(size=9, color=_INK),
                             marker=dict(symbol="star", size=16, color=_AMBER, line=dict(width=1.1, color=_INK)),
                             showlegend=False), row=1, col=1)
    for x, y, t, col in [(0.26, 0.9, "too closed<br>(starves)", _SLATE),
                         (0.8, 0.28, "too open<br>(leaks)", _RUST),
                         (0.8, 0.9, "viable", _TEAL)]:
        fig.add_annotation(x=x, y=y, text=t, showarrow=False, font=dict(size=10, color=col), row=1, col=1)
    fig.update_xaxes(title_text="access (gradient import)", range=[0, 1.02], row=1, col=1)
    fig.update_yaxes(title_text="retention (chemistry held)", range=[0, 1.02], row=1, col=1)
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
    fig.add_annotation(x=0.35, y=float(mix.max()), text="seawater", showarrow=False, yshift=8,
                       font=dict(size=9, color=_SLATE), row=1, col=2)
    fig.update_xaxes(title_text="ionic strength (M)", row=1, col=2)
    fig.update_yaxes(title_text="co-surfactant fraction", row=1, col=2)

    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=70, r=20),
                                      showlegend=False))
    cap = ("A membrane is useful only in the viable window &mdash; permeable enough to import the "
           "gradient, tight enough to hold its chemistry. Mixed amphiphiles lift the salt ceiling so "
           "vesicles survive at seawater salt (Jordan 2019).")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "A boundary that retains without isolating"),
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
        from .phase_maps import protocell_feasibility_map, protocell_retention_access_arc
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

    def col(rows, k):
        return [float(r.get(k, 0.0)) for r in rows]

    t = [r.get("global_time", i) for i, r in enumerate(fav)]
    ext = col(fav, "external_power")
    intl = col(fav, "internal_power")
    frac_ext = [e / (e + n) if (e + n) > 1e-30 else 0.0 for e, n in zip(ext, intl)]
    frac_int = [1.0 - f if (e + n) > 1e-30 else 0.0 for f, e, n in zip(frac_ext, ext, intl)]
    vext = col(fav, "electric_potential")

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
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
    fig.update_xaxes(title_text="time (s)", row=1, col=1)
    # --- right: survivors, efficient vs weak pump ---
    fig.add_trace(go.Scatter(x=t, y=col(fav, "survivors"), mode="lines", name="efficient pump",
                             line=dict(color=_TEAL, width=3)), row=1, col=2)
    fig.add_trace(go.Scatter(x=[r.get("global_time", i) for i, r in enumerate(weak)],
                             y=col(weak, "survivors"), mode="lines", name="weak-pump control",
                             line=dict(color=_RUST, width=2.5, dash="dash")), row=1, col=2)
    fig.add_trace(go.Scatter(x=t, y=col(fav, "internalization"), mode="lines", name="internalization",
                             line=dict(color=_SLATE, width=1.5, dash="dot")), row=1, col=2)
    fig.update_yaxes(title_text="surviving population fraction", range=[-0.02, 1.05], row=1, col=2)
    fig.update_xaxes(title_text="time (s)", row=1, col=2)

    fig.update_layout(**S.base_layout(
        height=450, width=960, margin=dict(t=48, b=60, l=70, r=60),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center", font=dict(size=9))))
    cap = ("As the geochemical gradient collapses, selection shifts the useful free energy from external "
           "(amber) to internally pumped (teal). The efficient pump internalizes and survives; the weak "
           "pump cannot beat its cost and collapses &mdash; the gradient becomes a resource, not the "
           "scaffold.")
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

        from .composites.bioenergetic_internalization import bioenergetic_internalization
        from .core import build_core
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
        from .phase_maps import carbon_fixation_phase_map
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
    cap = ("All three views at once. <b>World</b>: individuals inherit a chemical phenotype φ at fission "
           "into a real lineage tree. <b>Mechanism</b>: the template (RNA-like) module holds function only "
           "above the Eigen error threshold (white line); the non-heritable control loses the parent&harr;"
           "offspring correlation (flat cloud) and collapses. <b>Decision</b>: compositional / hybrid "
           "heredity persist at ANY length &mdash; heredity need not presume a long, high-fidelity template.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Heredity as an inherited lineage"),
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
        from .heredity.lineage import simulate_lineage
        from .phase_maps import heredity_error_threshold_map
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


def metacommunity_phase_figure(res, *, title=None) -> str:
    """og-07 Decision view: where cross-feeding robustness EMERGES. **Left**: the
    metacommunity-robustness landscape over (cross-feeding exchange_rate × inter-
    compartment diversity) with the emergence boundary (robustness == threshold) and
    the operating point; robustness rises only in the high-diversity, sufficient-
    exchange corner. **Right**: the connected-vs-isolated contrast — the redundancy
    GAIN (connected minus the isolated counterfactual) that connectivity builds, with
    the LUCA-overlap boundary contour overlaid (reported, not targeted). ``res`` is a
    SweepResult / grid view with ``robustness``, ``isolated_robustness``,
    ``capability_diversity`` and ``luca_overlap`` surfaces."""
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

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.13, shared_yaxes=True,
                        subplot_titles=("Where cross-feeding robustness emerges",
                                        "Connectivity builds redundancy (connected − isolated)"))
    # --- left: robustness landscape + emergence boundary ---
    fig.add_trace(go.Contour(x=div, y=ex, z=rob, colorscale="Viridis", ncontours=14,
                             zmin=0.0, zmax=1.0,
                             colorbar=dict(title="robustness<br>(redundancy)", len=0.9, x=0.44),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=1)
    fig.add_trace(go.Contour(x=div, y=ex, z=rob, showscale=False,
                             contours=dict(start=thr, end=thr, coloring="lines"),
                             line=dict(color="#f8fafc", width=2.4, dash="dash"),
                             hoverinfo="skip"), row=1, col=1)
    # --- right: the connected-vs-isolated redundancy gain (diverging), + LUCA boundary ---
    gmax = max(float(np.nanmax(np.abs(gain))), 0.1)
    fig.add_trace(go.Heatmap(x=div, y=ex, z=gain, colorscale="RdBu", zmid=0.0,
                             zmin=-gmax, zmax=gmax,
                             colorbar=dict(title="robustness<br>gain", len=0.9),
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

    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=70, r=20),
                                      showlegend=False))
    cap = ("A connected metacommunity develops functional redundancy a single compartment cannot &mdash; "
           "but only where diversity gives cross-feeding something to share AND exchange spreads it "
           "(dashed = emergence boundary). Right: the redundancy gain over the isolated counterfactual; "
           "black contours = overlap with the anaerobic LUCA reconstruction, a reported boundary, not a "
           "target.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Where cross-feeding robustness emerges"),
                   phase="Campaign VII", view="Decision", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class MetacommunityPhaseMap(Visualization):
    """og-07 Decision view: the cross-feeding metacommunity robustness-emergence
    boundary over (exchange_rate × diversity) + the connected-vs-isolated redundancy
    gain, with the anaerobic LUCA-overlap boundary overlaid. Renders from a persisted
    grid (``grid_json``) or computes a modest grid live."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign VII — where cross-feeding robustness emerges"},
        "grid_json": {"_type": "string", "_default": ""},
        "n_grid": {"_type": "integer", "_default": 12},
        "n_steps": {"_type": "integer", "_default": 40},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from .phase_maps import metacommunity_robustness_phase_map
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
        return {"html": metacommunity_phase_figure(res, title=self.config["title"])}


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
        rows=1, cols=2, horizontal_spacing=0.13, column_widths=[0.48, 0.52],
        subplot_titles=("Survival frontier (persistence vs support × innovation set)",
                        "Escape: persistence as geological support is withdrawn"))

    # --- left: the phase map + the survival frontier -----------------------------
    fig.add_trace(go.Heatmap(
        x=set_idx, y=support, z=Z, colorscale="Viridis", zmin=0, zmax=1,
        colorbar=dict(title="persist.", len=0.9, x=0.44),
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
    cap = ("As the geological reactor's support is withdrawn, only the full innovation set &mdash; "
           "internal pump + resource importer + heredity &mdash; persists off-gradient. The budget is "
           "co-limited (energy AND resources), so each single knockout collapses: the minimum robust set "
           "for autonomy is irreducible.")
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
        from .autonomy.off_gradient import decline_trajectory
        from .phase_maps import _INNOVATION_SETS, off_gradient_phase_map
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
        column_widths=[0.56, 0.44] if have_bars else [1.0],
        horizontal_spacing=0.14,
        subplot_titles=(["Carbon-fixation gate over (H₂ × catalyst)",
                         "Every vent-specific gate rejects the control"]
                        if have_bars else ["Carbon-fixation gate over (H₂ × catalyst)"]))

    fig.add_trace(go.Contour(
        x=h2, y=cat, z=z, colorscale="Viridis", ncontours=16,
        colorbar=dict(title="log₁₀ peak<br>net C-flux", len=0.9, x=0.49 if have_bars else 1.02),
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
    cap = ("The gates pass only in the vent corner (sustained H₂ AND a Fe/Ni/S catalytic interface). "
           "Generic non-vent chemistry sits below every threshold &mdash; the discriminating gates REJECT "
           "this non-vent control, so they measure the vent mechanism, not generic nonequilibrium "
           "chemistry.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Vent-specificity of the gates"),
                   phase="Adversarial control", view="Decision", tier="null_control",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


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
        from .phase_maps import vent_specificity_map
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
                                 text=["favourable<br>operating point"], textposition="bottom center",
                                 textfont=dict(size=9, color=_INK),
                                 marker=dict(symbol="star", size=14, color=_AMBER,
                                             line=dict(width=1.1, color=_INK)), showlegend=False), row=1, col=c)
        fig.update_xaxes(title_text="FeS catalyst activity", row=1, col=c)
    fig.update_yaxes(type="log", title_text="nitrate supply (M/s)", row=1, col=1)

    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=75, r=20),
                                      showlegend=False))
    cap = ("Reduced nitrogen keeps pace with carbon only where the nitrate feed is sufficient AND the FeS "
           "catalyst is active (dashed = keeps-pace boundary, "
           f"C:N = {thr:.0f}). Above the feed/activity frontier the C:N supply ratio blows up and nitrogen "
           "&mdash; not carbon or energy &mdash; becomes limiting first. The no-FeS / no-H2 controls sit "
           "off-scale at zero production.")
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
        from .phase_maps import nitrogen_assimilation_phase_map
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
    cap = ("Reactive P is available only in a bounded region &mdash; enough pore enrichment that "
           "condensation/activation outpace precipitation. Dashed = availability threshold (production = "
           "loss); dotted amber = the enrichment at which the same og-03 pore co-concentrates carbon. "
           "PASS = right of both; left of the dashed line phosphate precipitates before it is useful.")
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
        from .phase_maps import phosphorus_availability_map
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
    fig.add_annotation(x=eta.min(), y=bond, xanchor="left", yanchor="bottom",
                       text=f"{carrier} bond ({bond:.0f} kJ/mol) — drive must clear it",
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
    cap = ("A pre-ATP carrier is only a currency where the geochemical drive clears the carrier bond "
           "(red dotted gate) AND the coupling is efficient enough to hold it charged against load + "
           "hydrolysis (dashed = viability boundary). Right: the fraction of geochemical free energy that "
           "becomes transferable usable work &mdash; the rest is dissipated. No-coupling / no-drive "
           "controls sit at zero (ablations).")
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
        from .phase_maps import proto_energetics_map
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

    def col(k):
        return [float(r.get(k, 0.0)) for r in rows]

    t = [r.get("global_time", i) for i, r in enumerate(rows)]
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
    fig.update_xaxes(title_text="time (s)", row=1, col=1)
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
    fig.update_xaxes(title_text="time (s)", row=1, col=2)

    fig.update_layout(**S.base_layout(
        height=450, width=960, margin=dict(t=48, b=60, l=70, r=60),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center", font=dict(size=9))))
    cap = ("Every kilojoule of tapped geochemical free energy is accounted: a bounded fraction is captured "
           "as transferable currency (teal &mdash; delivered work plus the pool still charged), the rest "
           "dissipated (uncoupled drive, discharge loss, hydrolysis). Right: input = work + stored + "
           "dissipated, held to machine precision &mdash; free-energy accounting is the stage's "
           "conservation invariant.")
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

        from .composites.proto_energetics import proto_energetics
        from .core import build_core
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
    cap = ("A protocell's chemistry changes its physical fate: product accumulation &rarr; osmotic "
           "pressure &rarr; solvent influx &rarr; volume growth &rarr; division. Sustained net growth "
           f"leading to DIVISION is a BOUNDED viable band ({viable_frac * 100:.0f}% of the grid, dashed "
           "boundary) &mdash; too permeable starves (the product leaks before the osmotic pressure can "
           "build), too impermeable lyses (the pressure bursts the membrane). Physical selection without "
           "an abstract fitness score.")
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
        from .phase_maps import growth_division_map
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
    """og-00 Decision view: the Lost City habitability window over (olivine reaction
    rate × flow velocity). **Left:** settled outlet temperature (°C) with the Lost City
    T-window edges (40 / 91 °C) dashed and the too-hot FAIL region shaded; **right:**
    settled outlet pH with the pH-window edges (9.0 / 10.8). The bold teal contour on
    BOTH panels is the combined habitability PASS boundary (inside the T AND pH window
    with a positive H₂ flux). ``res`` is the vent_habitability_phase_map SweepResult."""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    olv = np.asarray(res.axes["olivine_rate"], float)        # y
    flow = np.asarray(res.axes["flow_velocity"], float)      # x (log)
    T = np.asarray(res.surfaces["temperature_C"], float)     # [olivine, flow]
    pH = np.asarray(res.surfaces["pH"], float)
    hab = np.nan_to_num(np.asarray(res.surfaces["habitable"], float), nan=0.0)
    win = res.meta.get("window", {})
    t_lo, t_hi = win.get("T_C", [40.0, 91.0])
    ph_lo, ph_hi = win.get("pH", [9.0, 10.8])
    op = res.meta.get("operating_point", {})
    op_o = float(op.get("olivine_rate", 0.15)); op_f = float(op.get("flow_velocity", 1.0e-3))
    # over-heated / out-of-range points (NaN) read as "too hot" and "fail-pH".
    t_cap = max(float(np.nanmax(T)) if np.isfinite(np.nanmax(T)) else 120.0, t_hi + 40.0)
    T_disp = np.where(np.isnan(T), t_cap, T)
    pH_disp = np.where(np.isnan(pH), ph_lo - 2.0, pH)

    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.12,
                        subplot_titles=("Settled outlet temperature (°C)",
                                        "Settled outlet pH"))
    # --- left: temperature landscape + T-window edges + PASS boundary ---
    fig.add_trace(go.Contour(x=flow, y=olv, z=T_disp, colorscale="Inferno", ncontours=16,
                             colorbar=dict(title="outlet T<br>(°C)", len=0.9, x=0.44),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.25)")), row=1, col=1)
    for edge in (t_lo, t_hi):
        fig.add_trace(go.Contour(x=flow, y=olv, z=T_disp, showscale=False,
                                 contours=dict(start=edge, end=edge, coloring="lines"),
                                 line=dict(color="#e2e8f0", width=1.6, dash="dot"),
                                 hoverinfo="skip"), row=1, col=1)
    # --- right: pH landscape + pH-window edges ---
    fig.add_trace(go.Contour(x=flow, y=olv, z=pH_disp, colorscale="Viridis", ncontours=16,
                             colorbar=dict(title="outlet<br>pH", len=0.9),
                             contours=dict(showlabels=True, labelfont=dict(size=9, color="white")),
                             line=dict(width=0.4, color="rgba(255,255,255,0.25)")), row=1, col=2)
    for edge in (ph_lo, ph_hi):
        fig.add_trace(go.Contour(x=flow, y=olv, z=pH_disp, showscale=False,
                                 contours=dict(start=edge, end=edge, coloring="lines"),
                                 line=dict(color="#e2e8f0", width=1.6, dash="dot"),
                                 hoverinfo="skip"), row=1, col=2)
    # the combined habitability PASS boundary + operating point on both panels.
    for c in (1, 2):
        fig.add_trace(go.Contour(x=flow, y=olv, z=hab, showscale=False,
                                 contours=dict(start=0.5, end=0.5, coloring="lines"),
                                 line=dict(color=_TEAL, width=2.8, dash="dash"),
                                 hoverinfo="skip"), row=1, col=c)
        fig.add_trace(go.Scatter(x=[op_f], y=[op_o], mode="markers+text",
                                 text=["baseline<br>(51 °C, pH 9.4)"], textposition="top center",
                                 textfont=dict(size=9, color=_INK),
                                 marker=dict(symbol="star", size=15, color=_AMBER,
                                             line=dict(width=1.2, color=_INK)), showlegend=False), row=1, col=c)
        fig.update_xaxes(type="log", title_text="flow velocity (m/s)", row=1, col=c)
    fig.update_yaxes(title_text="olivine reaction rate (mol/step)", row=1, col=1)

    fig.update_layout(**S.base_layout(height=450, width=960, margin=dict(t=48, b=60, l=72, r=20),
                                      showlegend=False))
    cap = ("The real PHREEQC + FiPy vent settles inside the Lost City field window (teal dashed = "
           "habitability PASS) only in a bounded band: enough serpentinization to drive H₂ + alkalinity, "
           "slow enough flow to hold 40&ndash;91 °C / pH 9.0&ndash;10.8. Too fast flushes it cold; too "
           "much reaction at low flow over-heats past the window &mdash; the baseline (&starf;) sits "
           "safely inside.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The Lost City habitability window"),
                   phase="Campaign 0", view="Decision", tier="reproduction",
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
        from .phase_maps import vent_habitability_phase_map
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

    def col(k):
        return [float(r.get(k, 0.0)) for r in rows]

    t = [r.get("global_time", i) for i, r in enumerate(rows)]
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
    fig.update_xaxes(title_text="time (s)", row=1, col=1)
    # --- right: H2 + alkalinity pools + H2 flux (secondary) ---
    fig.add_trace(go.Scatter(x=t, y=[v * 1e3 for v in h2], mode="lines", name="dissolved H₂ (mM)",
                             line=dict(color=_INK, width=2.6)), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=[v * 1e3 for v in alk], mode="lines", name="alkalinity (mmol/L)",
                             line=dict(color=_AMBER, width=2.4)), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=t, y=[v * 1e6 for v in h2_flux], mode="lines", name="H₂ source flux (µmol/s)",
                             line=dict(color=_TEAL, width=2.0, dash="dot")), row=1, col=2, secondary_y=True)
    fig.update_yaxes(title_text="pool (mM / mmol·L⁻¹)", row=1, col=2, secondary_y=False)
    fig.update_yaxes(title_text="H₂ source flux (µmol/s)", row=1, col=2, secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text="time (s)", row=1, col=2)

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

        from .composites.vent_reactor import serpentinizing_vent_reactor
        from .core import build_core
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
        "A dilute vent feed localizes where the accumulation Péclet crosses the frontier (white dashed, "
        f"Pe &asymp; {pe_thr:.0f}) &mdash; the <b>graded quantity is the Péclet, not the precise fold</b>. "
        "A long, tight pore traps; an open / short pore washes through. The reduced trap's fold-enrichment "
        "(left) rises steeply with length, but the teal dotted line marks the resolvable Péclet "
        f"(&asymp; {pe_resolvable:.0f}): beyond it the favourable trap (&starf;) sits in the solver-sensitive "
        "region where the reduced column over-extrapolates the resolved FEM. Localization is robust; the "
        "extreme fold is not. See the FiPy&harr;FEM solver-sensitivity Decision view."
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
        from .phase_maps import pore_localization_map
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
    fig.add_annotation(x=max(pe), y=fem_sat, text=f"resolved field saturates &asymp; {fem_sat:.0f}&times;",
                       showarrow=False, yshift=-14, xanchor="right",
                       font=dict(size=10, color=_TEAL, family=S.FONT_STACK))
    # the default Baaske-favorable pore (the strongest-Pe point) — the retired headline
    fig.add_annotation(x=pe[-1], y=fipy[-1], text=f"Baaske-favorable pore<br>reduced column &asymp; {fipy[-1]:.0e}&times;",
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
    cap = ("A viable boundary at the operating point ({:.0f} vesicles): the membrane (grey) holds internal "
           "chemistry (teal, retention {:.2f}) while staying permeable enough to import the external "
           "gradient (amber arrows, access {:.2f}). Individuality = retention &times; access = {:.2f} "
           "&mdash; a boundary that retains WITHOUT isolating.").format(viable, retention, access, individ)
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The compartment and the gradient"),
                   phase="Campaign IV", view="World", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


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

        from .composites.mixed_amphiphile_protocell import mixed_amphiphile_protocell
        from .core import build_core
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
    cap = ("As the external gradient collapses to its floor, a lineage persists either by riding a floor "
           "that never falls too far OR by internalizing &mdash; but internalizing only pays above the "
           f"Sojo cost line (η≈{eff_sojo:.2f}, red). The low-floor / low-efficiency corner goes extinct. "
           "Right: only an efficient pump truly OWNS its energy (white dashed = internalization > 0.5), "
           "independent of the floor.")
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
        from .phase_maps import bioenergetic_survival_map
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
        rows=2, cols=2, column_widths=[0.52, 0.48], row_heights=[0.5, 0.5],
        horizontal_spacing=0.1, vertical_spacing=0.15,
        specs=[[{"rowspan": 2}, {}], [None, {}]],
        subplot_titles=("World — the connected metacommunity (nodes = pore compartments)",
                        "Mechanism — connectivity builds redundancy",
                        "Decision — where cross-feeding robustness emerges"))

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
                    colorbar=dict(title="functional<br>breadth", len=0.45, y=0.78, x=0.46, thickness=10),
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
    fig.add_annotation(x=exx.max(), y=iso, xref="x2", yref="y2", xanchor="right", yanchor="bottom",
                       text=f"isolated counterfactual ({iso:.2f})", showarrow=False,
                       font=dict(size=9, color=_SLATE))
    fig.add_hline(y=thr, line=dict(color=_INK, width=1, dash="dot"), row=1, col=2)
    fig.add_annotation(x=exx.min(), y=thr + 0.02, xref="x2", yref="y2", xanchor="left", yanchor="bottom",
                       text=f"emergence threshold ({thr:.1f})", showarrow=False,
                       font=dict(size=8.5, color=_INK))
    fig.add_hline(y=luca, line=dict(color=_AMBER, width=2, dash="dot"), row=1, col=2)
    fig.add_annotation(x=exx.max(), y=luca, xref="x2", yref="y2", xanchor="right", yanchor="top",
                       text=f"LUCA-core overlap boundary ({luca:.2f}) — reported, not a target",
                       showarrow=False, font=dict(size=8.5, color=_AMBER))
    fig.update_xaxes(title_text="cross-feeding exchange rate (connectivity)", row=1, col=2)
    fig.update_yaxes(title_text="metacommunity robustness", range=[0, 1.02], row=1, col=2)

    # --- Decision: the (exchange × parasite_load) robustness phase map ---------
    e_axis = np.asarray(phase.axes["exchange_rate"], float)
    p_axis = np.asarray(phase.axes["parasite_load"], float)
    Z = np.asarray(phase.surfaces["robustness"], float)        # [exchange, parasite]
    fig.add_trace(go.Contour(
        x=p_axis, y=e_axis, z=Z, colorscale="Viridis", zmin=0.0, zmax=1.0, ncontours=14,
        colorbar=dict(title="robustness<br>(redundancy)", len=0.45, y=0.22, x=1.0, thickness=10),
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
    cap = ("All three views at once. Connectivity, not complexity, makes a population robust. <b>World</b>: "
           "cross-feeding + horizontal transfer across a pore network. <b>Mechanism</b>: redundant coverage "
           "climbs from the isolated floor (0.42) to 0.71 and approaches the anaerobic-LUCA overlap "
           "boundary. <b>Decision</b>: robustness emerges only in the well-connected, low-parasite corner "
           "(dashed = emergence boundary).")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Ecology before LUCA"),
                   phase="Campaign VII", view="Decision", tier="conceptual_demonstration",
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

        from .composites.cross_feeding_metacommunity import cross_feeding_metacommunity
        from .core import build_core
        from .ecology.metacommunity import CrossFeedingMetacommunityProcess, metacommunity_state
        from .phase_maps import ecology_robustness_parasite_map
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
        height=640, margin=dict(l=70, r=40, t=50, b=60),
        legend=dict(orientation="h", y=1.03, x=0.0, xanchor="left", font=dict(size=9))))
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
        from .autonomy.off_gradient import decline_trajectory, simulate_offgradient
        from .phase_maps import _INNOVATION_SETS, off_gradient_phase_map
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
    fig.add_annotation(x=0.02, y=0.96, xref="x domain", yref="y domain", xanchor="left",
                       text="og-01 formate gate (50 mM)", showarrow=False,
                       font=dict(size=8.5, color=_INK))
    fig.update_xaxes(title_text="time (s)", row=1, col=1)
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
        height=640, margin=dict(l=70, r=40, t=50, b=60), barmode="group",
        legend=dict(orientation="h", y=1.03, x=0.0, xanchor="left", font=dict(size=9))))
    cap = ("All three views at once. The SAME real composites with no sustained H₂, no Fe/Ni/S catalyst "
           "and no pore concentration are REJECTED by every discriminating gate, where the vent passes all "
           "five. <b>World</b>: vent is productive, the generic control is not. <b>Mechanism</b>: every "
           "gate rejects the generic control. <b>Decision</b>: the gate PASS region is the vent corner "
           "&mdash; a PASS certifies the vent mechanism, not generic nonequilibrium chemistry.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Vent-specificity of the gates"),
                   phase="Adversarial control", view="Decision", tier="null_control",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1100)


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
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from .adversarial import GENERIC_PARAMS, VENT_PARAMS
        from .composites.carbon_fixation import hydrothermal_carbon_fixation
        from .core import build_core
        from .phase_maps import vent_specificity_map
        from process_bigraph import Composite, gather_emitter_results

        core = build_core()
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

        # World trajectories: the real carbon-fixation composite, vent vs generic.
        tsteps = int(self.config["traj_steps"])

        def _traj(params):
            sim = Composite({"state": hydrothermal_carbon_fixation(core=core, **params)}, core=core)
            sim.run(float(tsteps))
            rows = gather_emitter_results(sim)[("emitter",)]
            t = [float(r.get("global_time", i)) for i, r in enumerate(rows)]
            form = [max(float(r.get("formate", 0.0)) * 1e3, 1e-12) for r in rows]
            return {"t": t, "formate_mM": form}
        trajectories = {"vent": _traj(VENT_PARAMS["carbon"]),
                        "generic": _traj(GENERIC_PARAMS["carbon"])}
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
        from .colocalization_map import colocalization_map
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
