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


class _ResultView:
    """Minimal duck-typed SweepResult for rendering from a persisted grid."""

    def __init__(self, axis_order, axes, surfaces, meta):
        self.axis_order, self.axes, self.surfaces, self.meta = axis_order, axes, surfaces, meta
