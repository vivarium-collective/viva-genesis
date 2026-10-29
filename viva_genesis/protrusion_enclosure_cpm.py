"""S3 — protrusions to enclosure, the SPATIAL model (campaign composite B).

A deformable archaeal-like HOST cell and a compact bacterial SYMBIONT share a
medium, with actual spatial boundaries, on the real Rust Cellular Potts engine
(``cpm``, from viva-cpm). Differential adhesion (Glazier & Graner 1993, Fig. 18
engulfment) drives the host to wrap the symbiont when the energy gained by
host-symbiont contact beats the cost of host membrane deformation plus the lost
host-medium and symbiont-medium interface:

    engulfment when  gamma(symbiont, medium) > gamma(host, medium) + gamma(host, symbiont)
    with self-energies ~0 this is       J_sM  >  J_hM + J_hs

so the wrapping transition in the host-symbiont adhesion ``J_hs`` sits at
``J_sM - J_hM``.  Lower J_hs = stronger adhesion = enclosure.  This is the spatial
companion to the analytical Helfrich model in
:mod:`viva_genesis.membrane_enclosure`: here enclosure is an *emergent, measured*
outcome of the mechanics, not an area/bending threshold.

Provides the model kernel, the ``ProtrusionEnclosureCPMProcess`` (registered by
``build_core``), and the phase-diagram sweep used as the S3 capstone figure.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from process_bigraph import Process

from bigraph_schema.contract import ProcessContract

from cpm import cpm_core

MEDIUM, SYMBIONT, HOST = 0, 1, 2  # medium is always owner/type 0


@dataclass
class EnclosureParams:
    nx: int = 90
    temperature: float = 10.0
    lambda_volume: float = 2.0
    j_sM: float = 16.0
    j_hM: float = 4.0
    j_hs: float = 6.0
    symbiont_radius: float = 8.0
    host_radius: float = 12.0
    symbiont_target: float = 200.0
    host_target: float = 400.0
    seed: int = 7

    @property
    def wrapping_threshold(self) -> float:
        return self.j_sM - self.j_hM


def _disc(nx, cx, cy, r):
    yy, xx = np.mgrid[0:nx, 0:nx]
    return ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r


def build_world(p: EnclosureParams):
    """Two cells in contact: symbiont disc above, host disc just below it."""
    w = cpm_core.World((p.nx, p.nx, 1), "noflux", 2, p.temperature)
    for (a, b), j in {
        (MEDIUM, MEDIUM): 0.0, (HOST, MEDIUM): p.j_hM, (SYMBIONT, MEDIUM): p.j_sM,
        (HOST, SYMBIONT): p.j_hs, (HOST, HOST): 0.0, (SYMBIONT, SYMBIONT): 0.0,
    }.items():
        w.set_contact(a, b, float(j))
    labels = np.zeros((p.nx, p.nx), dtype=np.uint32)
    cx = p.nx // 2
    labels[_disc(p.nx, cx, int(p.nx * 0.42), p.symbiont_radius)] = 1
    host = _disc(p.nx, cx, int(p.nx * 0.62), p.host_radius) & (labels == 0)
    labels[host] = 2
    types_map = {1: SYMBIONT, 2: HOST}
    label_to_cid = w.seed_from_labels(
        labels.ravel().tolist(), types_map, HOST, p.symbiont_target, p.lambda_volume)
    targets = {SYMBIONT: p.symbiont_target, HOST: p.host_target}
    for label, cid in label_to_cid.items():
        w.set_target_volume(int(cid), targets[types_map[int(label)]])
    w.finalize(p.seed)
    return w


def type_grid(w, nx):
    owners = np.asarray(w.snapshot(), dtype=np.int64).reshape(nx, nx)
    types_of = np.asarray(w.cell_types(), dtype=np.int64)
    return types_of[owners]


def wrapping_fraction(g) -> float:
    """Fraction of the symbiont's exposed boundary the host covers (1 = enclosed)."""
    sym = g == SYMBIONT
    host_faces = med_faces = 0
    for ax, sh in [(0, 1), (0, -1), (1, 1), (1, -1)]:
        ng = np.roll(g, sh, axis=ax)
        host_faces += int(np.sum(sym & (ng == HOST)))
        med_faces += int(np.sum(sym & (ng == MEDIUM)))
    tot = host_faces + med_faces
    return host_faces / tot if tot else 0.0


# regime classification for the phase diagram
ENCLOSED_THRESH, PARTIAL_THRESH, TRANSIENT_DROP = 0.85, 0.45, 0.20
REGIMES = ["no enclosure", "partial wrapping", "transient internalization", "stable enclosure"]


def run_trajectory(p: EnclosureParams, total_sweeps: int = 2400, block: int = 60):
    w = build_world(p)
    xs, ys = [0], [wrapping_fraction(type_grid(w, p.nx))]
    for s in range(block, total_sweeps + 1, block):
        w.step_parallel(block, 16)
        xs.append(s); ys.append(wrapping_fraction(type_grid(w, p.nx)))
    return np.array(xs), np.array(ys), type_grid(w, p.nx)


def classify_regime(wrapping: np.ndarray) -> str:
    plateau = float(np.mean(wrapping[-max(1, len(wrapping) // 5):]))
    peak = float(np.max(wrapping))
    if plateau >= ENCLOSED_THRESH:
        return "stable enclosure"
    if peak >= ENCLOSED_THRESH and (peak - plateau) >= TRANSIENT_DROP:
        return "transient internalization"
    if plateau >= PARTIAL_THRESH:
        return "partial wrapping"
    return "no enclosure"


class ProtrusionEnclosureCPMProcess(Process):
    """Host/symbiont differential-adhesion wrapping on the Rust CPM engine (S3, composite B)."""

    contract = ProcessContract(
        summary=(
            "Advances a two-cell Cellular Potts world — a deformable archaeal-like HOST and a "
            "compact bacterial SYMBIONT in a shared medium — by `mcs_per_update` Monte-Carlo "
            "sweeps each step, and emits how far the host has wrapped the symbiont. Differential "
            "adhesion drives wrapping when host-symbiont adhesion J_hs beats the surface-tension "
            "cost J_sM - J_hM; enclosure is the emergent plateau of host coverage, not an imposed "
            "threshold."
        ),
        description=(
            "Eukaryogenesis S3 spatial model (campaign composite B). The energies J_hM, J_sM, J_hs "
            "set host/symbiont surface tensions against the medium and the host-symbiont adhesion; "
            "sweeping J_hs across J_sM - J_hM moves the system through the wrapping transition — the "
            "G3 (Enclosure) discriminator. The spatial companion to the analytical Helfrich model."
        ),
        inputs={},
        outputs={
            "enclosure_fraction": "host coverage of the symbiont boundary (0..1; 1 = fully enclosed)",
            "enclosed": "enclosure_fraction has passed the enclosure threshold",
            "host_contact_faces": "symbiont boundary faces touching the host",
            "medium_contact_faces": "symbiont boundary faces exposed to the medium",
            "sweeps": "cumulative Monte-Carlo sweeps advanced",
        },
    )

    config_schema = {
        "nx": {"_type": "integer", "_default": 90},
        "temperature": {"_type": "float", "_default": 10.0},
        "lambda_volume": {"_type": "float", "_default": 2.0},
        "j_sM": {"_type": "float", "_default": 16.0},
        "j_hM": {"_type": "float", "_default": 4.0},
        "j_hs": {"_type": "float", "_default": 6.0},
        "symbiont_radius": {"_type": "float", "_default": 8.0},
        "host_radius": {"_type": "float", "_default": 12.0},
        "symbiont_target": {"_type": "float", "_default": 200.0},
        "host_target": {"_type": "float", "_default": 400.0},
        "seed": {"_type": "integer", "_default": 7},
        "mcs_per_update": {"_type": "integer", "_default": 60},
    }

    def initialize(self, config):
        self.params = EnclosureParams(
            nx=int(config["nx"]), temperature=float(config["temperature"]),
            lambda_volume=float(config["lambda_volume"]), j_sM=float(config["j_sM"]),
            j_hM=float(config["j_hM"]), j_hs=float(config["j_hs"]),
            symbiont_radius=float(config["symbiont_radius"]),
            host_radius=float(config["host_radius"]),
            symbiont_target=float(config["symbiont_target"]),
            host_target=float(config["host_target"]), seed=int(config["seed"]))
        self.nx = self.params.nx
        self.mcs = int(config["mcs_per_update"])
        self.world = build_world(self.params)
        self._sweeps = 0

    def inputs(self):
        return {}

    def outputs(self):
        # overwrite: each step's reading REPLACES the store (a bare scalar apply accumulates).
        return {
            "enclosure_fraction": "overwrite[float]",
            "enclosed": "overwrite[boolean]",
            "host_contact_faces": "overwrite[integer]",
            "medium_contact_faces": "overwrite[integer]",
            "sweeps": "overwrite[integer]",
        }

    def update(self, state, interval):
        self.world.step_parallel(self.mcs, 16)
        self._sweeps += self.mcs
        g = type_grid(self.world, self.nx)
        sym = g == SYMBIONT
        host_faces = med_faces = 0
        for ax, sh in [(0, 1), (0, -1), (1, 1), (1, -1)]:
            ng = np.roll(g, sh, axis=ax)
            host_faces += int(np.sum(sym & (ng == HOST)))
            med_faces += int(np.sum(sym & (ng == MEDIUM)))
        frac = host_faces / (host_faces + med_faces) if (host_faces + med_faces) else 0.0
        return {
            "enclosure_fraction": float(frac),
            "enclosed": bool(frac >= ENCLOSED_THRESH),
            "host_contact_faces": int(host_faces),
            "medium_contact_faces": int(med_faces),
            "sweeps": int(self._sweeps),
        }


# ---------------------------------------------------------------------------
# Phase diagram — the enclosure (G3) plane of the endosymbiosis phase diagram
# ---------------------------------------------------------------------------

def compute_phase_diagram(j_hs_axis=(2, 6, 10, 12, 14, 18), j_sM_axis=(10, 14, 18, 22),
                          j_hM=4.0, seeds=(7, 23), nx=80, total_sweeps=1800):
    regime = np.empty((len(j_sM_axis), len(j_hs_axis)), dtype=int)
    wrap = np.empty_like(regime, dtype=float)
    idx = {r: i for i, r in enumerate(REGIMES)}
    for iy, jsm in enumerate(j_sM_axis):
        for ix, jhs in enumerate(j_hs_axis):
            plateaus, regs = [], []
            for sd in seeds:
                p = EnclosureParams(nx=nx, j_hs=float(jhs), j_sM=float(jsm),
                                    j_hM=float(j_hM), seed=int(sd))
                _, ys, _ = run_trajectory(p, total_sweeps=total_sweeps)
                plateaus.append(float(np.mean(ys[-max(1, len(ys) // 5):])))
                regs.append(classify_regime(ys))
            wrap[iy, ix] = float(np.mean(plateaus))
            regime[iy, ix] = idx[max(set(regs), key=lambda r: (regs.count(r), idx[r]))]
    return {"j_hs_axis": list(map(float, j_hs_axis)), "j_sM_axis": list(map(float, j_sM_axis)),
            "j_hM": float(j_hM), "regimes": REGIMES, "regime_grid": regime.tolist(),
            "wrapping_grid": np.round(wrap, 3).tolist()}


def render_phase_diagram_html(data, out_path):
    """Self-contained interactive Plotly heatmap for the workbench (viz/*.html)."""
    import json
    from pathlib import Path
    jhs, jsm = data["j_hs_axis"], data["j_sM_axis"]
    colors = ["#f4f1ea", "#e4c27a", "#c6792f", "#2f6f8f"]
    n = len(REGIMES)
    colorscale = []
    for i, c in enumerate(colors):
        colorscale += [[i / n, c], [(i + 1) / n, c]]
    text = [[f"{REGIMES[data['regime_grid'][iy][ix]]}<br>wrap {data['wrapping_grid'][iy][ix]:.2f}"
             for ix in range(len(jhs))] for iy in range(len(jsm))]
    fig_data = [
        {"type": "heatmap", "x": jhs, "y": jsm, "z": data["regime_grid"], "text": text,
         "hoverinfo": "text", "colorscale": colorscale, "zmin": 0, "zmax": n,
         "showscale": False, "xgap": 2, "ygap": 2},
        {"type": "scatter", "x": [y - data["j_hM"] for y in jsm], "y": jsm, "mode": "lines",
         "line": {"color": "#111", "width": 2.5, "dash": "dash"},
         "name": "predicted threshold J_hs = J_sM − J_hM", "hoverinfo": "name"},
    ]
    layout = {
        "title": {"text": "<b>Endosymbiosis phase diagram — enclosure (G3) plane</b><br>"
                  "<span style='font-size:12px;color:#64748b'>CPM differential-adhesion wrapping; "
                  "colour = regime, number = measured host coverage of the symbiont boundary</span>"},
        "xaxis": {"title": "host–symbiont adhesion  J_hs  (lower = stronger adhesion)"},
        "yaxis": {"title": "symbiont–medium surface tension  J_sM"},
        "annotations": [{"x": jhs[ix], "y": jsm[iy],
                         "text": f"{data['wrapping_grid'][iy][ix]:.2f}", "showarrow": False,
                         "font": {"size": 10, "color": "#111"}}
                        for iy in range(len(jsm)) for ix in range(len(jhs))],
        "margin": {"l": 70, "r": 30, "t": 70, "b": 60},
        "paper_bgcolor": "white", "plot_bgcolor": "white",
    }
    legend = "".join(f'<span style="display:inline-block;width:12px;height:12px;background:{c};'
                     f'margin:0 4px 0 12px;vertical-align:middle"></span>{r}'
                     for c, r in zip(colors, REGIMES))
    html = ("<!doctype html><html><head><meta charset='utf-8'>"
            "<script src='https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js'></script>"
            "</head><body style='font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0'>"
            "<div id='pd' style='width:100%;max-width:820px;margin:0 auto'></div>"
            f"<div style='text-align:center;font-size:12px;color:#334155;margin:6px'>{legend}</div>"
            f"<script>Plotly.newPlot('pd',{json.dumps(fig_data)},{json.dumps(layout)},"
            "{responsive:true,displayModeBar:false});</script></body></html>")
    Path(out_path).write_text(html)
    return out_path


# ---------------------------------------------------------------------------
# Spatial lattice figure — the actual host-wraps-symbiont geometry over time
# ---------------------------------------------------------------------------

def run_with_snapshots(p: EnclosureParams, snapshot_sweeps=(0, 150, 450, 1200), block: int = 30):
    """Run the CPM and return (sweeps, wrapping-fraction trajectory, {sweep: type_grid})
    capturing the 2D lattice at each requested sweep count."""
    w = build_world(p)
    xs, ys = [0], [wrapping_fraction(type_grid(w, p.nx))]
    snaps = {0: type_grid(w, p.nx).tolist()} if 0 in snapshot_sweeps else {}
    total = max(snapshot_sweeps)
    for s in range(block, total + 1, block):
        w.step_parallel(block, 16)
        g = type_grid(w, p.nx)
        xs.append(s); ys.append(wrapping_fraction(g))
        if s in snapshot_sweeps:
            snaps[s] = g.tolist()
    return np.array(xs), np.array(ys), snaps


def render_enclosure_spatial_html(out_path, p: EnclosureParams = None,
                                  snapshot_sweeps=(0, 150, 450, 1200)):
    """Self-contained Plotly figure of the CPM *spatial* enclosure: the 2D lattice
    (medium / symbiont / host) at several Monte-Carlo timepoints, showing the host
    physically wrapping the symbiont, with the measured host-coverage trajectory
    below. This is the spatial detail behind the enclosure probability."""
    import json
    from pathlib import Path
    p = p or EnclosureParams()
    xs, ys, snaps = run_with_snapshots(p, snapshot_sweeps)
    sweeps = sorted(snaps)
    wf = dict(zip([int(x) for x in xs], [float(y) for y in ys]))
    med, sym, host = "#efe9dc", "#e0a53f", "#2f6f8f"
    colorscale = [[0.0, med], [1/3, med], [1/3, sym], [2/3, sym], [2/3, host], [1.0, host]]
    n = len(sweeps)
    gap = 0.018
    w_each = (1.0 - gap * (n - 1)) / n
    fig_data, layout = [], {
        "paper_bgcolor": "white", "plot_bgcolor": "white",
        "margin": {"l": 20, "r": 20, "t": 64, "b": 44}, "showlegend": False,
        "title": {"text": "<b>Enclosure, in space — host wrapping the symbiont (Cellular Potts)</b><br>"
                  "<span style='font-size:12px;color:#64748b'>differential adhesion J_hs="
                  f"{p.j_hs:g} &lt; J_sM&minus;J_hM={p.wrapping_threshold:g}; "
                  "colour = cell type, panels = Monte-Carlo sweeps</span>"},
        "annotations": [],
    }
    labels = ["contact", "wrapping", "deep wrapping", "enclosed"]
    for i, sw in enumerate(sweeps):
        ax = "" if i == 0 else str(i + 1)
        x0 = i * (w_each + gap)
        fig_data.append({"type": "heatmap", "z": snaps[sw], "colorscale": colorscale,
                         "zmin": 0, "zmax": 2, "showscale": False, "hoverinfo": "skip",
                         "xaxis": f"x{ax}", "yaxis": f"y{ax}"})
        layout[f"xaxis{ax}"] = {"domain": [x0, x0 + w_each], "showticklabels": False,
                                "ticks": "", "showgrid": False, "zeroline": False}
        layout[f"yaxis{ax}"] = {"domain": [0.34, 0.92], "showticklabels": False, "ticks": "",
                                "showgrid": False, "zeroline": False, "scaleanchor": f"x{ax}"}
        lab = labels[min(i, len(labels) - 1)]
        layout["annotations"].append({
            "x": x0 + w_each / 2, "y": 0.95, "xref": "paper", "yref": "paper", "showarrow": False,
            "text": f"<b>{lab}</b><br><span style='font-size:11px;color:#64748b'>"
                    f"sweep {sw} · coverage {wf.get(sw, 0):.2f}</span>", "font": {"size": 12}})
    # trajectory curve across the bottom
    cax = str(n + 1)
    fig_data.append({"type": "scatter", "x": [int(x) for x in xs], "y": [float(y) for y in ys],
                     "mode": "lines", "line": {"color": host, "width": 2.5},
                     "fill": "tozeroy", "fillcolor": "rgba(47,111,143,0.12)",
                     "xaxis": f"x{cax}", "yaxis": f"y{cax}", "hoverinfo": "x+y"})
    layout[f"xaxis{cax}"] = {"domain": [0.05, 0.95], "anchor": f"y{cax}",
                             "title": {"text": "Monte-Carlo sweeps", "font": {"size": 11}}}
    layout[f"yaxis{cax}"] = {"domain": [0.0, 0.24], "anchor": f"x{cax}", "range": [0, 1.02],
                             "title": {"text": "host coverage of symbiont", "font": {"size": 11}}}
    legend = ("".join(f"<span style='display:inline-block;width:12px;height:12px;background:{c};"
              f"margin:0 4px 0 14px;vertical-align:middle;border:1px solid #cbd5e1'></span>{lab}"
              for c, lab in [(med, "medium"), (sym, "symbiont"), (host, "host")]))
    html = ("<!doctype html><html><head><meta charset='utf-8'>"
            "<script src='https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js'></script>"
            "</head><body style='font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0'>"
            "<div id='sp' style='width:100%;max-width:960px;margin:0 auto'></div>"
            f"<div style='text-align:center;font-size:12px;color:#334155;margin:4px'>{legend}</div>"
            f"<script>Plotly.newPlot('sp',{json.dumps(fig_data)},{json.dumps(layout)},"
            "{responsive:true,displayModeBar:false});</script></body></html>")
    Path(out_path).write_text(html)
    return out_path
