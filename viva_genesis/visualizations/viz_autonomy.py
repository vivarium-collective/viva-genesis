"""Phase-9 figures — integrated autonomy (og-08-alt-robust-innovation-set).

Both render from the persisted artifact written by
``sims/compute_robust_innovation_set.py`` (hundreds of integrated-world runs),
so nothing is recomputed at page load:

* :class:`RobustInnovationLattice` — the Decision view: the lattice of the
  eight innovation subsets, each node coloured by the fraction of sampled
  model structures under which that subset persists off-gradient, the
  intersection / union of the required sets across structures, the og-adv
  generic control, and per structural axis the full-set persistence and each
  innovation's necessity per class.
* :class:`AutonomyAblationTrace` — the Mechanism / World view: the canonical
  structure's time course through the withdrawal (the drivers, the power
  budget the storage class delivers against the demands, the machinery the
  inheritance class holds, the population, the autonomy decomposition) with
  the structural events marked, beside the ocean-floor map (which structures
  persist at which residual support).
"""

from __future__ import annotations

import json
import math

from process_bigraph.visualization import Visualization

from .viz_uq import _resolve

from . import viz_style as S
from .viz_style import (INK as _INK, TEAL as _TEAL, AMBER as _AMBER, SLATE as _SLATE,
                        RUST as _RUST, MUTED as _MUTED, VIOLET as _VIOLET)

_GREEN = "#15803d"  # 6th categorical (not in the core palette)
_FONT = S.FONT()
_LATTICE_POS = {"none": (0.5, 0.0), "pump": (0.15, 1.0), "importer": (0.5, 1.0), "heredity": (0.85, 1.0),
                "pump+importer": (0.15, 2.0), "pump+heredity": (0.5, 2.0), "importer+heredity": (0.85, 2.0),
                "pump+importer+heredity": (0.5, 3.0)}
_EDGES = [("none", "pump"), ("none", "importer"), ("none", "heredity"), ("pump", "pump+importer"), ("pump", "pump+heredity"),
          ("importer", "pump+importer"), ("importer", "importer+heredity"), ("heredity", "pump+heredity"),
          ("heredity", "importer+heredity"), ("pump+importer", "pump+importer+heredity"),
          ("pump+heredity", "pump+importer+heredity"), ("importer+heredity", "pump+importer+heredity")]
_AXIS_LABELS = {"model_energy_coupling": "storage model", "model_heredity": "inheritance class",
                "model_boundary": "boundary class", "permeability_anchor": "permeability anchor",
                "model_localization": "transport law", "maintenance_law": "maintenance function"}


def _fmt(v, nd=2):
    return "n/a" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f"{v:.{nd}g}"


def _mix(frac: float) -> str:
    """slate (0) -> teal (1) on the lattice nodes."""
    f = min(max(0.0 if frac != frac else float(frac), 0.0), 1.0)
    a, b = (0xe2, 0xe8, 0xf0), (0x0d, 0x94, 0x88)
    return "#%02x%02x%02x" % tuple(int(round(a[i] + (b[i] - a[i]) * f)) for i in range(3))


def lattice_figure(rep: dict, *, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    lat = rep["lattice"]
    nodes = lat["nodes"]
    axes = list(lat["by_axis"])
    fig = make_subplots(rows=2, cols=max(len(axes), 1), specs=[[{"colspan": max(len(axes), 1)}] + [None] * (max(len(axes), 1) - 1),
                                                               [{} for _ in range(max(len(axes), 1))]],
                        row_heights=[0.58, 0.42], vertical_spacing=0.14, horizontal_spacing=0.04,
                        subplot_titles=["The innovation lattice — persistence across model structures"]
                        + [_AXIS_LABELS.get(a, a) for a in axes])
    for a, b in _EDGES:
        xa, ya = _LATTICE_POS[a]
        xb, yb = _LATTICE_POS[b]
        fig.add_trace(go.Scatter(x=[xa, xb], y=[ya, yb], mode="lines", line=dict(color=_MUTED, width=1.2),
                                 hoverinfo="skip", showlegend=False), row=1, col=1)
    inter = set(lat.get("required_intersection") or [])
    for lab, pos in _LATTICE_POS.items():
        d = nodes.get(lab, {})
        frac = d.get("persistence_fraction", float("nan"))
        is_full = lab == "pump+importer+heredity"
        text = f"{lab.replace('+', ' + ')}<br>{d.get('n_persist', 0)}/{d.get('n', 0)}"
        fig.add_trace(go.Scatter(
            x=[pos[0]], y=[pos[1]], mode="markers+text", text=[text], textposition="middle center",
            textfont=dict(size=10, color=_INK if (frac != frac or frac < 0.55) else "white"),
            marker=dict(size=96 if is_full else 80, color=_mix(frac), line=dict(width=3 if is_full else 1,
                                                                                 color=_RUST if is_full else _SLATE)),
            hovertemplate=f"<b>{lab}</b><br>persists under {_fmt(frac)} of structures<extra></extra>", showlegend=False), row=1, col=1)
    fig.update_xaxes(visible=False, range=[-0.05, 1.05], row=1, col=1)
    fig.update_yaxes(visible=False, range=[-0.5, 3.5], row=1, col=1)
    # per-axis breakdown: full-set persistence per level + required fractions
    colors = {"pump": _AMBER, "importer": _VIOLET, "heredity": _GREEN}
    for j, axis in enumerate(axes, start=1):
        levels = lat["by_axis"][axis]
        names = list(levels)
        short = [n.replace("_", " ")[:18] for n in names]
        fig.add_trace(go.Bar(x=short, y=[levels[n]["full_set_persistence"] for n in names], name="full set persists",
                             marker_color=_TEAL, showlegend=(j == 1),
                             hovertemplate="%{x}<br>full set persists under %{y:.2f} of its structures<extra></extra>"), row=2, col=j)
        for inn, col in colors.items():
            fig.add_trace(go.Scatter(x=short, y=[levels[n]["required_fraction"].get(inn, float("nan")) for n in names],
                                     mode="markers", marker=dict(symbol="diamond", size=9, color=col), name=f"{inn} required",
                                     showlegend=(j == 1),
                                     hovertemplate=f"%{{x}}<br>{inn} required in %{{y:.2f}} of viable structures<extra></extra>"), row=2, col=j)
        fig.update_yaxes(range=[0, 1.08], row=2, col=j, title_text=("fraction" if j == 1 else None), showticklabels=(j == 1))
        fig.update_xaxes(tickangle=-35, tickfont=dict(size=9), row=2, col=j)
    gen = rep.get("generic", {})
    au = (rep.get("autonomy") or {}).get("persisting_full_set", {})
    sub = (f"required in EVERY viable structure: {{{', '.join(lat.get('required_intersection') or []) or '—'}}} | in some: "
           f"{{{', '.join(lat.get('required_union') or []) or '—'}}} | full set persists under {_fmt(lat.get('full_set_persistence_fraction'))} "
           f"of {lat.get('n_structures')} structures ({lat.get('n_viable')} viable) | og-adv generic control persists {gen.get('n_persist', 0)}/{gen.get('n', 0)}"
           + (f" | autonomy of the persisting full set {_fmt(au.get('autonomy', {}).get('mean'))} (work {_fmt(au.get('autonomy_work', {}).get('mean'))}, "
              f"material {_fmt(au.get('autonomy_material', {}).get('mean'))}, information {_fmt(au.get('autonomy_information', {}).get('mean'))})"
              if au else ""))
    fig.update_layout(**S.base_layout(height=720, barmode="group", margin=dict(t=44, b=90),
                                      legend=dict(orientation="h", y=-0.16, x=0.0, font=dict(size=10))))
    cap = (
        "An HONEST NEGATIVE: og-08's escape set {pump, importer, heredity} is <b>not sufficient</b> in the "
        "integrated world. Each lattice node is a subset, coloured by the fraction of sampled model structures "
        "under which it persists off-gradient; the pre-registered gate FAILS (the full set persists under 0 of "
        "the structures at the nominal floor, against the 0.5 required). Over the viable structures the required "
        f"intersection is {{pump, heredity}} and the importer is required in none — it costs more than it returns. "
        f"<b>{sub}</b>. Autonomy is reached; sufficiency is not — the transition turns on one number the campaign "
        "cannot yet constrain: what the ocean offers."
    )
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "Is og-08's escape set sufficient? An honest negative"),
                   phase="Phase 9", view="Decision", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="negative")


def ablation_trace_figure(rep: dict, *, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    series = rep.get("series") or {}
    events = rep.get("events") or {}
    full = series.get("full")
    meta = rep.get("meta", {})
    fmap = rep.get("floor_map") or {}
    fig = make_subplots(rows=2, cols=3, column_widths=[0.36, 0.32, 0.32], row_heights=[0.5, 0.5],
                        horizontal_spacing=0.07, vertical_spacing=0.16,
                        subplot_titles=["Drivers withdrawn + power budget (W)",
                                        "Machinery, heredity, population",
                                        "Autonomy decomposed by function",
                                        "Knockouts: net work budget",
                                        "Knockouts: machinery held",
                                        "Ocean-floor map: who persists"])
    if full:
        t = [x / 3600.0 for x in full["t"]]
        start = float(meta.get("ablation_start", 3600.0)) / 3600.0
        end = start + float(meta.get("ablation_duration", 6000.0)) / 3600.0
        for r, c in ((1, 1), (1, 2), (1, 3), (2, 1), (2, 2)):
            fig.add_vrect(x0=start, x1=end, fillcolor=_MUTED, opacity=0.15, line_width=0, row=r, col=c)
        fig.add_trace(go.Scatter(x=t, y=full["feed_support"], name="feed / mineral support", line=dict(color=_SLATE, width=1, dash="dot"),
                                 yaxis="y2", hovertemplate="support %{y:.2f} at %{x:.1f} h<extra></extra>"), row=1, col=1)
        for key, col, nm in (("external_power", _SLATE, "external tap"), ("internal_power", _TEAL, "internal store"),
                             ("maintenance_power", _RUST, "maintenance"), ("import_power", _VIOLET, "import"),
                             ("heredity_power", _GREEN, "heredity"), ("net_power", _INK, "net")):
            fig.add_trace(go.Scatter(x=t, y=full[key], name=nm, line=dict(color=col, width=2 if key == "net_power" else 1.4),
                                     hovertemplate=f"{nm} %{{y:.2e}} W at %{{x:.1f}} h<extra></extra>"), row=1, col=1)
        fig.add_trace(go.Scatter(x=t, y=full["machinery"], name="machinery", line=dict(color=_AMBER, width=2),
                                 hovertemplate="machinery %{y:.2f}<extra></extra>"), row=1, col=2)
        fig.add_trace(go.Scatter(x=t, y=full["attached"], name="heredity attached", line=dict(color=_GREEN, width=1, dash="dash"),
                                 hovertemplate="attached %{y:.0f}<extra></extra>"), row=1, col=2)
        fig.add_trace(go.Scatter(x=t, y=full["survivors"], name="survivors (alive / founders)", line=dict(color=_INK, width=1.5),
                                 hovertemplate="survivors %{y:.2f}<extra></extra>"), row=1, col=2)
        fig.add_trace(go.Scatter(x=t, y=full["energy_charge_fraction"], name="store charge", line=dict(color=_TEAL, width=1, dash="dot"),
                                 hovertemplate="store charge %{y:.2f}<extra></extra>"), row=1, col=2)
        for key, col, nm in (("autonomy_work", _TEAL, "work"), ("autonomy_material", _AMBER, "material"),
                             ("autonomy_information", _GREEN, "information"), ("autonomy", _INK, "total (work-weighted)")):
            fig.add_trace(go.Scatter(x=t, y=full[key], name=f"autonomy: {nm}", line=dict(color=col, width=2 if key == "autonomy" else 1.4),
                                     hovertemplate=f"autonomy {nm} %{{y:.2f}}<extra></extra>"), row=1, col=3)
        # events on the machinery panel
        ev = events.get("full") or []
        shown = [e for e in ev if e["kind"] not in ("world_assembled",)][:14]
        for e in shown:
            fig.add_annotation(x=e["t"] / 3600.0, y=1.02, text=e["kind"].replace("_", " "), showarrow=True, arrowhead=0, ax=0, ay=-18,
                               font=dict(size=8, color=_SLATE), row=1, col=2)
        # knockouts
        for arm, col in (("full", _INK), ("-pump", _AMBER), ("-importer", _VIOLET), ("-heredity", _GREEN), ("generic", _RUST)):
            s = series.get(arm)
            if not s:
                continue
            tt = [x / 3600.0 for x in s["t"]]
            fig.add_trace(go.Scatter(x=tt, y=s["net_power"], name=f"{arm} net", line=dict(color=col, width=1.6), legendgroup=arm,
                                     hovertemplate=f"{arm}: net %{{y:.2e}} W<extra></extra>"), row=2, col=1)
            fig.add_trace(go.Scatter(x=tt, y=s["machinery"], name=f"{arm} machinery", line=dict(color=col, width=1.6), legendgroup=arm,
                                     showlegend=False, hovertemplate=f"{arm}: machinery %{{y:.2f}}<extra></extra>"), row=2, col=2)
        fig.add_hline(y=0.0, line=dict(color=_MUTED, width=1), row=2, col=1)
        fig.update_xaxes(title_text="world time (h)", row=2, col=1)
        fig.update_xaxes(title_text="world time (h)", row=2, col=2)
        fig.update_yaxes(title_text="W", row=1, col=1)
        fig.update_yaxes(title_text="W", row=2, col=1)
        fig.update_yaxes(range=[-0.05, 1.1], row=1, col=2)
        fig.update_yaxes(range=[-0.05, 1.1], row=1, col=3)
        fig.update_yaxes(range=[-0.05, 1.1], row=2, col=2)
    # the ocean-floor map
    if fmap.get("cells"):
        floors = list(fmap["floors"])
        sids = list(fmap["structures"])
        cell = {(c["structure"], c["floor"]): c for c in fmap["cells"]}
        z = [[(1.0 if cell[(s, f)]["persists"] else 0.0) if (s, f) in cell else None for f in floors] for s in sids]
        text = [[(f"net {_fmt(cell[(s, f)]['net_power'])} W<br>machinery {_fmt(cell[(s, f)]['machinery'])}<br>autonomy {_fmt(cell[(s, f)]['autonomy'])}"
                  if (s, f) in cell else "") for f in floors] for s in sids]
        fig.add_trace(go.Heatmap(x=[f"{f:.0e}" for f in floors], y=sids, z=z, text=text,
                                 hovertemplate="structure %{y} at floor %{x}<br>%{text}<extra></extra>",
                                 colorscale=[[0.0, "#e2e8f0"], [1.0, _TEAL]], showscale=False, zmin=0, zmax=1), row=2, col=3)
        fig.update_xaxes(title_text="ocean floor (fraction of the vent feed)", row=2, col=3)
        fig.update_yaxes(title_text="structure", tickfont=dict(size=8), row=2, col=3)
    led = rep.get("ledger") or {}
    worst = led.get("worst_residuals") or {}
    sub = (f"seven ledgers over {led.get('n_runs', 0)} runs: all ok on {led.get('n_ok', 0)} | worst residuals — C {_fmt(worst.get('C'))}, "
           f"free energy {_fmt(worst.get('free_energy'))}, information {_fmt(worst.get('information_energy'))}, rewrite {_fmt(worst.get('rewrite'))}, "
           f"charge {_fmt(worst.get('charge'))} | structural events logged {led.get('events_total', 0)} "
           f"(divisions {led.get('divisions_total', 0)}, extinctions {led.get('extinctions_total', 0)})"
           + (f" | floors where the full set persists: {_fmt(fmap.get('persistence_fraction_by_floor', {}).get(str(floors[0]) if fmap.get('floors') else '', float('nan')))}"
              if False else ""))
    fig.update_layout(**S.base_layout(height=760, margin=dict(t=44, b=110),
                                      legend=dict(orientation="h", y=-0.12, x=0.0, font=dict(size=9))))
    cap = (
        "The integrated world through the ablation: every driver is withdrawn to its ocean floor (grey band) and "
        "the per-individual power budget, machinery/heredity/population, and the work-weighted autonomy are traced; "
        "the knockouts and the ocean-floor map show which structures persist at which residual support. The seven "
        f"ledgers (geology, interface, network/ecology, free energy, information, rewrite) close on every run. <b>{sub}</b>."
    )
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    return S.frame(inner, title=(title or "The integrated world through the ablation"),
                   phase="Phase 9", view="Mechanism", tier="conceptual_demonstration",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1100)


class _ArtifactViz(Visualization):
    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string", "_default": ""},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def _load(self):
        path = _resolve(str(self.config.get("report_json", "") or ""))
        if not path:
            return None
        with open(path) as f:
            return json.load(f)


class RobustInnovationLattice(_ArtifactViz):
    """Phase-9 Decision view: the innovation lattice across model structures."""

    def update(self, state=None):
        rep = self._load()
        if rep is None:
            return {"html": "<p>robust_innovation_set.json not found — run sims/compute_robust_innovation_set.py first.</p>"}
        return {"html": lattice_figure(rep, title=self.config["title"])}


class AutonomyAblationTrace(_ArtifactViz):
    """Phase-9 Mechanism / World view: the integrated world through the withdrawal, the knockouts and the floor map."""

    def update(self, state=None):
        rep = self._load()
        if rep is None:
            return {"html": "<p>robust_innovation_set.json not found — run sims/compute_robust_innovation_set.py first.</p>"}
        return {"html": ablation_trace_figure(rep, title=self.config["title"])}


__all__ = ["RobustInnovationLattice", "AutonomyAblationTrace", "lattice_figure", "ablation_trace_figure"]
