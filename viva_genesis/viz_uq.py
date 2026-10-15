"""UQ-layer figures — the Phase-1 posterior and the Phase-2 mechanism map.

Phase 1 (``VentEnvironmentPosterior``) renders from the persisted ensemble +
report artifacts written by
``og-cal-vent-environment/sims/compute_vent_environment_ensemble.py`` (the real
PHREEQC + FiPy ensemble is minutes of compute, so it is never recomputed at
page-load). Three panels: the prior draws in the (flow x olivine-rate) plane
coloured by their fate under conditioning (headline class); the per-class
Feasibility / Robustness bars with the cross-class agreement; and the Morris
screening (mu*) of the prior per conditioning readout.

Phase 2 (``ElectrochemistryMechanismMap``, ``ElectrochemistryPolarization``)
renders the limitation label of every swept point per carbon-fixation class
and where the classes agree (from the committed mechanism-map artifact of
``og-01-cal-electrochemistry``), and the galvanic cell's polarization curve
computed live from the Butler-Volmer class's own ``solve_cell``.
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


# --------------------------------------------------------------------------- #
# Phase 2 — the electrochemical mechanism map and the galvanic-cell polarization
# --------------------------------------------------------------------------- #
_LABEL_ORDER = ("thermodynamic", "electrical", "catalytic", "transport", "unresolved")
_LABEL_COLORS = {"thermodynamic": "#7c3aed", "electrical": _AMBER, "catalytic": _TEAL,
                 "transport": _RUST, "unresolved": "#cbd5e1"}


def _nearest_index(values, target) -> int:
    arr = np.asarray(values, dtype=float)
    with np.errstate(divide="ignore"):
        la, lt = np.log10(np.where(arr > 0, arr, np.nan)), (np.log10(target) if target > 0 else np.nan)
    if np.isfinite(lt) and np.isfinite(la).all():
        return int(np.nanargmin(np.abs(la - lt)))
    return int(np.argmin(np.abs(arr - target)))


def _label_grid(labels_4d, axis_order, fixed: dict, free: tuple[str, str]):
    """Slice the 4-D label array down to a 2-D (free[1] rows x free[0] cols) grid."""
    arr = np.asarray(labels_4d, dtype=object)
    taker = []
    for ax in axis_order:
        taker.append(slice(None) if ax in free else fixed[ax])
    sub = arr[tuple(taker)]
    i0, i1 = [a for a in axis_order if a in free].index(free[0]), [a for a in axis_order if a in free].index(free[1])
    return sub.T if i0 < i1 else sub


def electrochemistry_mechanism_map_figure(mmap: dict, report: dict, *, title: str = "",
                                          nominal: dict | None = None) -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    att = report["attribution"]
    classes = list(mmap["classes"])
    axes, order = mmap["axes"], list(mmap["axis_order"])
    nominal = dict(nominal or {"ph_vent": 9.5, "h2": 5.0e-3, "conductivity": 1.0e-3, "ni_fraction": 0.75})
    fixed = {ax: _nearest_index(axes[ax], nominal[ax]) for ax in order}
    code = {name: i for i, name in enumerate(_LABEL_ORDER)}
    colorscale = [[i / (len(_LABEL_ORDER) - 1), _LABEL_COLORS[n]] for i, n in enumerate(_LABEL_ORDER)]
    cross = att.get("cross_class") or {}

    panels = [(c, ("h2", "ph_vent")) for c in classes] + [("agreement", ("h2", "ph_vent"))]
    panels += [(c, ("conductivity", "ni_fraction")) for c in classes] + [("agreement", ("conductivity", "ni_fraction"))]
    titles = []
    for name, free in panels:
        where = ", ".join(f"{ax}={axes[ax][fixed[ax]]:.3g}" for ax in order if ax not in free)
        titles.append((f"{name} — limitation" if name != "agreement" else "classes agree?") + f"<br><sup>{where}</sup>")
    fig = make_subplots(rows=2, cols=3, subplot_titles=titles, horizontal_spacing=0.08, vertical_spacing=0.2)

    def add_panel(row, col, name, free):
        xs, ys = axes[free[0]], axes[free[1]]
        if name == "agreement":
            a, b = cross.get("classes", classes[:2])
            ga = _label_grid(mmap["labels"][a], order, fixed, free)
            gb = _label_grid(mmap["labels"][b], order, fixed, free)
            fa = _label_grid(mmap["favorable"][a], order, fixed, free).astype(float)
            fb = _label_grid(mmap["favorable"][b], order, fixed, free).astype(float)
            z = np.where(ga == gb, 1.0, 0.0)
            text = [[f"{a}: {ga[i][j]}<br>{b}: {gb[i][j]}" + ("<br>favorable in both" if fa[i][j] * fb[i][j] > 0 else "")
                     for j in range(len(xs))] for i in range(len(ys))]
            fig.add_trace(go.Heatmap(x=[f"{v:.3g}" for v in xs], y=[f"{v:.3g}" for v in ys], z=z, text=text,
                                     hovertemplate="%{x}, %{y}<br>%{text}<extra></extra>", zmin=0, zmax=1,
                                     colorscale=[[0, "#fde68a"], [1, "#99f6e4"]], showscale=False), row=row, col=col)
            fav = fa * fb
            for i in range(len(ys)):
                for j in range(len(xs)):
                    if fav[i][j] > 0:
                        fig.add_annotation(x=f"{xs[j]:.3g}", y=f"{ys[i]:.3g}", text="★", showarrow=False,
                                           font=dict(size=11, color=_INK), xref=f"x{(row - 1) * 3 + col}" if (row, col) != (1, 1) else "x",
                                           yref=f"y{(row - 1) * 3 + col}" if (row, col) != (1, 1) else "y")
        else:
            g = _label_grid(mmap["labels"][name], order, fixed, free)
            fv = _label_grid(mmap["favorable"][name], order, fixed, free).astype(float)
            z = np.vectorize(lambda s: code.get(str(s), code["unresolved"]))(g).astype(float)
            text = [[f"{g[i][j]}" + ("<br>favorable" if fv[i][j] > 0 else "") for j in range(len(xs))] for i in range(len(ys))]
            fig.add_trace(go.Heatmap(x=[f"{v:.3g}" for v in xs], y=[f"{v:.3g}" for v in ys], z=z, text=text,
                                     hovertemplate="%{x}, %{y}<br>%{text}<extra>" + name + "</extra>",
                                     zmin=0, zmax=len(_LABEL_ORDER) - 1, colorscale=colorscale, showscale=False),
                          row=row, col=col)
        fig.update_xaxes(title_text=free[0], row=row, col=col, type="category")
        fig.update_yaxes(title_text=free[1], row=row, col=col, type="category")

    for k, (name, free) in enumerate(panels):
        add_panel(k // 3 + 1, k % 3 + 1, name, free)
    # legend proxies
    for n in _LABEL_ORDER[:4]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=12, color=_LABEL_COLORS[n], symbol="square"),
                                 name=n), row=1, col=1)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=12, color="#99f6e4", symbol="square"),
                             name="labels agree"), row=1, col=1)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=12, color="#fde68a", symbol="square"),
                             name="labels differ"), row=1, col=1)
    agree_fav = cross.get("label_agreement_favorable")
    agree_all = cross.get("label_agreement_all")
    deferred = ", ".join(f"{k} ({v.split(';')[0]})" for k, v in (mmap.get("deferred_classes") or {}).items())
    sub = (f"label agreement: {agree_all:.2f} over all {cross.get('n_both_ok', 0)} points, "
           f"{(agree_fav if agree_fav is not None else float('nan')):.2f} over the {cross.get('n_favorable_both', 0)} points both classes call favorable (★)"
           + (f"; deferred: {deferred}" if deferred else ""))
    fig.update_layout(
        title=(title or "Phase 2 — electrochemical mechanism map") + f"<br><sup>{sub}</sup>",
        height=760, margin=dict(l=60, r=20, t=110, b=60), legend=dict(orientation="h", y=-0.12),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, Helvetica, Arial, sans-serif", color=_INK, size=12),
    )
    head = report.get("report", {}).get("headline", "")
    disc = report.get("decision_discipline") or []
    note = f"<p style='font: 12px Inter, sans-serif; color:{_SLATE}; margin:6px 0'>{head}</p>"
    if disc:
        note += f"<p style='font: 12px Inter, sans-serif; color:{_RUST}; margin:6px 0'>decision discipline: {'; '.join(disc)}</p>"
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False}) + note


def electrochemistry_polarization_figure(curve: dict, *, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    j = np.asarray(curve["j"], dtype=float)
    op = curve["operating_point"]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Cell voltage vs current density (loss partition)",
                                                        "Faradaic efficiency to carbon"),
                        horizontal_spacing=0.12)
    emf = float(op["emf"])
    fig.add_trace(go.Scatter(x=j, y=[emf] * len(j), mode="lines", name="emf (Nernst)",
                             line=dict(color=_SLATE, dash="dot")), row=1, col=1)
    eta_a, eta_c, ohm = (np.asarray(curve[k], dtype=float) for k in ("eta_anode", "eta_cathode", "ohmic"))
    fig.add_trace(go.Scatter(x=j, y=emf - eta_a, mode="lines", name="− anode activation", fill="tonexty",
                             line=dict(color=_TEAL)), row=1, col=1)
    fig.add_trace(go.Scatter(x=j, y=emf - eta_a - eta_c, mode="lines", name="− cathode activation", fill="tonexty",
                             line=dict(color="#0f766e")), row=1, col=1)
    fig.add_trace(go.Scatter(x=j, y=emf - eta_a - eta_c - ohm, mode="lines", name="− ohmic (mineral + ionic) = delivered",
                             fill="tonexty", line=dict(color=_AMBER)), row=1, col=1)
    fig.add_trace(go.Scatter(x=[op["j"]], y=[op["e_cathode"] - op["e_anode"]], mode="markers",
                             name=f"operating point ({op['limitation']}-limited)",
                             marker=dict(size=12, color=_RUST, line=dict(width=1, color=_INK))), row=1, col=1)
    fig.update_xaxes(type="log", title_text="current density (A/m²)", row=1, col=1)
    fig.update_yaxes(title_text="volt", row=1, col=1)
    fig.add_trace(go.Scatter(x=j, y=curve["faradaic_efficiency"], mode="lines", name="FE(j)", line=dict(color=_INK)),
                  row=1, col=2)
    fig.add_trace(go.Scatter(x=[op["j"]], y=[op["faradaic_efficiency"]], mode="markers", showlegend=False,
                             marker=dict(size=12, color=_RUST, line=dict(width=1, color=_INK))), row=1, col=2)
    fig.update_xaxes(type="log", title_text="current density (A/m²)", row=1, col=2)
    fig.update_yaxes(range=[0, 1.05], title_text="fraction", row=1, col=2)
    losses = op["losses"]
    sub = (f"j = {op['j']:.2e} A/m², emf {emf:.3f} V, FE {op['faradaic_efficiency']:.2f}; losses: "
           + ", ".join(f"{k} {v:.2f}" for k, v in losses.items()) + f"; circuit residual {op['iv_residual']:.1e}")
    fig.update_layout(title=(title or "Vent wall as a galvanic cell") + f"<br><sup>{sub}</sup>", height=430,
                      margin=dict(l=60, r=20, t=90, b=60), legend=dict(orientation="h", y=-0.25),
                      plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(family="Inter, Helvetica, Arial, sans-serif", color=_INK, size=12))
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


class ElectrochemistryMechanismMap(Visualization):
    """Phase-2 Decision view: the limitation label (thermodynamic / electrical /
    catalytic / transport) of every swept point per carbon-fixation class, and
    where the classes agree, from the committed mechanism-map artifact."""

    config_schema = {
        "title": {"_type": "string", "_default": "Phase 2 — electrochemical mechanism map"},
        "mechanism_map_json": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        map_path = _resolve(str(self.config.get("mechanism_map_json", "") or ""))
        rep_path = _resolve(str(self.config.get("report_json", "") or ""))
        if not map_path or not rep_path:
            return {"html": "<p>mechanism-map / report artifacts not found — run "
                            "sims/compute_electrochemistry_mechanism_map.py first.</p>"}
        with open(map_path) as f:
            mmap = json.load(f)
        with open(rep_path) as f:
            report = json.load(f)
        return {"html": electrochemistry_mechanism_map_figure(mmap, report, title=self.config["title"])}


class ElectrochemistryPolarization(Visualization):
    """Phase-2 Mechanism view: the Butler-Volmer galvanic cell's polarization curve
    at a chosen operating point — emf minus the anode / cathode activation and the
    ohmic drop, the operating current, and the faradaic efficiency — computed live
    from the same ``solve_cell`` the process runs (cheap: a scalar root solve)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Vent wall as a galvanic cell"},
        "ph_vent": {"_type": "float", "_default": 9.5},
        "ph_ocean": {"_type": "float", "_default": 6.0},
        "h2": {"_type": "float", "_default": 5.0e-3},
        "co2": {"_type": "float", "_default": 2.0e-3},
        "temperature": {"_type": "float", "_default": 373.15},
        "conductivity": {"_type": "float", "_default": 1.0e-3},
        "layer_thickness": {"_type": "float", "_default": 1.0e-3},
        "ni_fraction": {"_type": "float", "_default": 0.75},
        "formate": {"_type": "float", "_default": 0.0},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from .electrochemistry.butler_volmer import default_cell_kwargs, polarization_curve
        c = self.config
        kw = default_cell_kwargs(T=float(c["temperature"]), pH_vent=float(c["ph_vent"]), pH_ocean=float(c["ph_ocean"]),
                                 h2=float(c["h2"]), co2=float(c["co2"]), conductivity=float(c["conductivity"]),
                                 layer_thickness=float(c["layer_thickness"]), ni_fraction=float(c["ni_fraction"]),
                                 formate=float(c["formate"]))
        return {"html": electrochemistry_polarization_figure(polarization_curve(**kw), title=self.config["title"])}


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
