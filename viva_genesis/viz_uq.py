"""UQ-layer figures — the Phase-1 environmental-calibration posterior.

Renders from the persisted ensemble + report artifacts written by
``og-cal-vent-environment/sims/compute_vent_environment_ensemble.py`` (the real
PHREEQC + FiPy ensemble is minutes of compute, so it is never recomputed at
page-load). Three panels: the prior draws in the (flow x olivine-rate) plane
coloured by their fate under conditioning (headline class); the per-class
Feasibility / Robustness bars with the cross-class agreement; and the Morris
screening (mu*) of the prior per conditioning readout.
"""

from __future__ import annotations

import json
import os

import numpy as np
from process_bigraph.visualization import Visualization

_INK, _TEAL, _AMBER, _SLATE, _RUST = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c"
_FATE_COLORS = {"failed": _SLATE, "inconsistent": "#cbd5e1", "consistent": _AMBER, "viable": _TEAL}


def _resolve(path: str) -> str | None:
    if not path:
        return None
    if os.path.isabs(path) and os.path.exists(path):
        return path
    here = os.path.abspath(os.getcwd())
    for _ in range(8):
        cand = os.path.join(here, path)
        if os.path.exists(cand):
            return cand
        if os.path.exists(os.path.join(here, "workspace.yaml")):
            break
        here = os.path.dirname(here)
    return path if os.path.exists(path) else None


def _fates(rows, observations, requirements):
    from .uq.calibration import Observation, consistency_mask
    obs = [Observation(**{k: v for k, v in o.items() if k in Observation.__dataclass_fields__}) for o in observations]
    req = [Observation(**{k: v for k, v in o.items() if k in Observation.__dataclass_fields__}) for o in requirements]
    ok = np.array([bool(r.get("ok")) for r in rows])
    cons = consistency_mask(rows, obs) & ok
    viable = cons & (consistency_mask(rows, req) if req else True)
    fate = np.where(~ok, "failed", np.where(viable, "viable", np.where(cons, "consistent", "inconsistent")))
    return fate


def vent_environment_posterior_figure(ensemble: dict, report: dict, *, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    cond = report["conditioning"]
    rep = report["report"]
    labels = list(ensemble["outcomes"])
    head = rep["meta"].get("headline_class", labels[0])
    rows = ensemble["outcomes"][head]
    draws = ensemble["draws"]
    fate = _fates(rows, cond["observations"], cond["requirements"])

    fig = make_subplots(
        rows=1, cols=3, horizontal_spacing=0.09, column_widths=[0.42, 0.28, 0.30],
        subplot_titles=(f"Prior draws and their fate under conditioning ({head.split('+')[-1]})",
                        "Feasibility and robustness per model class",
                        "Morris screening of the prior (mu*)"))
    # --- left: prior scatter coloured by fate ---
    fv = np.array([d["flow_velocity"] for d in draws]); ol = np.array([d["olivine_rate"] for d in draws])
    h2 = np.array([float(r.get("dissolved_H2_mmol_kg") or np.nan) for r in rows])
    t = np.array([float(r.get("settled_temperature_C") or np.nan) for r in rows])
    for name in ("failed", "inconsistent", "consistent", "viable"):
        m = fate == name
        if not m.any():
            continue
        fig.add_trace(go.Scatter(
            x=fv[m], y=ol[m], mode="markers", name=name,
            marker=dict(size=11 if name == "viable" else 8, color=_FATE_COLORS[name],
                        line=dict(width=1, color=_INK) if name == "viable" else None),
            text=[f"H2 {a:.2f} mM, T {b:.1f} C" for a, b in zip(h2[m], t[m])],
            hovertemplate="flow %{x:.2e} m/s<br>olivine_rate %{y:.3f}<br>%{text}<extra>" + name + "</extra>"),
            row=1, col=1)
    fig.update_xaxes(type="log", title_text="flow_velocity (m/s)", row=1, col=1)
    fig.update_yaxes(type="log", title_text="olivine_rate (reaction extent / step)", row=1, col=1)
    # --- middle: per-class bars ---
    pcs = cond["per_class"]
    short = [l.split("spatial_transport=")[-1] for l in labels]
    fig.add_trace(go.Bar(x=short, y=[pcs[l]["p_consistent"] for l in labels], name="P(consistent | prior)",
                         marker_color=_AMBER), row=1, col=2)
    fig.add_trace(go.Bar(x=short, y=[pcs[l]["p_viable_given_consistent"] for l in labels],
                         name="P(viable | consistent)", marker_color=_TEAL), row=1, col=2)
    agree = cond["cross_class"]["viable"]["agreement"]
    fig.add_annotation(xref="x2 domain", yref="y2 domain", x=0.5, y=1.02, showarrow=False,
                       text=f"cross-class agreement on viability: {agree:.2f}", font=dict(size=11, color=_INK))
    fig.update_yaxes(range=[0, 1.05], title_text="fraction", row=1, col=2)
    # --- right: Morris mu* per readout ---
    morris = ensemble.get("morris") or {}
    ros = morris.get("readouts") or {}
    if ros:
        names = next(iter(ros.values()))["names"]
        for i, (ro, res) in enumerate(ros.items()):
            mu = np.array([res["mu_star"].get(n, np.nan) for n in names], dtype=float)
            scale = np.nanmax(mu) if np.nanmax(mu) > 0 else 1.0
            fig.add_trace(go.Bar(y=names, x=mu / scale, orientation="h", name=f"mu* ({ro}) / max",
                                 marker_color=[_TEAL, _AMBER, _RUST][i % 3], opacity=0.85), row=1, col=3)
        fig.update_xaxes(title_text="normalised elementary effect", row=1, col=3)
    else:
        fig.add_annotation(xref="x3 domain", yref="y3 domain", x=0.5, y=0.5, showarrow=False,
                           text="no Morris screening in the artifact", font=dict(color=_SLATE))
    fig.update_layout(
        title=title or "Phase 1 — Lost-City-conditioned vent ensemble (real PHREEQC + FiPy)",
        barmode="group", height=470, margin=dict(l=60, r=20, t=90, b=60),
        legend=dict(orientation="h", y=-0.2), plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, Helvetica, Arial, sans-serif", color=_INK, size=12),
    )
    head_md = rep.get("headline", "")
    return (fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
            + f"<p style='font: 12px Inter, sans-serif; color:{_SLATE}; margin:6px 0'>{head_md}</p>")


class VentEnvironmentPosterior(Visualization):
    """Phase-1 Decision view: the Lost-City-conditioned posterior of the vent world
    (prior draws and their fate, per-class feasibility/robustness, Morris screening)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Phase 1 — environmental calibration posterior"},
        "ensemble_json": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        ens_path = _resolve(str(self.config.get("ensemble_json", "") or ""))
        rep_path = _resolve(str(self.config.get("report_json", "") or ""))
        if not ens_path or not rep_path:
            return {"html": "<p>ensemble / report artifacts not found — run "
                            "sims/compute_vent_environment_ensemble.py first.</p>"}
        with open(ens_path) as f:
            ensemble = json.load(f)
        with open(rep_path) as f:
            report = json.load(f)
        return {"html": vent_environment_posterior_figure(ensemble, report, title=self.config["title"])}
