"""Workspace visualizations for viva-genesis (live in the workbench Visualizations tab).

``VentReactorTimeseries`` runs the og-00 **real coupled model**
(``serpentinizing_vent_reactor`` — PHREEQC serpentinization + FiPy reactive
transport) via ``build_core()`` and returns ``{"html": <plotly html>}``. As a
``Visualization`` (a Step subclass) it auto-registers through the package walk
and re-runs live with the study.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from process_bigraph.visualization import Visualization

from . import viz_style as S
from .viz_style import INK, TEAL, AMBER, SLATE, RUST


class VentReactorTimeseries(Visualization):
    """Campaign-0 real vent-reactor trajectory: temperature, pH, reducing power
    (H2 flux + pe), porosity, and the mass/charge + spatial-flux conservation
    witnesses — with the Lost City acceptance windows shaded.

    Drives the genuine PHREEQC + FiPy composite (``viva_genesis.composites``).
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign 0 — real vent reactor (PHREEQC + FiPy)"},
        "n_steps": {"_type": "integer", "_default": 120},
        # Real-composite overrides (kept in sync with the generator parameters).
        "flow_velocity": {"_type": "float", "_default": 1.0e-3},
        "olivine_rate": {"_type": "float", "_default": 0.15},
        "nx": {"_type": "integer", "_default": 40},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.vent_reactor import serpentinizing_vent_reactor

        core = build_core()
        doc = serpentinizing_vent_reactor(
            core,
            flow_velocity=float(self.config["flow_velocity"]),
            olivine_rate=float(self.config["olivine_rate"]),
            nx=int(self.config["nx"]),
        )
        sim = Composite({"state": doc}, core=core)
        sim.run(float(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        from ..composites.vent_reactor import serpentinizing_vent_reactor

        def col(k):
            return [r[k] for r in rows if k in r]

        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)],
                                serpentinizing_vent_reactor)
        temp_c = [v - 273.15 for v in col("temperature")]
        ph = col("pH")
        h2f = col("H2_flux")
        pe = col("pe")
        por = col("porosity")
        ci = [abs(v) for v in col("charge_imbalance")]
        fdr = [abs(v) for v in col("flux_divergence_residual")]

        ink, teal, amber, slate, rust = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c"
        fig = make_subplots(
            rows=2, cols=3, vertical_spacing=0.17, horizontal_spacing=0.09,
            subplot_titles=(
                "Temperature (°C)", "pH", "H₂ source flux (mol/s)",
                "Redox pe (dimensionless)", "Porosity (fraction)", "Conservation residuals (|·|)",
            ),
        )
        # Temperature + Lost City window 40–91 °C.
        fig.add_hrect(y0=40, y1=91, line_width=0, fillcolor=teal, opacity=0.08, row=1, col=1)
        fig.add_scatter(x=t, y=temp_c, mode="lines", line=dict(color=amber, width=2.5), row=1, col=1)
        # pH + field window 9.0–10.8 (real equilibrium sits below — the open gap).
        fig.add_hrect(y0=9.0, y1=10.8, line_width=0, fillcolor=teal, opacity=0.08, row=1, col=2)
        fig.add_scatter(x=t, y=ph, mode="lines", line=dict(color=teal, width=2.5), row=1, col=2)
        # H2 flux (reducing power).
        fig.add_scatter(x=t, y=h2f, mode="lines", line=dict(color=ink, width=2), row=1, col=3)
        # Redox pe (reducing < 0).
        fig.add_hline(y=0.0, line=dict(color=slate, width=1, dash="dot"), row=2, col=1)
        fig.add_scatter(x=t, y=pe, mode="lines", line=dict(color=rust, width=2), row=2, col=1)
        # Porosity.
        fig.add_scatter(x=t, y=por, mode="lines", line=dict(color=slate, width=2.5), row=2, col=2)
        # Conservation witnesses (log — both hug machine epsilon / zero).
        fig.add_scatter(x=t, y=[max(v, 1e-18) for v in ci], mode="lines",
                        line=dict(color=ink, width=2), name="|charge imbalance|", row=2, col=3)
        fig.add_scatter(x=t, y=[max(v, 1e-18) for v in fdr], mode="lines",
                        line=dict(color=teal, width=2, dash="dot"), name="|flux div. residual|", row=2, col=3)

        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(type="log", row=2, col=3)
        fig.update_layout(**S.base_layout(
            height=620, showlegend=True,
            legend=dict(orientation="h", y=-0.08, x=0.66, font=dict(size=10)),
            margin=dict(l=60, r=30, t=46, b=60)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Real vent reactor (PHREEQC + FiPy)"),
            phase="Campaign 0", view="World", tier="reproduction", caption_prefix="How to read",
            caption_text=(
                "The real PHREEQC + FiPy vent reactor over time — temperature, pH, reducing power "
                "(H₂ flux + pe), porosity, and the mass/charge + spatial-flux conservation witnesses. "
                "Shaded bands are the Lost City acceptance windows (40–91&#8239;°C; pH 9.0–10.8); the "
                "conservation residuals hug zero."))


class CarbonFixationViz(Visualization):
    """Campaign-I real geology->reduced-carbon trajectory: product yields
    (formate/acetate/pyruvate), the pH-gradient proton-motive force + current,
    the real eQuilibrator ΔG'/feasibility gate, and net organic-carbon flux.

    Drives the genuine eQuilibrator + FiPy composite
    (``viva_genesis.composites.carbon_fixation``).
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign I — geology to reduced carbon"},
        "n_steps": {"_type": "integer", "_default": 120},
        "gradient_efficiency": {"_type": "float", "_default": 1.0},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.carbon_fixation import hydrothermal_carbon_fixation
        core = build_core()
        doc = hydrothermal_carbon_fixation(
            core, gradient_efficiency=float(self.config["gradient_efficiency"]))
        sim = Composite({"state": doc}, core=core)
        sim.run(float(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        from plotly.subplots import make_subplots
        from ..composites.carbon_fixation import hydrothermal_carbon_fixation

        def col(k):
            return [r[k] for r in rows if k in r]

        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)],
                                hydrothermal_carbon_fixation)
        formate = [v * 1000.0 for v in col("formate")]      # mM
        acetate = [v * 1e6 for v in col("acetate")]         # uM
        pyruvate = [v * 1e6 for v in col("pyruvate")]       # uM
        pmf = [v * 1000.0 for v in col("pmf")]              # mV
        jcur = col("current_density")
        ncf = col("net_carbon_flux")
        dgf = col("dg_formate")
        feas = col("feasible_formate")

        ink, teal, amber, slate, rust, violet = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c", "#7c3aed"
        fig = make_subplots(
            rows=2, cols=3, vertical_spacing=0.17, horizontal_spacing=0.09,
            subplot_titles=(
                "Formate (mM)", "Acetate / pyruvate (µM)", "Net carbon flux (mol/s)",
                "Proton-motive force (mV)", "Current density (A/m²)", "ΔG′ formate & feasibility",
            ),
        )
        fig.add_hrect(y0=0, y1=200, line_width=0, fillcolor=teal, opacity=0.06, row=1, col=1)
        fig.add_scatter(x=t, y=formate, mode="lines", line=dict(color=teal, width=2.5), row=1, col=1)
        fig.add_scatter(x=t, y=acetate, mode="lines", line=dict(color=amber, width=2), name="acetate", row=1, col=2)
        fig.add_scatter(x=t, y=pyruvate, mode="lines", line=dict(color=rust, width=2, dash="dot"), name="pyruvate", row=1, col=2)
        fig.add_scatter(x=t, y=ncf, mode="lines", line=dict(color=ink, width=2), row=1, col=3)
        fig.add_scatter(x=t, y=pmf, mode="lines", line=dict(color=violet, width=2.5), row=2, col=1)
        fig.add_scatter(x=t, y=jcur, mode="lines", line=dict(color=slate, width=2), row=2, col=2)
        fig.add_scatter(x=t, y=dgf, mode="lines", line=dict(color=rust, width=2), name="ΔG′ (kJ/mol)", row=2, col=3)
        fig.add_scatter(x=t, y=[f * 100 for f in feas], mode="lines", line=dict(color=teal, width=2, dash="dot"), name="feasibility ×100", row=2, col=3)
        fig.add_hline(y=0.0, line=dict(color=slate, width=1, dash="dot"), row=2, col=3)

        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(**S.base_layout(
            height=620, showlegend=True,
            legend=dict(orientation="h", y=-0.08, x=0.3, font=dict(size=10)),
            margin=dict(l=60, r=30, t=46, b=60)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Geology to reduced carbon (eQuilibrator + FiPy)"),
            phase="Campaign I", view="World", tier="mechanistic_prediction", caption_prefix="How to read",
            caption_text=(
                "The real eQuilibrator + FiPy carbon-fixation trajectory — product yields "
                "(formate/acetate/pyruvate), the pH-gradient proton-motive force and current density, "
                "the real ΔG′/feasibility gate, and net organic-carbon flux, all driven by the "
                "geochemical gradient."))


class ProtometabolismViz(Visualization):
    """Campaign-II real protometabolic-network trajectory: rTCA-fragment species
    (OAA / acetate / succinate), the net carbon throughput under feed+washout, and
    the autocatalytic gain — the emergent metabolism-like behavior.

    Drives the genuine libRoadRunner/Tellurium composite
    (``viva_genesis.composites.protometabolism``).
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign II — protometabolic network"},
        "n_steps": {"_type": "integer", "_default": 120},
        "feed_CO2": {"_type": "float", "_default": 2.0e-3},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.protometabolism import protometabolic_network
        core = build_core()
        doc = protometabolic_network(
            core, feed_CO2=float(self.config["feed_CO2"]))
        sim = Composite({"state": doc}, core=core)
        sim.run(float(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        from plotly.subplots import make_subplots
        from ..composites.protometabolism import protometabolic_network

        def col(k):
            return [r[k] for r in rows if k in r]

        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)],
                                protometabolic_network)
        oaa = [v * 1e3 for v in col("OAA")]            # mM
        acetate = [v * 1e3 for v in col("acetate")]   # mM
        succinate = [v * 1e3 for v in col("succinate")]
        ncf = col("net_carbon_flux")
        gain = col("autocatalytic_gain")

        ink, teal, amber, slate, rust = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c"
        fig = make_subplots(
            rows=1, cols=3, horizontal_spacing=0.08,
            subplot_titles=("rTCA-fragment species (mM)", "Net carbon throughput (mol/s)",
                            "Autocatalytic gain (dimensionless)"),
        )
        fig.add_scatter(x=t, y=oaa, mode="lines", line=dict(color=teal, width=2.5), name="OAA", row=1, col=1)
        fig.add_scatter(x=t, y=acetate, mode="lines", line=dict(color=amber, width=2), name="acetate", row=1, col=1)
        fig.add_scatter(x=t, y=succinate, mode="lines", line=dict(color=rust, width=2, dash="dot"), name="succinate", row=1, col=1)
        fig.add_scatter(x=t, y=ncf, mode="lines", line=dict(color=ink, width=2.5), row=1, col=2)
        fig.add_hline(y=1.0, line=dict(color=slate, width=1, dash="dot"), row=1, col=3)
        fig.add_scatter(x=t, y=gain, mode="lines", line=dict(color=rust, width=2.5), row=1, col=3)

        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(**S.base_layout(
            height=380, showlegend=True,
            legend=dict(orientation="h", y=-0.2, x=0.0, font=dict(size=10)),
            margin=dict(l=60, r=30, t=46, b=60)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Protometabolic network (libRoadRunner)"),
            phase="Campaign II", view="World", tier="mechanistic_prediction", caption_prefix="How to read",
            caption_text=(
                "The real libRoadRunner rTCA-fragment network over time — the OAA / acetate / succinate "
                "pools, the net carbon throughput under continuous feed + washout, and the autocatalytic "
                "gain (above 1 the network self-amplifies)."))


def render_declared_viz_json(study_dir, run_id, ws_root):
    """Render a study's declared ``visualizations[]`` to
    ``<ws_root>/.pbg/runs/<run_id>/viz.json`` ({viz_name: html}) — the file the
    workbench native viz gallery (study_native_gallery) reads for the latest run.

    Mirrors ``run_runner._render_viz`` for the canonical ``sims/run.py`` path,
    which otherwise leaves the live gallery empty (only the committed
    ``viz/*.html`` disk file surfaces via the auto-discover path).
    """
    import json
    import yaml
    from pathlib import Path
    from ..core import build_core

    study_dir = Path(study_dir)
    ws_root = Path(ws_root)
    spec = yaml.safe_load((study_dir / "study.yaml").read_text(encoding="utf-8")) or {}
    core = build_core()
    reg = core.link_registry
    panels = {}
    for entry in (spec.get("visualizations") or []):
        name = entry.get("name") or "viz"
        addr = (entry.get("address") or "").split(":")[-1]  # local:<Class> -> <Class>
        try:
            cls = reg[addr]
        except Exception:  # noqa: BLE001
            continue
        schema_keys = set(getattr(cls, "config_schema", {}) or {})
        cfg = {k: v for k, v in (entry.get("config") or {}).items() if k in schema_keys}
        try:
            out = cls(config=cfg, core=build_core()).update({})
            html = out.get("html") if isinstance(out, dict) else None
            if isinstance(html, str) and html.strip():
                panels[name] = html
        except Exception:  # noqa: BLE001 — one viz must not fail the run
            continue
    run_dir = ws_root / ".pbg" / "runs" / str(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "viz.json").write_text(json.dumps(panels, default=str), encoding="utf-8")
    return list(panels)

class VentCrossSection(Visualization):
    """Campaign-0 REAL 2-D vent cross-section — every pixel a FiPy cell.

    Runs the ``serpentinizing_vent_reactor`` composite step by step and snapshots
    the genuine 2-D finite-volume field each step (temperature, the reducing-power
    solute tracer, and the pH / porosity fields derived from the real transported
    solute). Renders (a) a STATIC settled cross-section of all four fields and
    (b) an ANIMATED temperature field — the vent lighting up and settling into the
    Lost City window. Cold acidic ocean on the left, the hot alkaline conduit on
    the right; the across-wall gradient is the defining vent structure.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign 0 — real 2-D vent cross-section (FiPy)"},
        "n_steps": {"_type": "integer", "_default": 60},
        "flow_velocity": {"_type": "float", "_default": 1.0e-3},
        "olivine_rate": {"_type": "float", "_default": 0.15},
        "max_frames": {"_type": "integer", "_default": 30},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    @staticmethod
    def _find_reactor(node):
        if isinstance(node, dict):
            inst = node.get("instance")
            if inst is not None and type(inst).__name__ == "FipyReactiveTransportProcess":
                return inst
            for v in node.values():
                r = VentCrossSection._find_reactor(v)
                if r is not None:
                    return r
        return None

    def update(self, state=None):
        from ..core import build_core
        from ..composites.vent_reactor import serpentinizing_vent_reactor
        from ..transport.fipy_reactor import spatial_field

        core = build_core()
        doc = serpentinizing_vent_reactor(
            core,
            flow_velocity=float(self.config["flow_velocity"]),
            olivine_rate=float(self.config["olivine_rate"]),
        )
        sim = Composite({"state": doc}, core=core)
        reactor = self._find_reactor(sim.state)
        # VIZ-ONLY cold start: build the mesh at seawater temperature and mark it
        # seeded so the reactor does NOT warm-start the field to the interface
        # temperature. The animation then shows the field heating up from cold —
        # the wall lighting up — instead of appearing near-settled from frame 1.
        # (The graded composite keeps its own warm-start; this is a separate run.)
        if reactor is not None:
            reactor._build()
            reactor._T.setValue(float(reactor.config["seawater_temp"]))
            reactor._S.setValue(0.0)
            reactor._seeded = True
        n = int(self.config["n_steps"])
        frames = []
        for _ in range(n):
            sim.run(1)
            rows = gather_emitter_results(sim)[("emitter",)]
            last = rows[-1] if rows else {}
            f = spatial_field(reactor, {
                "pH": float(last.get("pH", 9.4)),
                "pH_eq": float(last.get("pH_eq", 0.0) or 0.0),
                "porosity": float(last.get("porosity", 0.35)),
            })
            if f.get("nx"):
                f["t_c"] = [[v - 273.15 for v in row] for row in f["temperature"]]
                f["settled_T"] = float(last.get("temperature", 0.0)) - 273.15
                f["settled_pH"] = float(last.get("pH", 0.0))
                frames.append(f)
        return {"html": self._figure(frames)}

    def _figure(self, frames) -> str:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        if not frames:
            return "<p>No field produced (reactor did not step).</p>"
        last = frames[-1]
        ext = last["extent"]
        nx, ny = last["nx"], last["ny"]
        xs = [(i + 0.5) * (ext[1] / nx) * 100.0 for i in range(nx)]   # cm across the wall
        ys = [(j + 0.5) * (ext[3] / ny) * 100.0 for j in range(ny)]   # cm up the chimney
        ink = "#1e293b"

        # ---- STATIC: the four settled fields as a clean 2x2 ----
        stat = make_subplots(
            rows=2, cols=2, horizontal_spacing=0.17, vertical_spacing=0.15,
            subplot_titles=("Temperature (\u00b0C)", "pH  (acidic \u2192 alkaline)",
                            "Reducing power (H\u2082 + alkalinity)", "Porosity"))
        specs = [
            (last["t_c"], "Inferno", 1, 1, 0.42, 0.80),
            (last["pH"], "Tealgrn", 1, 2, 1.00, 0.80),
            (last["solute"], "Viridis", 2, 1, 0.42, 0.195),
            (last["porosity"], "YlOrBr", 2, 2, 1.00, 0.195),
        ]
        for z, cs, r, c, cbx, cby in specs:
            stat.add_trace(go.Heatmap(z=z, x=xs, y=ys, colorscale=cs,
                                      colorbar=dict(len=0.40, thickness=11, x=cbx, y=cby)),
                           row=r, col=c)
        # Precipitation front: a contour of the REAL porosity field at its midpoint —
        # where the alkaline vent fluid meets the ocean and the carbonate/brucite
        # chimney precipitates. Overlaid on the temperature panel (1,1).
        pz = last["porosity"]
        pflat = [v for rrow in pz for v in rrow]
        lvl = (min(pflat) + max(pflat)) / 2.0
        stat.add_trace(go.Contour(z=pz, x=xs, y=ys, showscale=False,
                                  contours=dict(start=lvl, end=lvl, coloring="lines"),
                                  line=dict(color="#e2e8f0", width=1.6, dash="dot"),
                                  hoverinfo="skip"), row=1, col=1)
        # Streamlines: contours of the stream function ψ ARE the streamlines of the
        # real Darcy–Boussinesq convection — the buoyant recirculation cell. Hot
        # conduit fluid rises, cold ocean fluid sinks. Overlaid on temperature (1,1).
        if last.get("psi"):
            stat.add_trace(go.Contour(z=last["psi"], x=xs, y=ys, showscale=False, ncontours=14,
                                      contours=dict(coloring="lines"),
                                      line=dict(color="rgba(255,255,255,0.55)", width=1.0),
                                      hoverinfo="skip"), row=1, col=1)
            xL, xR = xs[int(len(xs) * 0.20)], xs[int(len(xs) * 0.80)]
            y0, y1 = ys[int(len(ys) * 0.36)], ys[int(len(ys) * 0.64)]
            stat.add_annotation(x=xR, y=y1, ax=xR, ay=y0, xref="x", yref="y", axref="x", ayref="y",
                                showarrow=True, arrowhead=2, arrowwidth=1.5, arrowcolor="#fde68a", text="")
            stat.add_annotation(x=xL, y=y0, ax=xL, ay=y1, xref="x", yref="y", axref="x", ayref="y",
                                showarrow=True, arrowhead=2, arrowwidth=1.5, arrowcolor="#bae6fd", text="")
            stat.add_annotation(x=xR, y=ys[-1], xref="x", yref="y", text="rises", showarrow=False,
                                yshift=-12, yanchor="top", font=dict(size=9, color="#fde68a"))
            stat.add_annotation(x=xL, y=ys[0], xref="x", yref="y", text="sinks", showarrow=False,
                                yshift=-8, font=dict(size=9, color="#bae6fd"))
        stat.update_xaxes(showgrid=False, zeroline=False,
                          title_text="across the wall (cm)", title_font=dict(size=10))
        stat.update_yaxes(showgrid=False, zeroline=False,
                          title_text="up (cm)", title_font=dict(size=10))
        stat.update_layout(**S.base_layout(
            height=560, width=820,
            title=dict(text="Settled cross-section  \u00b7  cold acidic OCEAN (left)  \u2192  hot alkaline CONDUIT (right)",
                       font=dict(size=13, color=INK), x=0.5, xanchor="center"),
            margin=dict(l=55, r=20, t=58, b=50)))

        # ---- MOTION: the temperature field heating up (generous, uncramped) ----
        step = max(1, len(frames) // int(self.config["max_frames"]))
        keep = frames[::step] + [frames[-1]]
        zmin = min(min(min(r) for r in f["t_c"]) for f in keep)
        zmax = max(max(max(r) for r in f["t_c"]) for f in keep)
        def _flow(f):
            """Streamline overlay (\u03c8 contours) for a frame, if the field carries it."""
            if not f.get("psi"):
                return []
            return [go.Contour(z=f["psi"], x=xs, y=ys, showscale=False, ncontours=12,
                               contours=dict(coloring="lines"),
                               line=dict(color="rgba(255,255,255,0.45)", width=0.9),
                               hoverinfo="skip")]

        def _heat(f):
            return go.Heatmap(z=f["t_c"], x=xs, y=ys, colorscale="Inferno", zmin=zmin, zmax=zmax,
                              colorbar=dict(title="\u00b0C", thickness=13, len=0.9))

        anim = go.Figure(
            data=[_heat(keep[0])] + _flow(keep[0]),
            frames=[go.Frame(data=[_heat(f)] + _flow(f), name=str(i)) for i, f in enumerate(keep)])
        anim.update_xaxes(showgrid=False, zeroline=False, title_text="across the wall (cm)")
        anim.update_yaxes(showgrid=False, zeroline=False, title_text="up the chimney (cm)")
        anim.update_layout(
            template="plotly_white", height=460, width=760,
            title=dict(text="Temperature field heating up over the run", x=0.5, xanchor="center",
                       y=0.97, font=dict(size=14, color=ink)),
            margin=dict(l=60, r=20, t=100, b=70), font=dict(color=ink),
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.12, xanchor="left", yanchor="top",
                pad=dict(t=0, r=6), showactive=False, buttons=[
                    dict(label="\u25b6 Play", method="animate",
                         args=[None, dict(frame=dict(duration=90, redraw=True), fromcurrent=True)]),
                    dict(label="\u23f8 Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                ])],
            sliders=[dict(active=0, x=0.08, len=0.88, y=-0.16, pad=dict(t=0),
                currentvalue=dict(visible=False),
                steps=[dict(method="animate", label="",
                            args=[[str(i)], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                       for i in range(len(keep))])])

        cap_text = (
            "<b>A cross-section through the chimney wall</b> \u2014 a real 2-D FiPy finite-volume "
            "field, <b>every pixel a solved cell</b>. Cold acidic seawater bathes the outer wall "
            "(left); the hot alkaline serpentinized fluid percolates up the conduit (right). The "
            "<b>gradient across the wall</b> is the engine of the vent. White "
            "<b>streamlines (constant \u03c8)</b> trace the real Darcy\u2013Boussinesq "
            "convection: the hot conduit rises, the cold ocean sinks, a recirculation "
            "cell forms and stirs the field. "
            f"<b>Settled: {last['settled_T']:.0f}\u202f\u00b0C, pH {last['settled_pH']:.2f}</b> "
            "(the Lost City window).")
        s_html = stat.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        a_html = anim.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        inner = ("<div style='display:flex;justify-content:center'>" + s_html + "</div>"
                 "<div style='display:flex;justify-content:center;margin-top:8px'>" + a_html + "</div>")
        return S.frame(inner, title=(self.config.get("title") or "Real 2-D vent cross-section (FiPy)"),
                       phase="Campaign 0", view="World", tier="reproduction",
                       caption_text=cap_text, caption_prefix="How to read", tone="neutral", max_width=900)

class ProtonGradientProfile(Visualization):
    """Campaign-I REAL proton gradient across the Fe/Ni-S barrier — every value a
    FiPy cell. Runs the ``hydrothermal_carbon_fixation`` composite step by step and
    snapshots the genuine 1-D Nernst-Planck proton profile (ocean acidic → vent
    alkaline) each step, beside the molecular products (formate / acetate /
    pyruvate) the gradient drives. Static settled profile + an animated profile;
    the favorable (gradient_efficiency 1.0) vs Tutolo-2026 (~0.1) arm is a config.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign I — proton gradient → reduced carbon"},
        "n_steps": {"_type": "integer", "_default": 80},
        "gradient_efficiency": {"_type": "float", "_default": 1.0},
        "max_frames": {"_type": "integer", "_default": 30},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    @staticmethod
    def _find_gradient(node):
        if isinstance(node, dict):
            inst = node.get("instance")
            if inst is not None and type(inst).__name__ == "PhGradientNernstPlanckProcess":
                return inst
            for v in node.values():
                r = ProtonGradientProfile._find_gradient(v)
                if r is not None:
                    return r
        return None

    def update(self, state=None):
        from ..core import build_core
        from ..composites.carbon_fixation import hydrothermal_carbon_fixation
        from ..electrochemistry.ph_gradient import spatial_profile

        core = build_core()
        doc = hydrothermal_carbon_fixation(
            core, gradient_efficiency=float(self.config["gradient_efficiency"]))
        sim = Composite({"state": doc}, core=core)
        grad = self._find_gradient(sim.state)
        n = int(self.config["n_steps"])
        profiles, rows = [], []
        for _ in range(n):
            sim.run(1)
            rows = gather_emitter_results(sim)[("emitter",)]
            p = spatial_profile(grad)
            if p.get("x_cm"):
                profiles.append(p)
        return {"html": self._figure(profiles, rows)}

    def _figure(self, profiles, rows) -> str:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        from ..composites.carbon_fixation import hydrothermal_carbon_fixation

        if not profiles:
            return "<p>No proton profile produced.</p>"
        ink, teal, amber, rust = "#1e293b", "#0d9488", "#d97706", "#b91c1c"
        last = profiles[-1]
        x = last["x_cm"]
        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)],
                                hydrothermal_carbon_fixation)

        def col(k):
            return [r.get(k) for r in rows if k in r]

        # static: settled proton profile + products + the chemiosmotic back-pressure
        # (open-circuit vs loaded pmf — the gap is the proton-motive force SPENT
        # fixing carbon, the stoichiometric proton budget drawing the gradient down).
        stat = make_subplots(rows=1, cols=3, horizontal_spacing=0.085,
            subplot_titles=("Settled pH profile across the barrier",
                            "Reduced-carbon products (M)",
                            "Chemiosmotic back-pressure"))
        stat.add_hrect(y0=9.0, y1=11.0, line_width=0, fillcolor=teal, opacity=0.06, row=1, col=1)
        stat.add_scatter(x=x, y=last["pH"], mode="lines", line=dict(color=teal, width=3),
                         name="pH", row=1, col=1, showlegend=False)
        stat.add_annotation(x=x[0], y=last["pH"][0], text="◀ ocean (acidic)", showarrow=False,
                            font=dict(size=10, color="#2563eb"), xanchor="left", row=1, col=1)
        stat.add_annotation(x=x[-1], y=last["pH"][-1], text="vent (alkaline) ▶", showarrow=False,
                            font=dict(size=10, color="#b45309"), xanchor="right", row=1, col=1)
        for k, c in (("formate", teal), ("acetate", amber), ("pyruvate", rust)):
            y = col(k)
            if y:
                stat.add_scatter(x=t, y=y, mode="lines", line=dict(color=c, width=2.5),
                                 name=k, row=1, col=2)
        # back-pressure: open-circuit (what the gradient could give) vs loaded
        # (what fixation actually sees); shade the gap = pmf spent on carbon fixation.
        pmf_open = col("pmf_open"); pmf_load = col("pmf")
        if pmf_open and pmf_load:
            po_mv = [v * 1000.0 for v in pmf_open]; pl_mv = [v * 1000.0 for v in pmf_load]
            stat.add_scatter(x=t, y=po_mv, mode="lines", name="pmf open-circuit",
                             line=dict(color="#94a3b8", width=2, dash="dash"), row=1, col=3)
            stat.add_scatter(x=t, y=pl_mv, mode="lines", name="pmf loaded (fixation sees)",
                             line=dict(color="#7c3aed", width=2.6), fill="tonexty",
                             fillcolor="rgba(124,58,237,0.13)", row=1, col=3)
            imin = min(range(len(pl_mv)), key=lambda i: pl_mv[i])
            stat.add_annotation(x=t[imin], y=0.5 * (po_mv[imin] + pl_mv[imin]),
                                text="pmf spent<br>fixing carbon", showarrow=True, arrowhead=2,
                                ax=32, ay=0, font=dict(size=9, color="#7c3aed"), row=1, col=3)
        stat.update_xaxes(title_text="across the barrier (cm)", row=1, col=1, showgrid=False)
        stat.update_xaxes(title_text=tlabel, row=1, col=2, showgrid=True, gridcolor="#eef2f7")
        stat.update_xaxes(title_text=tlabel, row=1, col=3, showgrid=True, gridcolor="#eef2f7")
        stat.update_yaxes(title_text="pH", row=1, col=1, showgrid=True, gridcolor="#eef2f7")
        stat.update_yaxes(title_text="concentration (M, log)", type="log", row=1, col=2,
                          showgrid=True, gridcolor="#eef2f7")
        stat.update_yaxes(title_text="pmf (mV)", row=1, col=3, showgrid=True, gridcolor="#eef2f7")
        pmf_o = (pmf_open[-1] * 1000.0) if pmf_open else 0.0
        pmf_sag = (min(pmf_load) * 1000.0) if pmf_load else 0.0
        stat.update_layout(**S.base_layout(
            height=430, width=1180, showlegend=True,
            legend=dict(orientation="h", y=-0.17, x=0.5, xanchor="center", font=dict(size=10)),
            title=dict(text=f"pmf open {pmf_o:.0f} mV, sags to {pmf_sag:.0f} mV under load",
                       font=dict(size=13, color=INK), x=0.5, xanchor="center"),
            margin=dict(l=55, r=20, t=56, b=70)))

        # motion: the reduced-carbon products ACCUMULATING over the run, as the
        # REAL concentrations on a log axis (formate ~0.2 M is 20,000x pyruvate's
        # ~1e-5 M — the hierarchy IS the point). The lines reveal over time so you
        # watch formate shoot up first, then the slower trace products.
        fo, ac, py = col("formate"), col("acetate"), col("pyruvate")
        npts = min(len(fo), len(ac), len(py))
        tt = t[:npts]
        series = [("formate", fo, teal), ("acetate", ac, amber), ("pyruvate", py, rust)]
        fstep = max(1, npts // int(self.config["max_frames"]))
        idxs = [k for k in range(2, npts, fstep)] + ([npts - 1] if npts > 2 else [])
        def _rev(k):
            return [go.Scatter(x=tt[:k + 1], y=[max(v, 1e-9) for v in s[:k + 1]],
                               mode="lines", line=dict(color=c, width=2.6), name=nm)
                    for nm, s, c in series]
        yhi = max([max(fo or [1e-9]), max(ac or [1e-9]), max(py or [1e-9]), 1e-9])
        import math as _m
        anim = go.Figure(
            data=_rev(idxs[0]) if idxs else _rev(0),
            frames=[go.Frame(data=_rev(k), name=str(j)) for j, k in enumerate(idxs)])
        anim.update_xaxes(title_text=tlabel, range=[0, tt[-1] if tt else 1],
                          showgrid=True, gridcolor="#eef2f7")
        anim.update_yaxes(type="log", title_text="concentration (M)",
                          range=[-6, _m.ceil(_m.log10(yhi) + 0.3)],
                          showgrid=True, gridcolor="#eef2f7")
        anim.update_layout(
            template="plotly_white", height=420, width=620, showlegend=True,
            legend=dict(orientation="h", y=1.13, x=1.0, xanchor="right", yanchor="bottom",
                        font=dict(size=11), bgcolor="rgba(255,255,255,0.6)"),
            title=dict(text="products forming over time (real concentrations, log scale)",
                       x=0.5, xanchor="center", y=0.98, font=dict(size=13, color=ink)),
            margin=dict(l=60, r=20, t=100, b=60), font=dict(color=ink),
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.13, xanchor="left",
                yanchor="bottom", showactive=False, buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, dict(frame=dict(duration=90, redraw=True), fromcurrent=True)]),
                    dict(label="⏸ Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                ])],
            sliders=[dict(active=0, x=0.08, len=0.88, y=-0.12, currentvalue=dict(visible=False),
                steps=[dict(method="animate", label="",
                            args=[[str(i)], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                       for i in range(len(idxs))])])

        cap_text = (
            "<b>The proton gradient that powers the first carbon fixation</b> — the real 1-D "
            "Nernst-Planck proton profile across the Fe/Ni-S barrier (every value a FiPy cell), "
            "from the acidic ocean to the alkaline vent. That gradient is the proton-motive force "
            "driving H₂ + CO₂ → formate / acetate / pyruvate (right).")
        s_html = stat.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        a_html = anim.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        inner = ("<div style='display:flex;justify-content:center'>" + s_html + "</div>"
                 "<div style='display:flex;justify-content:center;margin-top:8px'>" + a_html + "</div>")
        return S.frame(inner, title=(self.config.get("title") or "Proton gradient → reduced carbon"),
                       phase="Campaign I", view="World", tier="mechanistic_prediction",
                       caption_text=cap_text, caption_prefix="How to read", tone="neutral", max_width=1000)

class ProtometabolicNetwork(Visualization):
    """Campaign-II REAL rTCA-fragment network igniting — every value a libRoadRunner
    concentration. Runs the ``protometabolic_network`` composite step by step and
    snapshots the live species concentrations each tick, laid out as the reaction
    graph (pyruvate + CO2 → the autocatalytic OAA hub → acetate + the reductive
    branch). Static settled network + an animation of it lighting up, beside the
    autocatalytic gain and net carbon throughput (does it self-amplify + sustain
    under washout?).
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign II — the protometabolic network igniting"},
        "n_steps": {"_type": "integer", "_default": 60},
        "k_rtca": {"_type": "float", "_default": 800.0},
        "max_frames": {"_type": "integer", "_default": 30},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    @staticmethod
    def _find_net(node):
        if isinstance(node, dict):
            inst = node.get("instance")
            if inst is not None and type(inst).__name__ == "RoadRunnerNetworkProcess":
                return inst
            for v in node.values():
                r = ProtometabolicNetwork._find_net(v)
                if r is not None:
                    return r
        return None

    def update(self, state=None):
        from ..core import build_core
        from ..composites.protometabolism import protometabolic_network
        from ..protometabolism.network import network_state

        core = build_core()
        doc = protometabolic_network(core, k_rtca=float(self.config["k_rtca"]))
        sim = Composite({"state": doc}, core=core)
        net = self._find_net(sim.state)
        n = int(self.config["n_steps"])
        snaps, rows = [], []
        for _ in range(n):
            sim.run(1)
            rows = gather_emitter_results(sim)[("emitter",)]
            s = network_state(net)
            snaps.append(s["conc"])
        topo = network_state(net)
        return {"html": self._figure(snaps, rows, topo)}

    def _figure(self, snaps, rows, topo) -> str:
        import math as _m
        import plotly.graph_objects as go

        if not snaps:
            return "<p>No network snapshots produced.</p>"
        ink, teal, amber, rust = "#1e293b", "#0d9488", "#d97706", "#b91c1c"
        sp = topo["species"]; pos = topo["pos"]; edges = topo["edges"]
        xn = [pos[s][0] for s in sp]; yn = [pos[s][1] for s in sp]
        gmax = max(max(c for c in snap) for snap in snaps) or 1e-9

        def node_trace(conc, show_text=True):
            sizes = [12 + 46 * _m.sqrt(max(c, 0) / gmax) for c in conc]
            txt = ["%s<br>%.2g M" % (s, c) for s, c in zip(sp, conc)]
            return go.Scatter(
                x=xn, y=yn, mode="markers+text" if show_text else "markers",
                marker=dict(size=sizes, color=conc, colorscale="Viridis", cmin=0, cmax=gmax,
                            line=dict(color="#334155", width=1.2),
                            colorbar=dict(title="M", thickness=12, len=0.8)),
                text=sp, textposition="bottom center", textfont=dict(size=8, color="#1e293b"),
                hovertext=txt, hoverinfo="text")

        # edge lines weighted by the LIVE libRoadRunner reaction flux — the living
        # flux map: thick edges carry most of the carbon. Falls back to uniform
        # edges if no flux is available.
        redges = topo.get("reaction_edges") or []
        fmax = max((abs(e["rate"]) for e in redges), default=0.0) or 1e-12
        if redges:
            edge_traces = [go.Scatter(
                x=[pos[e["src"]][0], pos[e["dst"]][0]], y=[pos[e["src"]][1], pos[e["dst"]][1]],
                mode="lines", line=dict(color="rgba(13,148,136,0.55)",
                                        width=1.2 + 7.0 * (abs(e["rate"]) / fmax)),
                hovertext="%s: %.1e" % (e["reaction"], e["rate"]), hoverinfo="text")
                for e in redges]
        else:
            ex, ey = [], []
            for a, b in edges:
                ex += [pos[a][0], pos[b][0], None]; ey += [pos[a][1], pos[b][1], None]
            edge_traces = [go.Scatter(x=ex, y=ey, mode="lines",
                                      line=dict(color="#cbd5e1", width=2), hoverinfo="skip")]

        def col(k):
            return [r.get(k) for r in rows if k in r]
        from ..composites.protometabolism import protometabolic_network
        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)],
                                protometabolic_network)

        # ---- STATIC: settled network (left) + gain & flux (right) via two figures
        net_fig = go.Figure(edge_traces + [node_trace(snaps[-1])])
        net_fig.add_annotation(x=pos["OAA"][0], y=pos["OAA"][1] + 0.22,
                               text="⟳ autocatalytic<br>OAA + 2CO₂ → 2 OAA + acetate",
                               showarrow=False, font=dict(size=9, color=rust))
        net_fig.update_xaxes(visible=False, range=[-0.9, 3.05])
        net_fig.update_yaxes(visible=False, range=[-0.3, 1.15])
        net_fig.update_layout(template="plotly_white", height=360, width=560, showlegend=False,
            title=dict(text="Settled network (node size = concentration, edge width = live flux)", x=0.5, xanchor="center",
                       font=dict(size=13, color=ink)),
            margin=dict(l=10, r=10, t=50, b=10), font=dict(color=ink))

        gain = col("autocatalytic_gain"); flux = col("net_carbon_flux")
        dyn = go.Figure()
        if gain:
            dyn.add_hline(y=1.0, line=dict(color="#94a3b8", width=1, dash="dot"))
            dyn.add_scatter(x=t, y=gain, mode="lines", line=dict(color=rust, width=2.5),
                            name="autocatalytic gain")
        if flux:
            dyn.add_scatter(x=t, y=flux, mode="lines", yaxis="y2",
                            line=dict(color=teal, width=2.5), name="net carbon flux")
        dyn.update_layout(template="plotly_white", height=360, width=520, showlegend=True,
            legend=dict(orientation="h", y=1.14, x=1.0, xanchor="right", font=dict(size=10)),
            title=dict(text="does it ignite? gain > 1 + sustained flux", x=0.5, xanchor="center",
                       y=0.98, font=dict(size=13, color=ink)),
            xaxis=dict(title=tlabel, showgrid=True, gridcolor="#eef2f7"),
            yaxis=dict(title="autocatalytic gain", showgrid=True, gridcolor="#eef2f7"),
            yaxis2=dict(title="net carbon flux (mol/s)", overlaying="y", side="right", showgrid=False),
            margin=dict(l=55, r=60, t=70, b=50), font=dict(color=ink))

        # ---- MOTION: the network igniting ----
        step = max(1, len(snaps) // int(self.config["max_frames"]))
        keep = list(range(0, len(snaps), step)) + [len(snaps) - 1]
        anim = go.Figure(
            data=edge_traces + [node_trace(snaps[keep[0]])],
            frames=[go.Frame(data=edge_traces + [node_trace(snaps[k])], name=str(j))
                    for j, k in enumerate(keep)])
        anim.update_xaxes(visible=False, range=[-0.9, 3.05])
        anim.update_yaxes(visible=False, range=[-0.3, 1.15])
        anim.update_layout(template="plotly_white", height=380, width=620, showlegend=False,
            title=dict(text="the network igniting (real libRoadRunner)", x=0.5, xanchor="center",
                       y=0.99, font=dict(size=13, color=ink)),
            margin=dict(l=10, r=10, t=70, b=50), font=dict(color=ink),
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.1, xanchor="left",
                yanchor="bottom", showactive=False, buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, dict(frame=dict(duration=110, redraw=True), fromcurrent=True)]),
                    dict(label="⏸ Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                ])],
            sliders=[dict(active=0, x=0.08, len=0.88, y=-0.08, currentvalue=dict(visible=False),
                steps=[dict(method="animate", label="",
                            args=[[str(i)], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                       for i in range(len(keep))])])

        cap_text = (
            "<b>The first metabolism, igniting</b> — the real libRoadRunner rTCA-fragment network: "
            "pyruvate + CO₂ feed the <b>autocatalytic OAA hub</b> (OAA + 2 CO₂ → 2 OAA + acetate), "
            "which drives the reductive branch (malate, succinate) and acetate under continuous "
            "feed + washout. Node size is the live concentration; the network lights up as it "
            "self-amplifies.")
        n_html = net_fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        d_html = dyn.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        a_html = anim.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        inner = ("<div style='display:flex;flex-wrap:wrap;gap:10px;justify-content:center;align-items:flex-start'>"
                 f"<div>{n_html}</div><div>{d_html}</div></div>"
                 "<div style='display:flex;justify-content:center;margin-top:8px'>" + a_html + "</div>")
        return S.frame(inner, title=(self.config.get("title") or "The protometabolic network igniting"),
                       phase="Campaign II", view="Mechanism", tier="mechanistic_prediction",
                       caption_text=cap_text, caption_prefix="How to read", tone="neutral", max_width=1000)

class ThermophoreticTrapViz(Visualization):
    """Campaign-III REAL thermal trap — the accumulation column and the geometric
    threshold at which a localized "individual" forms. Runs ``ThermophoreticTrapProcess``
    across a porosity sweep (open pore → confined), reads the steady accumulation
    column c(z) = exp(beta·(L−z)) and the enrichment from the FiPy-solved rate, and
    renders the concentration profile + the enrichment-vs-porosity threshold, plus
    an animation of the pore closing and the individual emerging. Every value a real
    trap solve (Baaske 2007)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign III — the thermal trap concentrates an individual"},
        "flow_velocity": {"_type": "float", "_default": 1.0e-4},
        "pore_length": {"_type": "float", "_default": 5.0e-3},
        "delta_T": {"_type": "float", "_default": 30.0},
        "n_porosity": {"_type": "integer", "_default": 22},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import numpy as np

        from ..core import build_core
        from ..transport.thermophoretic_trap import ThermophoreticTrapProcess, trap_profile
        core = build_core()
        flow = float(self.config["flow_velocity"])
        L = float(self.config["pore_length"])
        dT = float(self.config["delta_T"])
        por_grid = list(np.linspace(0.95, 0.1, int(self.config["n_porosity"])))
        sweep = []   # (porosity, enrichment, profile)
        for por in por_grid:
            p = ThermophoreticTrapProcess(config={"pore_length": L, "delta_T": dT}, core=core)
            for _ in range(4):
                p.update({"temperature": 333.15, "flow_velocity": flow, "porosity": float(por)}, 1.0)
            prof = trap_profile(p)
            sweep.append((float(por), prof["enrichment"], prof))
        return {"html": self._figure(sweep)}

    def _figure(self, sweep) -> str:
        import math

        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        if not sweep:
            return "<p>No trap sweep produced.</p>"
        ink, teal, rust, amber = INK, TEAL, RUST, AMBER
        por = [s[0] for s in sweep]
        enr = [s[1] for s in sweep]
        log_enr = [math.log10(max(e, 1.0)) for e in enr]
        fav = sweep[-1][2]           # most confined = favorable
        z = fav["z_mm"]; cprof = [math.log10(max(c, 1.0)) for c in fav["conc"]]
        # Localization threshold: where the trap first concentrates the feed above the
        # dilute background. Keyed to a modest, RESOLVABLE enrichment (10x), not the
        # extreme reduced-model fold, which a resolved FEM does not confirm.
        thr = next((p for p, e in zip(por, enr) if e >= 10.0), None)
        # The resolved-FEM saturation ceiling (dolfinx, spatial-transport cross-check):
        # above it the reduced exp(Pe) column is an unconfirmed extrapolation.
        resolved_log = math.log10(253.0)
        top = max(max(log_enr) * 1.05, resolved_log + 0.5)

        stat = make_subplots(rows=1, cols=2, horizontal_spacing=0.13,
            subplot_titles=("Accumulation column in the favorable pore",
                            "Enrichment vs porosity (bounded)"))
        stat.add_scatter(x=cprof, y=z, mode="lines", line=dict(color=teal, width=3),
                         name="log10 c(z)", row=1, col=1, showlegend=False)
        stat.add_annotation(x=cprof[0], y=z[0], text="base (trapped) ▲", showarrow=False,
                            font=dict(size=10, color=rust), xanchor="left", row=1, col=1)
        stat.add_annotation(x=cprof[-1], y=z[-1], text="feed (dilute) ▼", showarrow=False,
                            font=dict(size=10, color="#2563eb"), xanchor="left", row=1, col=1)
        stat.add_scatter(x=por, y=log_enr, mode="lines+markers", line=dict(color=amber, width=2.6),
                         marker=dict(size=5), name="reduced exp(Pe) column", row=1, col=2, showlegend=False)
        # Honest-uncertainty wash: everything above the resolved-FEM ceiling is a
        # reduced-model extrapolation, not a resolved enrichment.
        stat.add_hrect(y0=resolved_log, y1=top, line_width=0, fillcolor=S.SENSITIVE_FILL, row=1, col=2)
        stat.add_hline(y=resolved_log, line=dict(color=teal, dash="dot"), row=1, col=2)
        stat.add_annotation(x=0.5, y=resolved_log, xref="x2", yref="y2", yshift=9, showarrow=False,
                            text="resolved FEM saturates here — folds above are reduced-model only",
                            font=dict(size=9, color=teal))
        if thr is not None:
            stat.add_vline(x=thr, line=dict(color=teal, dash="dash"), row=1, col=2)
            stat.add_annotation(x=thr, y=0.3, text="localization<br>onset", showarrow=False,
                                font=dict(size=9, color=teal), row=1, col=2)
        stat.update_xaxes(title_text="log10 concentration (fold)", row=1, col=1, showgrid=True, gridcolor=S.GRID)
        stat.update_yaxes(title_text="height up the pore (mm)", row=1, col=1, showgrid=True, gridcolor=S.GRID)
        stat.update_xaxes(title_text="porosity (open → confined)", autorange="reversed", row=1, col=2,
                          showgrid=True, gridcolor=S.GRID)
        stat.update_yaxes(title_text="log10 enrichment (fold)", row=1, col=2, range=[0, top],
                          showgrid=True, gridcolor=S.GRID)
        stat.update_layout(**S.base_layout(height=430, width=900, showlegend=False,
            margin=dict(l=60, r=20, t=40, b=60)))

        # motion: the pore closing — the accumulation column building as porosity
        # drops (the individual emerging from the dilute feed).
        xmax = max(cprof) * 1.08 + 0.3
        frames = []
        for p, e, prof in sweep:
            cp = [math.log10(max(c, 1.0)) for c in prof["conc"]]
            frames.append(go.Frame(data=[go.Scatter(x=cp, y=prof["z_mm"], mode="lines",
                          line=dict(color=teal, width=3), fill="tozerox",
                          fillcolor="rgba(13,148,136,0.12)")],
                          name="%.2f" % p,
                          layout=go.Layout(annotations=[dict(x=xmax * 0.5, y=max(prof["z_mm"]) * 0.9,
                              text="porosity %.2f" % p, showarrow=False,
                              font=dict(size=12, color=ink))])))
        anim = go.Figure(data=frames[0].data, frames=frames)
        anim.update_xaxes(title_text="log10 concentration (fold)", range=[0, xmax],
                          showgrid=True, gridcolor="#eef2f7")
        anim.update_yaxes(title_text="height up the pore (mm)", showgrid=True, gridcolor="#eef2f7")
        anim.update_layout(template="plotly_white", height=430, width=560, showlegend=False,
            title=dict(text="the pore closing → the individual emerging", x=0.5, xanchor="center",
                       y=0.99, font=dict(size=13, color=ink)),
            margin=dict(l=60, r=20, t=70, b=55), font=dict(color=ink),
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.1, xanchor="left",
                yanchor="bottom", showactive=False, buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, dict(frame=dict(duration=140, redraw=True), fromcurrent=True)]),
                    dict(label="⏸ Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                ])],
            sliders=[dict(active=0, x=0.08, len=0.88, y=-0.1, currentvalue=dict(visible=False),
                steps=[dict(method="animate", label="",
                            args=[[f.name], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                       for f in frames])])

        s_html = stat.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        a_html = anim.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        inner = (f"<div style='display:flex;justify-content:center'>{s_html}</div>"
                 f"<div style='display:flex;justify-content:center;margin-top:8px'>{a_html}</div>")
        cap = (
            "The real FiPy thermal trap (thermophoresis + convection, Baaske 2007) concentrates the "
            "dilute feed exponentially up a confined pore (left); as the pore closes, enrichment crosses "
            "the localization onset and an open pore just washes the feed through. <b>Localization is "
            "real and bounded</b> — the amber band marks where the reduced <i>exp(Pe)</i> column climbs "
            "past what a resolved FEM confirms, so the extreme folds are a reduced-model extrapolation. "
            "The resolved Decision view is the FiPy&harr;FEM solver-sensitivity figure; see "
            "<code>workspace/references/spatial-transport-solver-comparison.md</code>."
        )
        return S.frame(inner, title=(self.config.get("title") or "The thermal trap concentrates an individual"),
                       phase="Campaign III", view="World", tier="mechanistic_prediction",
                       caption_text=cap, caption_prefix="How to read", tone="caution", max_width=960)


class ThermophoreticTrap3D(Visualization):
    """og-03 World view in 3-D: the real thermophoretic trap's accumulation column
    rendered as a pore. The pore is drawn as a cylinder coloured by the steady
    log-concentration up its length — dense (trapped) at the hot base, dilute at the
    cold feed end — from one run of the real ``ThermophoreticTrapProcess``. Honest:
    this is the reduced-model column; the resolved FEM bounds the fold (see the
    FiPy↔FEM solver-sensitivity Decision view)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Inside the pore — the accumulation column in 3-D"},
        "flow_velocity": {"_type": "float", "_default": 1.0e-4},
        "pore_length": {"_type": "float", "_default": 5.0e-3},
        "delta_T": {"_type": "float", "_default": 30.0},
        "porosity": {"_type": "float", "_default": 0.15},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import math

        import numpy as np
        import plotly.graph_objects as go

        from ..core import build_core
        from ..transport.thermophoretic_trap import ThermophoreticTrapProcess, trap_profile
        core = build_core()
        p = ThermophoreticTrapProcess(
            config={"pore_length": float(self.config["pore_length"]), "delta_T": float(self.config["delta_T"])},
            core=core)
        for _ in range(4):
            p.update({"temperature": 333.15, "flow_velocity": float(self.config["flow_velocity"]),
                      "porosity": float(self.config["porosity"])}, 1.0)
        prof = trap_profile(p)
        z = np.asarray(prof["z_mm"], dtype=float)                       # base..top (mm)
        conc = np.asarray(prof["conc"], dtype=float)
        enr = float(prof.get("enrichment", conc.max() / max(conc.min(), 1e-30)))
        logc = np.log10(np.clip(conc, 1.0, None))                      # fold (log10)

        # The pore as a cylinder, coloured up its length by the log-concentration.
        theta = np.linspace(0, 2 * np.pi, 48)
        R = 0.12 * (z.max() - z.min() + 1e-9)                          # a slender pore
        TH, ZZ = np.meshgrid(theta, z)
        X, Y = R * np.cos(TH), R * np.sin(TH)
        C = np.repeat(logc[:, None], theta.size, axis=1)
        resolved_log = math.log10(253.0)                              # resolved-FEM ceiling
        fig = go.Figure(go.Surface(
            x=X, y=Y, z=ZZ, surfacecolor=C, colorscale="YlOrRd", cmin=0.0, cmax=float(logc.max()),
            colorbar=dict(title="log₁₀<br>fold", thickness=12, len=0.7, x=0.9,
                          title_font=dict(size=11), tickfont=dict(size=9)),
            contours={"z": {"show": True, "color": "rgba(255,255,255,0.25)", "width": 1,
                            "start": 0, "end": float(logc.max()), "size": max(float(logc.max()) / 8, 0.3)}},
            hovertemplate="height %{z:.2f} mm<br>fold 10^%{surfacecolor:.1f}×<extra></extra>", showscale=True))
        # hot base / cold feed labels — offset outside the cylinder so they read clearly
        fig.add_trace(go.Scatter3d(x=[R * 2.1, R * 2.1], y=[0, 0], z=[z.min(), z.max()], mode="markers+text",
                                   text=["hot base — trapped", "cold feed — dilute"], textposition="middle right",
                                   textfont=dict(size=11, color=S.INK), marker=dict(size=5, color=[S.RUST, S.SLATE]),
                                   showlegend=False, hoverinfo="skip"))
        fig.update_layout(**S.base_layout(height=560, margin=dict(l=0, r=0, t=10, b=0),
                                          showlegend=False, scene=S.scene_3d(
                                              zaxis=dict(title="height up the pore (mm)"),
                                              xaxis=dict(visible=False), yaxis=dict(visible=False),
                                              aspectratio=dict(x=1, y=1, z=2.0))))
        cap = (
            f"One run of the real FiPy thermophoretic trap: the pore concentrates the dilute feed "
            f"exponentially toward its hot base (reduced-model peak &asymp; {enr:.0e}&times;). This is the "
            f"reduced accumulation column &mdash; the <b>resolved FEM bounds the fold</b> near a few-hundred-fold "
            f"(10<sup>{resolved_log:.1f}</sup>&times;) past the resolvable P&eacute;clet, so localization is real "
            f"but <b>bounded</b>. See the FiPy&harr;FEM solver-sensitivity Decision view for the resolved statement."
        )
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        html = S.frame(inner, title=(self.config.get("title") or "Inside the pore — the accumulation column in 3-D"),
                       phase="Campaign III", view="World", tier="mechanistic_prediction",
                       caption_text=cap, caption_prefix="How to read", tone="caution", max_width=820)
        return {"html": html}


class VentChimney3D(Visualization):
    """og-00 World view in 3-D: the alkaline vent chimney as a tapered column coloured
    by the real settled temperature up its height — the hot serpentinizing conduit at
    the base cooling into cold ocean — from one run of the real PHREEQC + FiPy
    ``serpentinizing_vent_reactor``. The Lost City habitability window (40–91 °C) is
    marked on the chimney. The geometry is schematic; the temperature up the conduit
    is the real settled field."""

    config_schema = {
        "title": {"_type": "string", "_default": "The vent wall in 3-D — the across-wall thermal gradient"},
        "n_steps": {"_type": "integer", "_default": 60},
        "flow_velocity": {"_type": "float", "_default": 1.0e-3},
        "olivine_rate": {"_type": "float", "_default": 0.15},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import numpy as np
        import plotly.graph_objects as go

        from ..core import build_core
        from ..composites.vent_reactor import serpentinizing_vent_reactor
        from ..transport.fipy_reactor import spatial_field
        core = build_core()
        doc = serpentinizing_vent_reactor(core, flow_velocity=float(self.config["flow_velocity"]),
                                          olivine_rate=float(self.config["olivine_rate"]))
        sim = Composite({"state": doc}, core=core)
        reactor = VentCrossSection._find_reactor(sim.state)
        sim.run(int(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        last = rows[-1] if rows else {}
        f = spatial_field(reactor, {"pH": float(last.get("pH", 9.4)),
                                    "pH_eq": float(last.get("pH_eq", 0.0) or 0.0),
                                    "porosity": float(last.get("porosity", 0.35))})
        if not f.get("nx"):
            return {"html": "<p>vent reactor produced no field.</p>"}
        t_c = np.asarray([[v - 273.15 for v in row] for row in f["temperature"]], dtype=float)  # [up, across]
        ny, nx = t_c.shape
        ext = f.get("extent", [0, 1, 0, 1])
        xs = np.array([(i + 0.5) * (ext[1] / nx) for i in range(nx)]) * 100.0   # cm across the wall
        ys = np.array([(j + 0.5) * (ext[3] / ny) for j in range(ny)]) * 100.0   # cm up the chimney

        # The vent wall as a thermal landscape: elevation + colour = the real settled
        # temperature over (across × up) — the hot serpentinizing conduit rises as a
        # ridge and cools toward the cold ocean; every cell a FiPy solve.
        lo, hi = float(t_c.min()), float(t_c.max())
        fig = go.Figure(go.Surface(
            x=xs, y=ys, z=t_c, surfacecolor=t_c, colorscale="Inferno", cmin=lo, cmax=hi,
            colorbar=dict(title="°C", thickness=12, len=0.7, x=0.92, title_font=dict(size=11), tickfont=dict(size=9)),
            contours={"z": {"show": 40.0 <= hi and lo <= 91.0, "start": 40.0, "end": 91.0, "size": 51.0,
                            "color": S.TEAL, "width": 3}},
            hovertemplate="across %{x:.1f} cm · up %{y:.1f} cm<br>%{z:.0f} °C<extra></extra>", showscale=True))
        fig.update_layout(**S.base_layout(height=580, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
                                          scene=S.scene_3d(
                                              xaxis=dict(title="across the wall (cm)"),
                                              yaxis=dict(title="up the chimney (cm)"),
                                              zaxis=dict(title="temperature (°C)"),
                                              camera=dict(eye=dict(x=1.6, y=1.5, z=1.25)),
                                              aspectmode="cube")))
        cap = (
            "One run of the real PHREEQC + FiPy serpentinizing vent reactor, as a thermal landscape over the "
            "wall: the hot serpentinizing conduit rises as a ridge and cools toward the cold ocean (every cell "
            "a FiPy solve). The teal contours bracket the <b>Lost City habitability window</b> (40–91 °C). This "
            "across-wall cold-ocean → hot-conduit gradient is the defining vent structure a cell would form in."
        )
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return {"html": S.frame(inner, title=(self.config.get("title") or "The vent wall in 3-D — the across-wall thermal gradient"),
                                phase="Campaign 0", view="World", tier="reproduction",
                                caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=820)}


class ProtocellVesicle3D(Visualization):
    """og-04 World view in 3-D: the protocell as a vesicle — a semi-transparent
    amphiphile membrane around a lumen coloured by the measured RETENTION, with inward
    import arrows sized by the measured ACCESS, from one run of the real
    ``mixed_amphiphile_protocell``. The geometry is schematic; retention / access /
    individuality are measured."""

    config_schema = {
        "title": {"_type": "string", "_default": "The protocell in 3-D — a boundary that retains without isolating"},
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
        import numpy as np
        import plotly.graph_objects as go

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
        r = rows[-1] if rows else {}
        retention = float(r.get("retention", 0.0))
        access = float(r.get("access", 0.0))
        individ = float(r.get("individuality_access", retention * access))
        viable = float(r.get("viable_compartments", 0.0))

        u = np.linspace(0, 2 * np.pi, 48)
        v = np.linspace(0, np.pi, 24)
        U, V = np.meshgrid(u, v)
        sx, sy, sz = np.cos(U) * np.sin(V), np.sin(U) * np.sin(V), np.cos(V)
        fig = go.Figure()
        # membrane shell — semi-transparent; tighter (thicker look) as retention rises
        fig.add_trace(go.Surface(x=sx, y=sy, z=sz, surfacecolor=np.zeros_like(sx), showscale=False,
                                 colorscale=[[0, "rgba(30,41,59,0.18)"], [1, "rgba(30,41,59,0.18)"]],
                                 opacity=0.18, hoverinfo="skip"))
        # lumen — retained internal chemistry, colour intensity ∝ retention
        rl = 0.82
        fig.add_trace(go.Surface(x=rl * sx, y=rl * sy, z=rl * sz, surfacecolor=np.full_like(sx, retention),
                                 colorscale=[[0, "#e2e8f0"], [1, S.TEAL]], cmin=0, cmax=1,
                                 colorbar=dict(title="retention", thickness=12, len=0.6, x=0.92,
                                               title_font=dict(size=10), tickfont=dict(size=9)),
                                 opacity=0.95, hovertemplate="retained internal product<br>retention %{surfacecolor:.2f}<extra></extra>"))
        # inward import arrows — count / length ∝ access (the permeable boundary lets the gradient in)
        n_arr = max(3, int(round(4 + 10 * access)))
        au = np.linspace(0, 2 * np.pi, n_arr, endpoint=False)
        av = np.full(n_arr, np.pi / 2) + 0.5 * np.sin(2 * au)
        ax_, ay_, az_ = np.cos(au) * np.sin(av), np.sin(au) * np.sin(av), np.cos(av)
        start = 1.55
        fig.add_trace(go.Cone(x=start * ax_, y=start * ay_, z=start * az_,
                              u=-ax_, v=-ay_, w=-az_, anchor="tail", showscale=False,
                              colorscale=[[0, S.AMBER], [1, S.AMBER]], sizemode="scaled",
                              sizeref=0.6 + 0.8 * access, hoverinfo="skip", opacity=0.9))
        fig.update_layout(**S.base_layout(height=560, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
                                          scene=S.scene_3d(xaxis=dict(visible=False), yaxis=dict(visible=False),
                                                           zaxis=dict(visible=False),
                                                           aspectmode="cube")))
        cap = (
            f"The real mixed-amphiphile protocell at the operating point ({viable:.0f} viable vesicles). The "
            f"semi-transparent amphiphile membrane encloses a lumen whose colour is the measured <b>retention</b> "
            f"({retention:.2f}) of internal product, while amber arrows (import, scaled by <b>access</b> {access:.2f}) "
            f"show the external gradient still crossing in. Individuality = retention × access = <b>{individ:.2f}</b> — "
            "a boundary that retains WITHOUT isolating. Geometry schematic; retention / access measured."
        )
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return {"html": S.frame(inner, title=(self.config.get("title") or "The protocell in 3-D"),
                                phase="Campaign IV", view="World", tier="mechanistic_prediction",
                                caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=820)}


class ProtocellWindowViz(Visualization):
    """Campaign-IV protocell stability window — the Jordan-2019 broadening and the
    individuality-vs-access tradeoff. Sweeps ``ProtocellAssemblyProcess`` over a
    (pH × ionic strength) grid and reads the individuality-access landscape; shows
    the single-fatty-acid vs mixed-amphiphile viable regions and an animation of the
    window broadening as the co-surfactant fraction rises. Every value a real model
    evaluation (coarse-grained, Jordan-calibrated)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign IV — the protocell window broadens (mixed amphiphiles)"},
        "n_grid": {"_type": "integer", "_default": 40},
        "n_frames": {"_type": "integer", "_default": 16},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import numpy as np

        from ..core import build_core
        from ..membranes.protocell_assembly import ProtocellAssemblyProcess
        core = build_core()
        ng = int(self.config["n_grid"])
        pH = np.linspace(6.0, 11.0, ng)
        ionic = np.linspace(0.0, 0.9, ng)

        def grid(mix):
            p = ProtocellAssemblyProcess(config={"mix_fraction": max(mix, 1e-4)}, core=core)
            Z = np.zeros((ng, ng))
            for i, ii in enumerate(ionic):
                for j, pp in enumerate(pH):
                    r = p.update({"pH": float(pp), "ionic_strength": float(ii), "temperature": 318.15}, 1.0)
                    Z[i, j] = r["individuality_access"]
            return Z

        mixes = list(np.linspace(0.0, 0.5, int(self.config["n_frames"])))
        frames_Z = [(m, grid(m)) for m in mixes]
        single_Z = frames_Z[0][1]
        mixed_Z = grid(0.4)
        return {"html": self._figure(pH.tolist(), ionic.tolist(), single_Z, mixed_Z, frames_Z)}

    def _figure(self, pH, ionic, single_Z, mixed_Z, frames_Z) -> str:
        import numpy as np
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        ink = "#1e293b"
        single_area = float(np.mean(np.asarray(single_Z) > 0.1)) * 100.0
        mixed_area = float(np.mean(np.asarray(mixed_Z) > 0.1)) * 100.0
        cs = "Tealgrn"

        stat = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
            subplot_titles=(f"Single fatty acid — viable {single_area:.0f}% of window",
                            f"Mixed amphiphiles — viable {mixed_area:.0f}% of window"))
        for col, Z in ((1, single_Z), (2, mixed_Z)):
            stat.add_trace(go.Heatmap(z=Z, x=pH, y=ionic, colorscale=cs, zmin=0, zmax=1,
                           colorbar=dict(title="indiv×<br>access", thickness=12, len=0.8) if col == 2 else None,
                           showscale=(col == 2)), row=1, col=col)
            stat.add_trace(go.Scatter(x=[9.0], y=[0.35], mode="markers+text", text=["vent"],
                           textposition="top center", marker=dict(symbol="star", size=12, color="#b91c1c"),
                           showlegend=False, textfont=dict(size=9, color="#b91c1c")), row=1, col=col)
        stat.update_xaxes(title_text="pH", row=1, col=1); stat.update_xaxes(title_text="pH", row=1, col=2)
        stat.update_yaxes(title_text="ionic strength (M)", row=1, col=1)
        stat.update_layout(**S.base_layout(
            height=430, width=900, showlegend=False,
            margin=dict(l=60, r=20, t=56, b=55)))

        # motion: the viable region broadening as the co-surfactant fraction rises.
        frames = [go.Frame(data=[go.Heatmap(z=Z, x=pH, y=ionic, colorscale=cs, zmin=0, zmax=1,
                           colorbar=dict(title="indiv×<br>access", thickness=12, len=0.8))],
                           name="%.2f" % m,
                           layout=go.Layout(annotations=[dict(x=10.2, y=0.82,
                               text="mix %.2f · viable %.0f%%" % (m, float(np.mean(np.asarray(Z) > 0.1)) * 100.0),
                               showarrow=False, font=dict(size=12, color=ink),
                               bgcolor="rgba(255,255,255,0.7)")]))
                  for m, Z in frames_Z]
        anim = go.Figure(data=frames[0].data, frames=frames)
        anim.add_scatter(x=[9.0], y=[0.35], mode="markers+text", text=["vent"], textposition="top center",
                         marker=dict(symbol="star", size=13, color="#b91c1c"), showlegend=False,
                         textfont=dict(size=10, color="#b91c1c"))
        anim.update_xaxes(title_text="pH")
        anim.update_yaxes(title_text="ionic strength (M)")
        anim.update_layout(template="plotly_white", height=440, width=560,
            title=dict(text="the window broadening with co-surfactant", x=0.5, xanchor="center",
                       y=0.99, font=dict(size=13, color=ink)),
            margin=dict(l=60, r=20, t=70, b=55), font=dict(color=ink),
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.1, xanchor="left",
                yanchor="bottom", showactive=False, buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, dict(frame=dict(duration=160, redraw=True), fromcurrent=True)]),
                    dict(label="⏸ Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                ])],
            sliders=[dict(active=0, x=0.08, len=0.88, y=-0.08, currentvalue=dict(visible=False),
                steps=[dict(method="animate", label="",
                            args=[[f.name], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                       for f in frames])])

        cap_text = (
            "<b>Organic boundaries without isolation</b> — the coarse-grained protocell model "
            "(Jordan 2019). Colour is the individuality × access product (retains chemistry AND "
            "stays permeable). A single fatty acid is viable only in a narrow corner; adding a "
            "co-surfactant (mixed amphiphiles) <b>broadens the window</b> to the alkaline, salty "
            "vent point (★) — the boundary enhances persistence without cutting the system off "
            "from the gradient.")
        s_html = stat.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        a_html = anim.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        inner = (f"<div style='display:flex;justify-content:center'>{s_html}</div>"
                 "<div style='display:flex;justify-content:center;margin-top:8px'>" + a_html + "</div>")
        return S.frame(inner, title=(self.config.get("title")
                                     or "The protocell window broadens — mixed amphiphiles"),
                       phase="Campaign IV", view="Mechanism", tier="mechanistic_prediction",
                       caption_text=cap_text, caption_prefix="How to read", tone="neutral", max_width=940)

class BioenergeticInternalizationViz(Visualization):
    """Campaign-V REAL bioenergetic internalization under selection. Runs the
    ``bioenergetic_internalization`` composite step by step, reading the live
    replicator strategy landscape (permeability × pump) and the internalization /
    survival time series as the external gradient declines. Shows the transition
    (internalization rising, gradient falling) + the strategy mass migrating from
    the leaky-external corner to the tight-pump corner, with an animation of the
    migration. Every value a real replicator state (Sojo-2014 fitness)."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign V — selection internalizes the gradient"},
        "n_steps": {"_type": "integer", "_default": 40},
        "catalyst_efficiency": {"_type": "float", "_default": 1.0},
        "max_frames": {"_type": "integer", "_default": 20},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    @staticmethod
    def _find_sel(node):
        if isinstance(node, dict):
            inst = node.get("instance")
            if inst is not None and type(inst).__name__ == "BioenergeticSelectionProcess":
                return inst
            for v in node.values():
                r = BioenergeticInternalizationViz._find_sel(v)
                if r is not None:
                    return r
        return None

    def update(self, state=None):
        from ..core import build_core
        from ..composites.bioenergetic_internalization import bioenergetic_internalization
        from ..bioenergetics.selection import selection_state
        core = build_core()
        doc = bioenergetic_internalization(core, catalyst_efficiency=float(self.config["catalyst_efficiency"]))
        sim = Composite({"state": doc}, core=core)
        sel = self._find_sel(sim.state)
        snaps, rows = [], []
        for _ in range(int(self.config["n_steps"])):
            sim.run(1)
            rows = gather_emitter_results(sim)[("emitter",)]
            snaps.append(selection_state(sel))
        return {"html": self._figure(snaps, rows)}

    def _figure(self, snaps, rows) -> str:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        if not snaps or not rows:
            return "<p>No selection snapshots produced.</p>"
        ink, teal, rust, amber = "#1e293b", "#0d9488", "#b91c1c", "#d97706"

        def col(k):
            return [r.get(k) for r in rows if k in r]
        from ..composites.bioenergetic_internalization import bioenergetic_internalization
        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)],
                                bioenergetic_internalization)
        intern = col("internalization"); surv = col("survivors"); vext = col("electric_potential")
        P = snaps[-1]["P"]; pump = snaps[-1]["pump"]

        stat = make_subplots(rows=1, cols=2, horizontal_spacing=0.13,
            subplot_titles=("The transition as the gradient declines",
                            "Settled strategy landscape (internalized)"))
        stat.add_scatter(x=t, y=intern, mode="lines", line=dict(color=rust, width=2.8),
                         name="internalization", row=1, col=1)
        stat.add_scatter(x=t, y=surv, mode="lines", line=dict(color=teal, width=2.5),
                         name="survivors", row=1, col=1)
        stat.add_scatter(x=t, y=vext, mode="lines", yaxis="y2", line=dict(color=amber, width=2, dash="dot"),
                         name="external gradient (V)", row=1, col=1)
        stat.add_trace(go.Heatmap(z=snaps[-1]["freq"], x=P, y=pump, colorscale="Oranges",
                       colorbar=dict(title="freq", thickness=12, len=0.8)), row=1, col=2)
        stat.update_xaxes(title_text=tlabel, row=1, col=1, showgrid=True, gridcolor="#eef2f7")
        stat.update_yaxes(title_text="fraction", row=1, col=1, showgrid=True, gridcolor="#eef2f7")
        stat.update_xaxes(title_text="membrane permeability P (normalized; P=1 ⇒ 1e-8 m/s)", row=1, col=2)
        stat.update_yaxes(title_text="active-pump rate (normalized)", row=1, col=2)
        stat.update_layout(**S.base_layout(
            height=430, width=940, showlegend=True,
            legend=dict(orientation="h", y=-0.2, x=0.25, font=dict(size=10)),
            yaxis2=dict(overlaying="y", side="right", anchor="x", showgrid=False, title="gradient (V)"),
            margin=dict(l=55, r=55, t=56, b=70)))

        # motion: the strategy mass migrating leaky-external -> tight-pump.
        step = max(1, len(snaps) // int(self.config["max_frames"]))
        keep = list(range(0, len(snaps), step)) + [len(snaps) - 1]
        frames = [go.Frame(data=[go.Heatmap(z=snaps[k]["freq"], x=P, y=pump, colorscale="Oranges",
                           colorbar=dict(title="freq", thickness=12, len=0.8))],
                           name=str(j),
                           layout=go.Layout(annotations=[dict(x=0.5, y=1.05,
                               text="gradient %.3f V · internalization %.2f" % (vext[k], intern[k]),
                               showarrow=False, xref="x domain", yref="y domain",
                               font=dict(size=12, color=ink))]))
                  for j, k in enumerate(keep)]
        anim = go.Figure(data=frames[0].data, frames=frames)
        anim.update_xaxes(title_text="permeability (leaky →)")
        anim.update_yaxes(title_text="active-pump rate (→ internalized)")
        anim.update_layout(template="plotly_white", height=440, width=560, showlegend=False,
            title=dict(text="the population migrating to internal pumping", x=0.5, xanchor="center",
                       y=0.99, font=dict(size=13, color=ink)),
            margin=dict(l=60, r=20, t=70, b=55), font=dict(color=ink),
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.1, xanchor="left",
                yanchor="bottom", showactive=False, buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, dict(frame=dict(duration=150, redraw=True), fromcurrent=True)]),
                    dict(label="⏸ Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                ])],
            sliders=[dict(active=0, x=0.08, len=0.88, y=-0.08, currentvalue=dict(visible=False),
                steps=[dict(method="animate", label="",
                            args=[[f.name], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                       for f in frames])])

        cap_text = (
            "<b>From environmental to internal bioenergetics</b> — a real evolutionary control "
            "loop (replicator dynamics, Sojo-2014 fitness). As the external geochemical gradient "
            "declines (dotted), selection drives the population from the leaky-external corner to "
            "the <b>tight-membrane, active-pump</b> corner — internalizing gradient generation "
            "(red) while persisting (teal). A weak pump cannot make this move and goes extinct.")
        s_html = stat.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        a_html = anim.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        inner = (f"<div style='display:flex;justify-content:center'>{s_html}</div>"
                 "<div style='display:flex;justify-content:center;margin-top:8px'>" + a_html + "</div>")
        return S.frame(inner, title=(self.config.get("title") or "Selection internalizes the gradient"),
                       phase="Campaign V", view="World", tier="conceptual_demonstration",
                       caption_text=cap_text, caption_prefix="How to read", tone="neutral", max_width=960)

class HeredityErrorThresholdViz(Visualization):
    """Campaign-VI REAL quasispecies heredity — the Eigen error threshold and the
    head-to-head module ranking. Sweeps ``HeredityReplicatorProcess`` over a
    (per-site fidelity × polymer length) grid for the information-retention
    landscape (the error threshold), marks the heredity modules on it, and animates
    the retention trajectories of the modules diverging over time (RNA-like retains;
    the sub-threshold module collapses). Every value a real libRoadRunner solve."""

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign VI — heredity above the error threshold"},
        "n_fid": {"_type": "integer", "_default": 22},
        "n_len": {"_type": "integer", "_default": 22},
        "n_steps": {"_type": "integer", "_default": 50},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        import numpy as np

        from ..core import build_core
        from ..heredity.replicator import HeredityReplicatorProcess
        core = build_core()
        fids = np.linspace(0.86, 0.999, int(self.config["n_fid"]))
        lens = np.linspace(5, 40, int(self.config["n_len"])).astype(int)

        def retention(fid, L):
            p = HeredityReplicatorProcess(config={"per_site_fidelity": float(fid),
                                                  "polymer_length": int(L)}, core=core)
            r = None
            for _ in range(30):
                r = p.update({"temperature": 353.15}, 1.0)
            return r["information_retention"]

        land = np.array([[retention(f, L) for f in fids] for L in lens])

        # module trajectories over time
        from ..composites.heredity_module_comparison import heredity_module_comparison, _MODULES
        from process_bigraph import Composite, gather_emitter_results
        mods = {}
        for m in ("rna-like", "peptide", "low-fidelity", "non-heritable"):
            sim = Composite({"state": heredity_module_comparison(core=core, module=m)}, core=core)
            traj = []
            for _ in range(int(self.config["n_steps"])):
                sim.run(1)
                traj.append(gather_emitter_results(sim)[("emitter",)][-1])
            mods[m] = traj
        module_pts = {m: (_MODULES[m]["per_site_fidelity"], _MODULES[m]["polymer_length"]) for m in mods}
        return {"html": self._figure(fids.tolist(), lens.tolist(), land, mods, module_pts)}

    def _figure(self, fids, lens, land, mods, module_pts) -> str:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        ink = "#1e293b"
        COL = {"rna-like": "#0d9488", "peptide": "#d97706",
               "low-fidelity": "#b91c1c", "non-heritable": "#64748b"}

        stat = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
            subplot_titles=("Eigen error threshold (retention landscape)",
                            "Module head-to-head: lineage fitness"))
        stat.add_trace(go.Heatmap(z=land, x=fids, y=lens, colorscale="Tealgrn", zmin=0, zmax=1,
                       colorbar=dict(title="retention", thickness=12, len=0.8)), row=1, col=1)
        # rna-like and non-heritable sit at the SAME grid point (fidelity 0.99, len 30)
        # near the right edge; offset their labels to opposite corners on the left so
        # they neither overprint each other nor run off the panel edge.
        TPOS = {"rna-like": "top left", "non-heritable": "bottom left",
                "peptide": "top center", "low-fidelity": "top center"}
        for m, (f, L) in module_pts.items():
            stat.add_trace(go.Scatter(x=[f], y=[L], mode="markers+text", text=[m],
                           textposition=TPOS.get(m, "top center"),
                           marker=dict(size=11, color=COL[m], symbol="star",
                           line=dict(color="#fff", width=1)), showlegend=False,
                           textfont=dict(size=9, color=COL[m])), row=1, col=1)
        names = ["rna-like", "peptide", "low-fidelity", "non-heritable"]
        fit = [mods[m][-1]["lineage_fitness"] for m in names]
        stat.add_trace(go.Bar(x=names, y=fit, marker_color=[COL[m] for m in names], showlegend=False),
                       row=1, col=2)
        stat.add_hline(y=0.0, line=dict(color="#94a3b8", width=1), row=1, col=2)
        stat.update_xaxes(title_text="per-site fidelity", row=1, col=1)
        stat.update_yaxes(title_text="polymer length", row=1, col=1)
        stat.update_yaxes(title_text="lineage fitness", row=1, col=2, showgrid=True, gridcolor="#eef2f7")
        stat.update_layout(**S.base_layout(
            height=430, width=940, showlegend=False,
            margin=dict(l=55, r=20, t=56, b=55)))

        # motion: retention trajectories diverging over time.
        from ..composites.heredity_module_comparison import heredity_module_comparison
        n = max(len(v) for v in mods.values())
        t, tlabel = S.real_time(list(range(n)), heredity_module_comparison)
        def _series(m, k):
            return [r.get("information_retention") for r in mods[m]]
        anim = go.Figure(
            data=[go.Scatter(x=[0], y=[_series(m, 0)[0]], mode="lines", name=m,
                             line=dict(color=COL[m], width=2.6)) for m in names],
            frames=[go.Frame(data=[go.Scatter(x=t[:j + 1], y=_series(m, j)[:j + 1], mode="lines",
                             line=dict(color=COL[m], width=2.6), name=m) for m in names], name=str(j))
                    for j in range(1, n)])
        anim.update_xaxes(title_text=tlabel, range=[0, t[-1] if t else 1], showgrid=True, gridcolor="#eef2f7")
        anim.update_yaxes(title_text="information retention C/(C+E)", range=[-0.03, 1.03],
                          showgrid=True, gridcolor="#eef2f7")
        anim.update_layout(template="plotly_white", height=430, width=580, showlegend=True,
            legend=dict(orientation="h", y=1.14, x=0.5, xanchor="center", font=dict(size=10)),
            title=dict(text="information retained over time (modules diverging)", x=0.5, xanchor="center",
                       y=0.99, font=dict(size=13, color=ink)),
            margin=dict(l=60, r=20, t=90, b=55), font=dict(color=ink),
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.14, xanchor="left",
                yanchor="bottom", showactive=False, buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, dict(frame=dict(duration=90, redraw=True), fromcurrent=True)]),
                    dict(label="⏸ Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                ])],
            sliders=[dict(active=0, x=0.08, len=0.88, y=-0.12, currentvalue=dict(visible=False),
                steps=[dict(method="animate", label="",
                            args=[[str(j)], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                       for j in range(1, n)])])

        cap_text = (
            "<b>Heredity above the error threshold</b> — the real libRoadRunner quasispecies "
            "replicator (Eigen). Longer, higher-fidelity polymers retain functional information "
            "(teal) up to the error threshold; beyond it, errors win and information is lost. "
            "RNA-like clears the threshold and wins the head-to-head over the cheaper peptide "
            "module; both beat non-inheritance, while a sub-threshold module suffers the "
            "error catastrophe.")
        s_html = stat.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        a_html = anim.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        inner = (f"<div style='display:flex;justify-content:center'>{s_html}</div>"
                 "<div style='display:flex;justify-content:center;margin-top:8px'>" + a_html + "</div>")
        return S.frame(inner, title=(self.config.get("title") or "Heredity above the error threshold"),
                       phase="Campaign VI", view="Decision", tier="conceptual_demonstration",
                       caption_text=cap_text, caption_prefix="How to read", tone="neutral", max_width=960)


class NitrogenAssimilationViz(Visualization):
    """Campaign-I (Module I) WORLD view — reduced-nitrogen assimilation at the vent.
    Runs the real ``reduced_nitrogen_reactor`` composite and shows the nitrogen pools
    moving down the reduction chain (NO3- -> NO2- -> NH4+ -> amino-acid precursor) over
    time, the standing reduced-N pool, and the ammonium-production rate — the first
    fixed nitrogen appearing on the FeS catalyst. Drives the genuine
    ``ReducedNitrogenProductionProcess``.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign I — reduced-nitrogen assimilation (FeS)"},
        "n_steps": {"_type": "integer", "_default": 120},
        "no3_supply": {"_type": "float", "_default": 2.0e-5},
        "fes_activity": {"_type": "float", "_default": 1.0},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.nitrogen_assimilation import reduced_nitrogen_reactor
        core = build_core()
        doc = reduced_nitrogen_reactor(core, no3_supply=float(self.config["no3_supply"]),
                                       fes_activity=float(self.config["fes_activity"]))
        sim = Composite({"state": doc}, core=core)
        sim.run(float(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        from plotly.subplots import make_subplots
        from ..composites.nitrogen_assimilation import reduced_nitrogen_reactor

        def col(k):
            return [r[k] for r in rows if k in r]

        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)],
                                reduced_nitrogen_reactor)
        no3 = [v * 1e6 for v in col("NO3")]
        no2 = [v * 1e6 for v in col("NO2")]
        nh4 = [v * 1e6 for v in col("NH4")]
        amino = [v * 1e6 for v in col("amino_precursor")]
        reduced = [v * 1e6 for v in col("reduced_n")]
        prod = col("nh4_production_rate")

        ink, teal, amber, slate, rust, violet = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c", "#7c3aed"
        fig = make_subplots(
            rows=1, cols=3, horizontal_spacing=0.08,
            subplot_titles=("Nitrogen pools down the reduction chain (µM)",
                            "Standing reduced nitrogen (µM)",
                            "Ammonium production rate (mol/s)"))
        fig.add_scatter(x=t, y=no3, mode="lines", line=dict(color=slate, width=2), name="NO₃⁻", row=1, col=1)
        fig.add_scatter(x=t, y=no2, mode="lines", line=dict(color=amber, width=2), name="NO₂⁻", row=1, col=1)
        fig.add_scatter(x=t, y=nh4, mode="lines", line=dict(color=teal, width=2.5), name="NH₄⁺", row=1, col=1)
        fig.add_scatter(x=t, y=amino, mode="lines", line=dict(color=violet, width=2, dash="dot"), name="amino precursor", row=1, col=1)
        fig.add_scatter(x=t, y=reduced, mode="lines", line=dict(color=teal, width=2.5),
                        fill="tozeroy", fillcolor="rgba(13,148,136,0.12)", name="reduced N (NH₄⁺+precursor)", row=1, col=2)
        fig.add_scatter(x=t, y=prod, mode="lines", line=dict(color=ink, width=2.5), row=1, col=3)

        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(**S.base_layout(
            height=400, showlegend=True,
            legend=dict(orientation="h", y=-0.2, x=0.0, font=dict(size=10)),
            margin=dict(l=60, r=30, t=46, b=70)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Reduced-nitrogen assimilation (FeS)"),
            phase="Nitrogen", view="World", tier="mechanistic_prediction", caption_prefix="How to read",
            caption_text=(
                "Modeled. The reduced-nitrogen reactor — nitrogen moving down the reduction chain "
                "(NO₃⁻ → NO₂⁻ → NH₄⁺ → amino-acid precursor) on the FeS catalyst as source→product "
                "conversion, the standing reduced-N pool, and the ammonium-production rate. Standing pools "
                "alone do not establish a sufficient nitrogen FLUX (the keeps-pace test is the phase map), "
                "and the nitrate feed is a supplied parameter, not an early-Earth abundance claim."))


class NitrogenCarbonBalanceViz(Visualization):
    """Campaign-I (Module I) MECHANISM view — the C:N supply-ratio panel. Runs the real
    ``reduced_nitrogen_reactor`` composite in both the favourable and a nitrogen-limited
    arm and shows (left) the reduced-N production rate against the carbon-fixation demand
    over time — where N production keeps pace vs falls behind — and (right) the C:N supply
    ratio trajectory with the keeps-pace threshold, so the limiting regime is explicit.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign I — does reduced N keep pace with carbon?"},
        "n_steps": {"_type": "integer", "_default": 120},
        "c_demand": {"_type": "float", "_default": 1.0e-4},
        "limited_no3_supply": {"_type": "float", "_default": 3.0e-6},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.nitrogen_assimilation import reduced_nitrogen_reactor
        core = build_core()
        n = int(self.config["n_steps"])
        cd = float(self.config["c_demand"])

        def run(**kw):
            sim = Composite({"state": reduced_nitrogen_reactor(core, c_demand=cd, **kw)}, core=core)
            sim.run(n)
            return gather_emitter_results(sim)[("emitter",)]

        fav = run(no3_supply=2.0e-5, fes_activity=1.0)
        lim = run(no3_supply=float(self.config["limited_no3_supply"]), fes_activity=1.0)
        return {"html": self._figure(fav, lim, cd)}

    def _figure(self, fav, lim, c_demand) -> str:
        from plotly.subplots import make_subplots
        from ..composites.nitrogen_assimilation import reduced_nitrogen_reactor

        def col(rows, k):
            return [r.get(k) for r in rows if k in r]

        tf, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(fav)],
                                 reduced_nitrogen_reactor)
        tl, _ = S.real_time([r.get("global_time", i) for i, r in enumerate(lim)],
                            reduced_nitrogen_reactor)
        prod_f = col(fav, "nh4_production_rate")
        prod_l = col(lim, "nh4_production_rate")
        cn_f = [min(v, 1e3) for v in col(fav, "cn_supply_ratio")]
        cn_l = [min(v, 1e3) for v in col(lim, "cn_supply_ratio")]
        # N production rate matched to carbon demand at the keeps-pace threshold (mol/s).
        thr = 8.0
        demand_match = c_demand / thr

        ink, teal, amber, slate, rust = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c"
        fig = make_subplots(
            rows=1, cols=2, horizontal_spacing=0.12,
            subplot_titles=("Reduced-N production vs carbon demand (mol/s)",
                            "C:N supply ratio — keeps pace vs limiting"))
        # --- left: production rates vs the carbon-demand-matched line ---
        fig.add_hline(y=demand_match, line=dict(color=slate, width=1.5, dash="dot"), row=1, col=1)
        fig.add_annotation(x=tf[-1], y=demand_match, text="N needed to keep pace", showarrow=False,
                           yshift=10, xanchor="right", font=dict(size=9, color=slate), row=1, col=1)
        fig.add_scatter(x=tf, y=prod_f, mode="lines", line=dict(color=teal, width=3),
                        name="favourable (keeps pace)", row=1, col=1)
        fig.add_scatter(x=tl, y=prod_l, mode="lines", line=dict(color=rust, width=2.5, dash="dash"),
                        name="N-limited feed", row=1, col=1)
        # --- right: C:N ratio with the keeps-pace band shaded ---
        fig.add_hrect(y0=0, y1=thr, line_width=0, fillcolor=teal, opacity=0.08, row=1, col=2)
        fig.add_hline(y=thr, line=dict(color=slate, width=1.5, dash="dot"), row=1, col=2)
        fig.add_scatter(x=tf, y=cn_f, mode="lines", line=dict(color=teal, width=3),
                        name="favourable", row=1, col=2)
        fig.add_scatter(x=tl, y=cn_l, mode="lines", line=dict(color=rust, width=2.5, dash="dash"),
                        name="N-limited", row=1, col=2)
        fig.add_annotation(x=tf[-1], y=thr, text="keeps-pace band", showarrow=False, yshift=-10,
                           xanchor="right", font=dict(size=9, color=teal), row=1, col=2)

        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(title_text="production (mol/s)", row=1, col=1, showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(title_text="C:N supply ratio (log)", type="log", row=1, col=2,
                         showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(**S.base_layout(
            height=420, showlegend=True,
            legend=dict(orientation="h", y=-0.2, x=0.0, font=dict(size=10)),
            margin=dict(l=65, r=30, t=46, b=70)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Does reduced N keep pace with carbon?"),
            phase="Nitrogen", view="Mechanism", tier="mechanistic_prediction", caption_prefix="How to read",
            caption_text=(
                "Does reduced-nitrogen supply keep pace with carbon fixation? Left: the reduced-N "
                "production rate against the carbon-fixation demand (dotted); right: the C:N supply "
                "ratio with the keeps-pace band shaded — the favourable feed keeps pace, the "
                "N-limited feed falls behind."))


class PhosphorusSpeciationViz(Visualization):
    """og-res-phosphorus World view: the P-species trajectories of the real
    libRoadRunner phosphorus-speciation network — dissolved phosphate, condensed
    polyphosphate, reactive (activated) P, and the mineral-bound (precipitated/
    adsorbed) sink — in the favorable thermal-gradient pore. Shows reactive P
    accumulating while only a small fraction precipitates.

    Drives the genuine libRoadRunner/Tellurium composite
    (``viva_genesis.composites.phosphorus_availability``).
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Phosphorus bottleneck — P-species trajectories"},
        "n_steps": {"_type": "integer", "_default": 120},
        "pore_enrichment": {"_type": "float", "_default": 30.0},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.phosphorus_availability import phosphorus_availability
        core = build_core()
        doc = phosphorus_availability(core, pore_enrichment=float(self.config["pore_enrichment"]))
        sim = Composite({"state": doc}, core=core)
        sim.run(float(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        from plotly.subplots import make_subplots
        from ..composites.phosphorus_availability import phosphorus_availability

        def col(k):
            return [r[k] for r in rows if k in r]

        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)],
                                phosphorus_availability)
        phosphate = [v * 1e6 for v in col("phosphate")]        # µM
        polyp = [v * 1e6 for v in col("polyphosphate")]
        reactivep = [v * 1e6 for v in col("reactive_P")]
        mineralp = [v * 1e6 for v in col("mineral_P")]
        precipf = col("precipitated_fraction")

        ink, teal, amber, slate, rust = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c"
        fig = make_subplots(
            rows=1, cols=2, horizontal_spacing=0.1,
            subplot_titles=("P-species pools (µM)", "Precipitated (mineral-bound) fraction"),
        )
        fig.add_scatter(x=t, y=reactivep, mode="lines", line=dict(color=teal, width=3), name="reactive P", row=1, col=1)
        fig.add_scatter(x=t, y=phosphate, mode="lines", line=dict(color=slate, width=2), name="phosphate", row=1, col=1)
        fig.add_scatter(x=t, y=polyp, mode="lines", line=dict(color=amber, width=2, dash="dash"), name="polyphosphate", row=1, col=1)
        fig.add_scatter(x=t, y=mineralp, mode="lines", line=dict(color=rust, width=2, dash="dot"), name="mineral-bound P", row=1, col=1)
        fig.add_scatter(x=t, y=precipf, mode="lines", line=dict(color=rust, width=2.5), showlegend=False, row=1, col=2)

        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(range=[0, 1], row=1, col=2)
        fig.update_layout(**S.base_layout(
            height=400, showlegend=True,
            legend=dict(orientation="h", y=-0.2, x=0.0, font=dict(size=10)),
            margin=dict(l=60, r=30, t=46, b=70)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Phosphorus bottleneck — P-species trajectories"),
            phase="Phosphorus", view="World", tier="mechanistic_prediction", caption_prefix="How to read",
            caption_text=(
                "Modeled. The libRoadRunner phosphorus-speciation network in the favourable thermal-gradient "
                "pore — dissolved phosphate, condensed polyphosphate, reactive (activated) P, and the "
                "mineral-bound sink partition a conserved total-P pool (mass-conserving). Reactive P "
                "accumulates while only a small fraction precipitates. The condensed-polyphosphate pool is a "
                "modeled kinetic partition, not demonstrated prebiotic polyphosphate chemistry."))


class PhosphorusMechanismViz(Visualization):
    """og-res-phosphorus Mechanism view: the reactive-P production flux vs the
    precipitation / adsorption loss flux, and their difference (net availability),
    for the favorable pore vs an open-pore / no-gradient control. The mechanism of
    the phosphorus bottleneck: without the thermal-gradient enrichment, precipitation
    outpaces reactive-P formation and net availability is negative.

    Drives the genuine libRoadRunner/Tellurium composite
    (``viva_genesis.composites.phosphorus_availability``).
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Phosphorus bottleneck — reactive-P production vs loss"},
        "n_steps": {"_type": "integer", "_default": 120},
        "pore_enrichment": {"_type": "float", "_default": 30.0},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def _run(self, enr):
        from ..core import build_core
        from ..composites.phosphorus_availability import phosphorus_availability
        core = build_core()
        sim = Composite({"state": phosphorus_availability(core, pore_enrichment=float(enr))}, core=core)
        sim.run(float(self.config["n_steps"]))
        return gather_emitter_results(sim)[("emitter",)]

    def update(self, state=None):
        fav = self._run(float(self.config["pore_enrichment"]))
        ctl = self._run(1.0)
        return {"html": self._figure(fav, ctl)}

    def _figure(self, fav, ctl) -> str:
        from plotly.subplots import make_subplots
        from ..composites.phosphorus_availability import phosphorus_availability

        def series(rows, k):
            return [r.get(k, 0.0) * 1e6 for r in rows]   # µmol/s

        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(fav)],
                                phosphorus_availability)
        ink, teal, amber, slate, rust = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c"
        fig = make_subplots(
            rows=1, cols=2, horizontal_spacing=0.1, shared_yaxes=False,
            subplot_titles=("Favorable pore (enriched)", "Open pore / no gradient (control)"),
        )
        for col_i, rows in ((1, fav), (2, ctl)):
            prod = series(rows, "reactive_P_production")
            loss = series(rows, "phosphate_loss")
            net = series(rows, "net_reactive_P")
            fig.add_scatter(x=t, y=prod, mode="lines", line=dict(color=teal, width=2.5),
                            name="reactive-P production", showlegend=(col_i == 1), row=1, col=col_i)
            fig.add_scatter(x=t, y=loss, mode="lines", line=dict(color=rust, width=2.5, dash="dash"),
                            name="precipitation loss", showlegend=(col_i == 1), row=1, col=col_i)
            fig.add_scatter(x=t, y=net, mode="lines", line=dict(color=ink, width=2),
                            name="net availability", showlegend=(col_i == 1), row=1, col=col_i)
            fig.add_hline(y=0.0, line=dict(color=slate, width=1, dash="dot"), row=1, col=col_i)

        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(title_text="flux (µmol/s)", showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(**S.base_layout(
            height=400, showlegend=True,
            legend=dict(orientation="h", y=-0.2, x=0.0, font=dict(size=10)),
            margin=dict(l=60, r=30, t=46, b=70)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Phosphorus bottleneck — reactive-P production vs loss"),
            phase="Phosphorus", view="Mechanism", tier="mechanistic_prediction", caption_prefix="How to read",
            caption_text=(
                "The mechanism of the phosphorus bottleneck — reactive-P production flux vs the "
                "precipitation / adsorption loss flux and their net, for the enriched favourable pore vs "
                "an open-pore / no-gradient control. Without the thermal-gradient enrichment, "
                "precipitation outpaces reactive-P formation and net availability goes negative."))


class ProtoEnergeticsWorldViz(Visualization):
    """Proto-energetics World view — charging and spending a pre-ATP energy currency.
    Runs the ``proto_energetics`` composite step by step and shows the carrier pool
    being CHARGED by the geochemical drive, DISCHARGED to do endergonic work under
    load, and bled by hydrolysis — the charge/discharge/loss flux trajectories and
    the carrier-charge time course, against the no-coupling and no-drive ablations
    that never build a store. Every value a real free-energy-ledger state."""

    config_schema = {
        "title": {"_type": "string", "_default": "Proto-energetics — charging and spending the currency"},
        "n_steps": {"_type": "integer", "_default": 60},
        "drive_free_energy": {"_type": "float", "_default": 50.0},
        "coupling_efficiency": {"_type": "float", "_default": 0.6},
        "max_frames": {"_type": "integer", "_default": 24},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.proto_energetics import proto_energetics
        core = build_core()
        n = int(self.config["n_steps"])

        def run(**kw):
            sim = Composite({"state": proto_energetics(core=core, **kw)}, core=core)
            sim.run(n)
            return gather_emitter_results(sim)[("emitter",)]

        fav = run(drive_free_energy=float(self.config["drive_free_energy"]),
                  coupling_efficiency=float(self.config["coupling_efficiency"]))
        no_coupling = run(coupling_efficiency=0.0)
        no_drive = run(drive_free_energy=10.0)
        return {"html": self._figure(fav, no_coupling, no_drive)}

    def _figure(self, fav, no_coupling, no_drive) -> str:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        if not fav:
            return "<p>No proto-energetics run produced.</p>"
        ink, teal, amber, slate, rust = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c"

        def col(rows, k):
            return [float(r.get(k, 0.0)) for r in rows]
        from ..composites.proto_energetics import proto_energetics
        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(fav)],
                                proto_energetics)
        # molar -> mM, per-tick fluxes -> µM/tick for readability
        charge_mM = [v * 1e3 for v in col(fav, "energy_charge")]
        chg_flux = [v * 1e6 for v in col(fav, "energy_charge_flux")]
        dis_flux = [v * 1e6 for v in col(fav, "energy_discharge_flux")]
        loss_flux = [v * 1e6 for v in col(fav, "energy_loss_flux")]

        stat = make_subplots(rows=1, cols=2, horizontal_spacing=0.13,
            subplot_titles=("Carrier charge vs the ablations",
                            "Charge / discharge / loss fluxes (favourable)"))
        stat.add_scatter(x=t, y=charge_mM, mode="lines", line=dict(color=teal, width=3),
                         name="favourable", row=1, col=1)
        stat.add_scatter(x=t, y=[v * 1e3 for v in col(no_coupling, "energy_charge")], mode="lines",
                         line=dict(color=slate, width=2, dash="dash"), name="no coupling", row=1, col=1)
        stat.add_scatter(x=t, y=[v * 1e3 for v in col(no_drive, "energy_charge")], mode="lines",
                         line=dict(color=rust, width=2, dash="dot"), name="no drive (ΔG < bond)", row=1, col=1)
        stat.add_scatter(x=t, y=chg_flux, mode="lines", line=dict(color=teal, width=2.4),
                         name="charging", row=1, col=2)
        stat.add_scatter(x=t, y=dis_flux, mode="lines", line=dict(color=amber, width=2.4),
                         name="discharge→work", row=1, col=2)
        stat.add_scatter(x=t, y=loss_flux, mode="lines", line=dict(color=rust, width=1.8, dash="dot"),
                         name="hydrolysis", row=1, col=2)
        stat.update_xaxes(title_text=tlabel, row=1, col=1, showgrid=True, gridcolor="#eef2f7")
        stat.update_yaxes(title_text="charged carrier (mM)", row=1, col=1, showgrid=True, gridcolor="#eef2f7")
        stat.update_xaxes(title_text=tlabel, row=1, col=2, showgrid=True, gridcolor="#eef2f7")
        stat.update_yaxes(title_text="flux (µM / tick)", row=1, col=2, showgrid=True, gridcolor="#eef2f7")
        stat.update_layout(**S.base_layout(
            height=430, width=960, showlegend=True,
            legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", font=dict(size=9)),
            margin=dict(l=60, r=20, t=56, b=70)))

        # motion: the charged fraction of the pool filling then holding under load.
        frac = col(fav, "energy_charge_fraction")
        capt = col(fav, "energy_stored_work_fraction")
        nf = max(2, int(self.config["max_frames"]))
        step = max(1, len(fav) // nf)
        keep = list(range(0, len(fav), step)) + [len(fav) - 1]
        frames = [go.Frame(data=[go.Bar(x=["charged", "free"],
                        y=[100 * frac[k], 100 * (1.0 - frac[k])],
                        marker_color=[teal, "#e2e8f0"])],
                  name=str(j),
                  layout=go.Layout(annotations=[dict(x=0.5, y=1.06,
                      text="t=%.0f · charged %.0f%% of pool · capture %.0f%%" % (
                          t[k], 100 * frac[k], 100 * capt[k]),
                      showarrow=False, xref="paper", yref="paper",
                      font=dict(size=12, color=ink))]))
                  for j, k in enumerate(keep)]
        anim = go.Figure(data=frames[0].data, frames=frames)
        anim.update_yaxes(title_text="% of carrier pool", range=[0, 105])
        anim.update_layout(template="plotly_white", height=430, width=520, showlegend=False,
            title=dict(text="the currency pool charging + holding under load", x=0.5, xanchor="center",
                       y=0.99, font=dict(size=13, color=ink)),
            margin=dict(l=60, r=20, t=70, b=55), font=dict(color=ink),
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.12, xanchor="left",
                yanchor="bottom", showactive=False, buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, dict(frame=dict(duration=130, redraw=True), fromcurrent=True)]),
                    dict(label="⏸ Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                ])],
            sliders=[dict(active=0, x=0.08, len=0.88, y=-0.06, currentvalue=dict(visible=False),
                steps=[dict(method="animate", label="",
                            args=[[f.name], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                       for f in frames])])

        cap_text = (
            "<b>An energy currency before modern pumping (modeled)</b> — a closed free-energy-ledger "
            "composite (input = useful work + stored + dissipated; ledger residual ~1e-16 kJ/L, so mass "
            "and energy are conserved). An exergonic geochemical drive charges a transferable carrier (teal), "
            "discharged to do endergonic work under load (amber) and bled by hydrolysis (red). At the "
            "canonical operating point the pool settles at a final charged fraction ~0.39 and ~47% of the "
            "tapped free energy is captured as transferable work — these are that single operating point, "
            "not universal (the phase map shows how both fall off across drive × coupling). With no coupling, "
            "or a drive too weak to clear the carrier bond, the pool never charges (the no-coupling and "
            "no-drive ablations). This is modeled energy-currency bookkeeping — a carrier charged and spent — "
            "NOT a demonstration of biochemical energy autonomy.")
        s_html = stat.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        a_html = anim.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        inner = (f"<div style='display:flex;justify-content:center'>{s_html}</div>"
                 "<div style='display:flex;justify-content:center;margin-top:8px'>" + a_html + "</div>")
        return S.frame(inner, title=(self.config.get("title")
                                     or "Proto-energetics — charging and spending the currency"),
                       phase="Energy", view="World", tier="mechanistic_prediction",
                       caption_text=cap_text, caption_prefix="How to read", tone="neutral", max_width=960)


# ----------------------------------------------------------------------------
# og-growth-division — metabolism → osmotic growth & division
# ----------------------------------------------------------------------------
class OsmoticGrowthWorld(Visualization):
    """og-growth-division World view — the favorable (matched) compartment's physical
    trajectory: the volume growing under the osmotic load its metabolism generates, the
    internal osmolyte concentration being drawn down by each division (the sawtooth),
    and the division events as the compartment doubles. Drives the real
    ``viva_genesis.composites.osmotic_growth_division`` composite."""

    config_schema = {
        "title": {"_type": "string", "_default": "Growth & division — volume, concentration, division events"},
        "n_steps": {"_type": "integer", "_default": 100},
        "network_throughput": {"_type": "float", "_default": 1.0e-19},
        "membrane_permeability": {"_type": "float", "_default": 1.0e-9},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from ..core import build_core
        from ..composites.osmotic_growth_division import osmotic_growth_division
        core = build_core()
        doc = osmotic_growth_division(
            core, network_throughput=float(self.config["network_throughput"]),
            membrane_permeability=float(self.config["membrane_permeability"]))
        sim = Composite({"state": doc}, core=core)
        sim.run(float(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        from plotly.subplots import make_subplots
        from ..composites.osmotic_growth_division import osmotic_growth_division

        def col(k):
            return [r.get(k) for r in rows]

        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(rows)],
                                osmotic_growth_division)
        vol = [v * 1e18 for v in col("volume")]               # aL (1e-18 L)
        conc = [v * 1e3 for v in col("internal_concentration")]  # mM
        div_count = col("division_count")
        events = [t[i] for i, e in enumerate(col("division_event")) if e]

        ink, teal, amber, slate = "#1e293b", "#0d9488", "#d97706", "#64748b"
        fig = make_subplots(
            rows=1, cols=3, horizontal_spacing=0.08,
            subplot_titles=("Compartment volume (aL)", "Internal osmolyte (mM)",
                            "Cumulative divisions"))
        fig.add_scatter(x=t, y=vol, mode="lines", line=dict(color=teal, width=2.5), name="volume", row=1, col=1)
        for e in events:
            fig.add_vline(x=e, line=dict(color=amber, width=1, dash="dot"), row=1, col=1)
        fig.add_scatter(x=t, y=conc, mode="lines", line=dict(color=ink, width=2.5), name="c_in", row=1, col=2)
        fig.add_scatter(x=t, y=div_count, mode="lines", line=dict(color=amber, width=2.5, shape="hv"),
                        name="divisions", row=1, col=3)
        fig.update_xaxes(title_text=tlabel, showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(**S.base_layout(
            height=380, showlegend=False, margin=dict(l=60, r=30, t=46, b=60)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title") or "Growth & division — volume, concentration, division events"),
            phase="Growth & division", view="World", tier="mechanistic_prediction", caption_prefix="How to read",
            caption_text=(
                "Modeled. The favourable (matched) compartment's physical trajectory — the volume growing "
                "under the osmotic load its metabolism generates, the internal osmolyte concentration (the "
                "osmotic drive) drawn down at every division (dotted lines) as volume and contents halve, "
                "and the cumulative divisions. A division here is a MODEL-IMPOSED fission rule fired when "
                "the compartment crosses an osmotic/size threshold — NOT emergent mechanical scission, and "
                "not evidence of physical reproduction, heredity or autonomy. Metabolism changes the "
                "compartment's modeled physical fate."))


class OsmoticCouplingMechanism(Visualization):
    """og-growth-division Mechanism view — the osmotic coupling panel. **Left:** for the
    favorable (matched) compartment, the coupling chain product accumulation → osmotic
    pressure → volume on shared time, so the causal order is visible. **Right:** the
    three permeability regimes on the (osmotic pressure vs volume) plane — WHY too
    permeable STARVES (the product leaks, the pressure never builds, the compartment
    never grows) and too impermeable LYSES (the pressure spikes past the burst tension,
    dashed line). Drives the real ``osmotic_growth_division`` composite in three arms."""

    config_schema = {
        "title": {"_type": "string", "_default": "The osmotic coupling — why too permeable starves, too impermeable lyses"},
        "n_steps": {"_type": "integer", "_default": 100},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def _run(self, **params):
        from ..core import build_core
        from ..composites.osmotic_growth_division import osmotic_growth_division
        core = build_core()
        doc = osmotic_growth_division(core, **params)
        sim = Composite({"state": doc}, core=core)
        sim.run(float(self.config["n_steps"]))
        return gather_emitter_results(sim)[("emitter",)]

    def update(self, state=None):
        fav = self._run(network_throughput=1.0e-19, membrane_permeability=1.0e-9)
        starve = self._run(network_throughput=1.0e-19, membrane_permeability=1.0e-5)
        lyse = self._run(network_throughput=1.0e-18, membrane_permeability=1.0e-10)
        return {"html": self._figure(fav, starve, lyse)}

    def _figure(self, fav, starve, lyse) -> str:
        from plotly.subplots import make_subplots
        from ..composites.osmotic_growth_division import osmotic_growth_division

        def series(rows, k, scale=1.0):
            return [r.get(k, 0.0) * scale for r in rows]

        ink, teal, amber, rust, slate = "#1e293b", "#0d9488", "#d97706", "#b91c1c", "#64748b"
        pi_lyse_bar = 1.5e5 / 1e3   # kPa

        fig = make_subplots(
            rows=1, cols=2, horizontal_spacing=0.17, column_widths=[0.52, 0.48],
            specs=[[{"secondary_y": True}, {}]],
            subplot_titles=("The coupling chain (matched regime)",
                            "The three fates on the pressure–volume plane"))
        t, tlabel = S.real_time([r.get("global_time", i) for i, r in enumerate(fav)],
                                osmotic_growth_division)
        fig.add_scatter(x=t, y=series(fav, "product_amount", 1e18), mode="lines",
                        line=dict(color=teal, width=2.5), name="product (amol)",
                        row=1, col=1, secondary_y=False)
        fig.add_scatter(x=t, y=series(fav, "osmotic_pressure", 1e-3), mode="lines",
                        line=dict(color=amber, width=2.5), name="osmotic pressure (kPa)",
                        row=1, col=1, secondary_y=True)
        fig.add_scatter(x=t, y=series(fav, "volume", 1e18), mode="lines",
                        line=dict(color=ink, width=2.5, dash="dot"), name="volume (aL)",
                        row=1, col=1, secondary_y=False)

        for rows, lab, color in ((starve, "too permeable → starve", slate),
                                 (fav, "matched → divide", teal),
                                 (lyse, "too impermeable → lyse", rust)):
            fig.add_scatter(x=series(rows, "volume", 1e18), y=series(rows, "osmotic_pressure", 1e-3),
                            mode="lines", line=dict(color=color, width=2.5), name=lab, row=1, col=2)
        fig.add_hline(y=pi_lyse_bar, line=dict(color=rust, width=1.2, dash="dash"), row=1, col=2)
        fig.add_annotation(x=0.98, y=pi_lyse_bar, xref="x2 domain", yref="y2",
                           text="burst tension", showarrow=False, xanchor="right",
                           font=dict(size=9, color=rust))

        fig.update_xaxes(title_text=tlabel, row=1, col=1)
        fig.update_xaxes(title_text="volume (aL)", row=1, col=2)
        fig.update_yaxes(title_text="product (amol) · volume (aL)", row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="osmotic pressure (kPa)", row=1, col=1, secondary_y=True)
        fig.update_yaxes(title_text="osmotic pressure (kPa)", row=1, col=2)
        fig.update_layout(**S.base_layout(
            height=430,
            legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=9)),
            margin=dict(l=65, r=65, t=54, b=70)))
        inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        return S.frame(
            inner, title=(self.config.get("title")
                          or "The osmotic coupling — why too permeable starves, too impermeable lyses"),
            phase="Growth & division", view="Mechanism", tier="mechanistic_prediction",
            caption_prefix="How to read",
            caption_text=(
                "Modeled. Left: in the matched regime the product accumulates, that raises the osmotic "
                "pressure, and the pressure draws water in to grow the volume (sawtooth = a MODEL-IMPOSED "
                "division rule at a size/pressure threshold, not mechanical scission). Right: too permeable "
                "leaks the product so the pressure never builds (starve); too impermeable traps it so the "
                "pressure spikes past the burst tension (lyse)."))
