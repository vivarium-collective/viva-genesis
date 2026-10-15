"""Phase-6 figures — the internalization threshold map and the protocell's power budget.

Both render from the committed artifacts of ``og-energy-alt-internalization-threshold``
(``artifacts/internalization_threshold_map.json`` + ``internalization_threshold_report.json``,
written by ``sims/compute_internalization_threshold.py``): the sweep is a few
minutes of real runs, so it is never recomputed at page load.

* :class:`InternalizationThresholdMap` — the Decision view: per active class the
  net-power ADVANTAGE over the passive baseline across (coupling activity x
  membrane permeability) at the nominal gradient, with the paying region and
  the threshold activity marked; plus net power and autonomy against activity
  at the nominal membrane for every class.
* :class:`ProtocellEnergyBudget` — the Mechanism view: the power flows of one
  individual over time per class (external tap, internal store, maintenance,
  leak), and the store potential climbing toward — or stalling below — the
  load it must clear.
"""

from __future__ import annotations

import json

import numpy as np
from process_bigraph.visualization import Visualization

from .viz_uq import _resolve
from . import viz_style as S
from .viz_style import INK as _INK, TEAL as _TEAL, AMBER as _AMBER, SLATE as _SLATE, RUST as _RUST, VIOLET as _VIOLET
_CLASS_COLORS = {"passive_gradient": _SLATE, "h_na_gradient_leaky_membrane": _AMBER,
                 "thioester_acyl_phosphate": _TEAL, "polyphosphate": _VIOLET, "fe_redox": _RUST}
_SHORT = {"passive_gradient": "passive", "h_na_gradient_leaky_membrane": "H+/Na+ gradient",
          "thioester_acyl_phosphate": "thioester", "polyphosphate": "polyphosphate", "fe_redox": "Fe redox"}


def _nearest(values, target):
    arr = np.asarray(values, dtype=float)
    if target > 0 and (arr > 0).all():
        return int(np.argmin(np.abs(np.log10(arr) - np.log10(target))))
    return int(np.argmin(np.abs(arr - target)))


def threshold_map_figure(mmap: dict, report: dict, *, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    att = report["attribution"]
    axes, order = mmap["axes"], list(mmap["axis_order"])
    ia, ip, iv = (order.index(k) for k in ("coupling_activity", "permeability", "electric_potential"))
    acts, perms, pmfs = (np.asarray(axes[k], dtype=float) for k in ("coupling_activity", "permeability", "electric_potential"))
    nominal = att["nominal"]
    k_v = _nearest(pmfs, nominal["electric_potential"])
    j_p = _nearest(perms, nominal["permeability"])
    active = list(att["active_classes"])
    base = np.asarray(mmap["passive_net_power"], dtype=float)          # (P, pmf) or (pmf, P)
    base_pv = base if ip < iv else base.T                               # -> (P, pmf)

    def grid(c, key):
        arr = np.asarray(mmap["surfaces"][c][key], dtype=float)
        arr = np.moveaxis(arr, (ia, ip, iv), (0, 1, 2))                 # -> (a, P, pmf)
        return arr

    titles = [f"{_SHORT[c]} — advantage over passive (W)" for c in active] + \
             ["net power vs activity (nominal membrane)", "autonomy vs activity (nominal membrane)"]
    fig = make_subplots(rows=2, cols=3, subplot_titles=titles, horizontal_spacing=0.09, vertical_spacing=0.18,
                        specs=[[{}, {}, {}], [{}, {}, {}]])
    vmax = 0.0
    advs = {}
    for c in active:
        net = grid(c, "net_power")[:, :, k_v]
        adv = net - base_pv[:, k_v][None, :]
        advs[c] = adv
        vmax = max(vmax, float(np.nanmax(np.abs(adv))) if np.isfinite(adv).any() else 0.0)
    vmax = vmax or 1.0
    pos = [(1, 1), (1, 2), (1, 3), (2, 1)]
    for c, (r, col) in zip(active, pos):
        adv = advs[c]
        pays = np.moveaxis(np.asarray(mmap["pays"][c], dtype=float), (ia, ip, iv), (0, 1, 2))[:, :, k_v]
        thr = np.asarray(mmap["thresholds"][c], dtype=float)
        thr = thr[:, k_v] if ip < iv else thr[k_v, :]
        text = [[f"activity {acts[i]:.2f}, P_H {perms[j]:.1e} m/s<br>advantage {adv[i, j]:+.2e} W"
                 + ("<br>pays" if pays[i, j] > 0 else "") for i in range(len(acts))] for j in range(len(perms))]
        fig.add_trace(go.Heatmap(x=[f"{a:.2f}" for a in acts], y=[f"{p:.0e}" for p in perms], z=adv.T, text=text,
                                 hovertemplate="%{text}<extra>" + _SHORT[c] + "</extra>", zmin=-vmax, zmax=vmax,
                                 colorscale=[[0, _RUST], [0.5, "#f8fafc"], [1, _TEAL]], showscale=(c == active[0]),
                                 colorbar=dict(title="W", x=1.02, y=0.78, len=0.4)), row=r, col=col)
        xs = [f"{thr[j]:.2f}" for j in range(len(perms)) if np.isfinite(thr[j])]
        ys = [f"{perms[j]:.0e}" for j in range(len(perms)) if np.isfinite(thr[j])]
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+lines", name=f"{_SHORT[c]} threshold a*",
                                     marker=dict(symbol="diamond", size=9, color=_INK, line=dict(width=1, color="white")),
                                     line=dict(color=_INK, width=1, dash="dot"), showlegend=False), row=r, col=col)
        fig.update_xaxes(title_text="coupling activity", type="category", row=r, col=col)
        fig.update_yaxes(title_text="P_H (m/s)", type="category", row=r, col=col)
    # net power + autonomy vs activity at the nominal membrane, every class
    for c in mmap["classes"]:
        net = grid(c, "net_power")[:, j_p, k_v]
        auto = grid(c, "autonomy")[:, j_p, k_v]
        fig.add_trace(go.Scatter(x=acts, y=net, mode="lines+markers", name=_SHORT[c],
                                 line=dict(color=_CLASS_COLORS[c], width=3 if c != "passive_gradient" else 2,
                                           dash="dash" if c == "passive_gradient" else "solid")), row=2, col=2)
        fig.add_trace(go.Scatter(x=acts, y=auto, mode="lines+markers", name=_SHORT[c], showlegend=False,
                                 line=dict(color=_CLASS_COLORS[c], width=3 if c != "passive_gradient" else 2,
                                           dash="dash" if c == "passive_gradient" else "solid")), row=2, col=3)
    fig.update_xaxes(title_text="coupling activity", row=2, col=2)
    fig.update_yaxes(title_text="net power (W)", row=2, col=2)
    fig.update_xaxes(title_text="coupling activity", row=2, col=3)
    fig.update_yaxes(title_text="autonomy = internal / (internal + external)", range=[0, 1.02], row=2, col=3)
    sub = (f"nominal P_H {perms[j_p]:.0e} m/s, external pmf {pmfs[k_v]:.3g} V; ◆ = threshold activity a*(P_H); "
           + "; ".join(f"{_SHORT[c]} a* = " + (f"{att['per_class'][c]['nominal']['threshold_activity']:.2f}"
                                               if att['per_class'][c]['nominal']['threshold_activity'] is not None else "none")
                       for c in active))
    fig.update_layout(**S.base_layout(height=780, margin=dict(l=60, r=80, t=52, b=60),
                                      legend=dict(y=-0.1)))
    head = report.get("report", {}).get("headline", "")
    disc = report.get("decision_discipline") or []
    # The gate passes (>=1 class pays) but WHICH class pays is structure-sensitive
    # (cross-class agreement ~0.46) — a caution, not a failure.
    cap = head or ("Internalization pays: at the nominal membrane and the Phase-1 gradient at least one "
                   "coupling class clears the passive baseline, with the free-energy ledger exact. But which "
                   "class pays is structure-sensitive (low cross-class agreement) — the benefit is real, its "
                   "attribution to a specific coupling is not yet resolved.")
    if disc:
        cap += f"<br><span style='color:{_RUST}'><b>Decision discipline:</b> {'; '.join(disc)}</span>"
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Where internalization pays"), subtitle=sub,
                   phase="Phase 6", view="Decision", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="Result", tone="caution")


def energy_budget_figure(report: dict, *, activity: str = "1", title: str = "", load_kj: float = 30.0) -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    traj = report.get("trajectories") or {}
    series = traj.get("series") or {}
    classes = [c for c in traj.get("classes", []) if c in series]
    if not classes:
        return "<p>no trajectories in the report artifact — run sims/compute_internalization_threshold.py first.</p>"
    acts = [f"{a:g}" for a in traj.get("activities", [])]
    key = activity if activity in acts else (acts[-1] if acts else activity)
    fig = make_subplots(rows=2, cols=len(classes), horizontal_spacing=0.05, vertical_spacing=0.16,
                        subplot_titles=[f"{_SHORT[c]} — power budget (activity {key})" for c in classes]
                        + [f"{_SHORT[c]} — store potential vs load" for c in classes])
    for j, c in enumerate(classes, start=1):
        s = series[c].get(key) or next(iter(series[c].values()))
        t = np.asarray(s["global_time"], dtype=float)
        for k, name, color in (("external_power", "external tap", _SLATE), ("internal_power", "internal store", _TEAL)):
            fig.add_trace(go.Scatter(x=t, y=s[k], mode="lines", name=name, stackgroup="in", line=dict(color=color, width=1),
                                     showlegend=(j == 1)), row=1, col=j)
        for k, name, color in (("maintenance_power", "maintenance", _RUST), ("leak_power", "leak", _AMBER)):
            fig.add_trace(go.Scatter(x=t, y=[-v for v in s[k]], mode="lines", name=name, stackgroup="out",
                                     line=dict(color=color, width=1), showlegend=(j == 1)), row=1, col=j)
        fig.add_trace(go.Scatter(x=t, y=s["net_power"], mode="lines", name="net power", line=dict(color=_INK, width=2),
                                 showlegend=(j == 1)), row=1, col=j)
        fig.add_trace(go.Scatter(x=t, y=s["store_potential"], mode="lines", name="store potential mu(q)",
                                 line=dict(color=_CLASS_COLORS[c], width=3), showlegend=(j == 1)), row=2, col=j)
        fig.add_trace(go.Scatter(x=[t[0], t[-1]], y=[load_kj, load_kj], mode="lines", name="load free energy",
                                 line=dict(color=_RUST, dash="dot"), showlegend=(j == 1)), row=2, col=j)
        fig.add_trace(go.Scatter(x=t, y=[a for a in s["autonomy"]], mode="lines", name="autonomy", yaxis="y2",
                                 line=dict(color=_SLATE, dash="dash"), showlegend=(j == 1), visible="legendonly"), row=2, col=j)
        fig.update_xaxes(title_text="time (s)", row=2, col=j)
        fig.update_yaxes(title_text="W" if j == 1 else None, row=1, col=j)
        fig.update_yaxes(title_text="kJ/mol" if j == 1 else None, row=2, col=j)
    fig.update_layout(**S.base_layout(height=620, margin=dict(l=60, r=20, t=52, b=60),
                                      legend=dict(y=-0.12), font=S.FONT(11)))
    fixed = traj.get("fixed") or {}
    cap = (f"Nominal membrane ({', '.join(f'{k} {v}' for k, v in fixed.items()) or 'vg-data energy_currencies defaults'}). "
           "Top row: each class's power flows (external tap + internal store in; maintenance + leak out; net in black). "
           "Bottom: the store potential &mu;(q) vs the load (dotted) — work is drawn only once the store clears it; "
           "the free-energy ledger closes on every tick.")
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "One individual's power budget per coupling class"),
                   phase="Phase 6", view="Mechanism", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral")


class _Phase6Viz(Visualization):
    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "threshold_map_json": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string", "_default": ""},
        "activity": {"_type": "string", "_default": "1"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def _load(self, key):
        path = _resolve(str(self.config.get(key, "") or ""))
        if not path:
            return None
        with open(path) as f:
            return json.load(f)


class InternalizationThresholdMap(_Phase6Viz):
    """Phase-6 Decision view: the net-power advantage of each coupling class over
    the passive baseline across (activity x permeability), the threshold a*(P_H),
    and net power / autonomy against activity at the nominal membrane."""

    def update(self, state=None):
        mmap, rep = self._load("threshold_map_json"), self._load("report_json")
        if mmap is None or rep is None:
            return {"html": "<p>threshold-map / report artifacts not found — run sims/compute_internalization_threshold.py first.</p>"}
        return {"html": threshold_map_figure(mmap, rep, title=self.config["title"])}


class ProtocellEnergyBudget(_Phase6Viz):
    """Phase-6 Mechanism view: one individual's power flows over time per class and
    the store potential climbing toward (or stalling below) the load."""

    def update(self, state=None):
        rep = self._load("report_json")
        if rep is None:
            return {"html": "<p>report artifact not found — run sims/compute_internalization_threshold.py first.</p>"}
        return {"html": energy_budget_figure(rep, activity=str(self.config["activity"]), title=self.config["title"])}


__all__ = ["InternalizationThresholdMap", "ProtocellEnergyBudget", "threshold_map_figure", "energy_budget_figure"]
