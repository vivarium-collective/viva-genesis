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

_INK, _TEAL, _AMBER, _SLATE, _RUST = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c"


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

    ttl = title or "Campaign I — the carbon-fixation landscape"
    fig.update_layout(
        title=dict(text=(f"<b>{ttl}</b><br><span style='font-size:12px;color:{_SLATE}'>"
                         "Where geological free energy sustains reduced-carbon production "
                         "(open-flow vent reactor). Dark = productive region fails; the "
                         "no-gradient / no-catalyst / no-H₂ controls sit off-scale at zero."
                         "</span>"), x=0.5, xanchor="center"),
        height=440, width=460 * len(panels), margin=dict(t=95, b=60, l=70, r=20),
        font=dict(family="system-ui, -apple-system, sans-serif", color=_INK),
        paper_bgcolor="white", plot_bgcolor="white",
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn",
                       config={"displayModeBar": False})


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

    ttl = title or "Campaign II — the protometabolic ignition landscape"
    fig.update_layout(
        title=dict(text=(f"<b>{ttl}</b><br><span style='font-size:12px;color:{_SLATE}'>"
                         "The rTCA network ignites in a bounded region — enough geological CO₂ in, "
                         "slow enough washout. Dashed line = the autocatalytic threshold (gain=1); "
                         "beyond it the loop cannot outpace dilution and the hub washes out.</span>"),
                   x=0.5, xanchor="center"),
        height=450, width=940, margin=dict(t=95, b=60, l=70, r=20),
        font=dict(family="system-ui, -apple-system, sans-serif", color=_INK),
        paper_bgcolor="white", plot_bgcolor="white")
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


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
                             text=[f"in pore<br>(×{enrichment:.0f} trap)"], textposition="top center",
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

    ttl = title or "Campaign III — localization makes the individual"
    fig.update_layout(
        title=dict(text=(f"<b>{ttl}</b><br><span style='font-size:12px;color:{_SLATE}'>"
                         f"A real thermophoretic pore concentrates the dilute vent feed ×{enrichment:.0f}, "
                         "lifting it across og-02's ignition threshold (dashed). The same chemistry stays "
                         "dead in the well-mixed ocean — the metabolizing individual is a product of "
                         "localization, not of new reactions.</span>"), x=0.5, xanchor="center"),
        height=450, width=960, margin=dict(t=100, b=60, l=70, r=20),
        legend=dict(orientation="h", y=1.02, x=1.0, xanchor="right", font=dict(size=10)),
        font=dict(family="system-ui, -apple-system, sans-serif", color=_INK),
        paper_bgcolor="white", plot_bgcolor="white")
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


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
                             colorbar=dict(title="individ.", len=0.9),
                             line=dict(width=0.4, color="rgba(255,255,255,0.3)")), row=1, col=2)
    fig.add_vline(x=0.35, line=dict(color="#f8fafc", width=1.5, dash="dot"), row=1, col=2)
    fig.add_annotation(x=0.35, y=float(mix.max()), text="seawater", showarrow=False, yshift=8,
                       font=dict(size=9, color=_SLATE), row=1, col=2)
    fig.update_xaxes(title_text="ionic strength (M)", row=1, col=2)
    fig.update_yaxes(title_text="co-surfactant fraction", row=1, col=2)

    ttl = title or "Campaign IV — a boundary that retains without isolating"
    fig.update_layout(
        title=dict(text=(f"<b>{ttl}</b><br><span style='font-size:12px;color:{_SLATE}'>"
                         "A membrane is useful only in the viable window — permeable enough to import "
                         "the gradient, tight enough to hold its chemistry. Mixed amphiphiles lift the "
                         "salt ceiling so vesicles survive at seawater salt (Jordan 2019).</span>"),
                   x=0.5, xanchor="center"),
        height=450, width=960, margin=dict(t=100, b=60, l=70, r=20),
        font=dict(family="system-ui, -apple-system, sans-serif", color=_INK),
        paper_bgcolor="white", plot_bgcolor="white")
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


class ProtocellPhaseMap(Visualization):
    """og-04 Decision view: the retention-access plane (3 regimes) + the salt-tolerance
    feasibility map (mixed amphiphiles lift the viable salt ceiling). Computed from
    sweeps of the real protocell composite."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign IV — a boundary that retains without isolating"},
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

    ttl = title or "Campaign V — the organism begins to own its energy"
    fig.update_layout(
        title=dict(text=(f"<b>{ttl}</b><br><span style='font-size:12px;color:{_SLATE}'>"
                         "As the geochemical gradient collapses, selection shifts the useful free energy "
                         "from external (amber) to internally pumped (teal). The efficient pump internalizes "
                         "and survives; the weak pump cannot beat its cost and collapses — the gradient "
                         "becomes a resource, not the scaffold.</span>"), x=0.5, xanchor="center"),
        height=450, width=960, margin=dict(t=100, b=60, l=70, r=60),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center", font=dict(size=9)),
        font=dict(family="system-ui, -apple-system, sans-serif", color=_INK),
        paper_bgcolor="white", plot_bgcolor="white")
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


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

    ttl = title or "Campaign VI — heredity as an inherited lineage"
    fig.update_layout(
        title=dict(text=(f"<b>{ttl}</b><br><span style='font-size:12px;color:{_SLATE}'>"
                         "Individuals inherit a chemical phenotype at fission into a real lineage tree. The "
                         "template (RNA-like) module holds function only above the Eigen error threshold "
                         "(white line); the non-heritable control loses the parent↔offspring correlation "
                         "(flat cloud) and collapses — while compositional / hybrid heredity persist at ANY "
                         "length. Heredity need not presume a long, high-fidelity template.</span>")),
        height=620, margin=dict(l=60, r=70, t=110, b=55),
        legend=dict(orientation="h", y=1.02, x=0.56, font=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="white")
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


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

    ttl = title or "Campaign VII — where cross-feeding robustness emerges"
    fig.update_layout(
        title=dict(text=(f"<b>{ttl}</b><br><span style='font-size:12px;color:{_SLATE}'>"
                         "A connected metacommunity develops functional redundancy a single compartment "
                         "cannot — but only where diversity gives cross-feeding something to share AND "
                         "exchange spreads it (dashed = emergence boundary). Right: the redundancy gain over "
                         "the isolated counterfactual; black contours = overlap with the anaerobic LUCA "
                         "reconstruction, a reported boundary, not a target.</span>"),
                   x=0.5, xanchor="center"),
        height=450, width=960, margin=dict(t=100, b=60, l=70, r=20),
        font=dict(family="system-ui, -apple-system, sans-serif", color=_INK),
        paper_bgcolor="white", plot_bgcolor="white")
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


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

    ttl = title or "Campaign VIII — the survival frontier off the gradient"
    fig.update_layout(
        title=dict(text=(f"<b>{ttl}</b><br><span style='font-size:12px;color:{_SLATE}'>"
                         "As the geological reactor's support is withdrawn, only the full innovation "
                         "set — internal pump + resource importer + heredity — persists off-gradient. "
                         "The budget is co-limited (energy AND resources), so each single knockout "
                         "collapses: the minimum robust set for autonomy is irreducible.</span>"),
                   x=0.5, xanchor="center"),
        height=460, width=980, margin=dict(t=105, b=60, l=75, r=20),
        legend=dict(orientation="h", y=-0.2, x=0.74, xanchor="center", font=dict(size=9)),
        font=dict(family="system-ui, -apple-system, sans-serif", color=_INK),
        paper_bgcolor="white", plot_bgcolor="white")
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


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

    ttl = title or "Adversarial control — vent-specificity of the gates"
    fig.update_layout(
        title=dict(text=(f"<b>{ttl}</b><br><span style='font-size:12px;color:{_SLATE}'>"
                         "The gates pass only in the vent corner (sustained H₂ AND a Fe/Ni/S "
                         "catalytic interface). Generic non-vent chemistry sits below every "
                         "threshold — the gates measure the vent mechanism, not generic "
                         "nonequilibrium chemistry.</span>"), x=0.5, xanchor="center"),
        height=470, width=980 if have_bars else 560, margin=dict(t=100, b=60, l=80, r=30),
        font=dict(family="system-ui, -apple-system, sans-serif", color=_INK),
        paper_bgcolor="white", plot_bgcolor="white")
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


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
