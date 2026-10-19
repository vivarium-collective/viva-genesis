"""Gate C–E study visualizations (og-32/33/34/35/36) — artifact-reader panels.

Each class is a committed-artifact reader (reads the study's JSON result, NO re-run;
that JSON is the deterministic result) that renders a multi-panel figure to the
richness bar of the original studies: the real chemistry/biology, the honest
verdict + numbers (qualified where qualified), and the simulation complexity.
Style via ``viz_style`` tokens (TEAL=positive/viable, RUST=negative/honest-negative,
AMBER=caution/boundary, SLATE=control); every axis/legend carries units via
``S.quantity_label``. Each degrades to a clean "artifact not found" panel rather
than throwing, so a render never hard-errors.

Declared from each study.yaml ``visualizations:`` as ``{address: local:<Class>,
config: {report_json / ... , title}}``.
"""
from __future__ import annotations

import json

from process_bigraph.visualization import Visualization

from . import viz_style as S
from .viz_uq import _resolve


def _load(path: str):
    p = _resolve(str(path or ""))
    if not p:
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _missing(name: str) -> str:
    return S.frame(
        f'<p style="padding:18px;color:{S.MUTED}">{name} not found — run the study\'s sims script '
        f"to generate it, then re-render.</p>",
        title="Artifact not available", tone="caution", max_width=900)


# =========================================================================== #
# og-32 — First Self-Maintaining Protocell (Gate C, QUALIFIED)
# =========================================================================== #
def self_maintaining_protocell_figure(gate_c: dict, md: dict | None, title: str = "") -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    comp = gate_c["boundary"]["composition"]            # [short di-C12, long di-C16]
    comp = comp[0] if (comp and isinstance(comp[0], list)) else comp   # tolerate [[...]] nesting
    by = {c["composition"]: c for c in comp}
    short = by.get("short_di-C12") or comp[0]
    long = by.get("long_di-C16") or comp[-1]
    md_res = (md or {}).get("results") or {}

    bd = gate_c["benefit_demo"]
    kdeg = gate_c["boundary"]["k_deg"]
    kdeg_max = float(gate_c["boundary"]["k_deg_boundary_max"])

    fig = make_subplots(
        rows=1, cols=3, horizontal_spacing=0.085,
        subplot_titles=(
            "Composition → permeability → retention",
            "Membrane pays on persistence, not throughput",
            "Integrity window (k_deg)",
        ),
    )

    # --- P1: thicker bilayer → lower permeability → higher retention (short vs long) ---
    x = ["short di-C12", "long di-C16"]
    fig.add_bar(x=x, y=[float(short["permeability"]), float(long["permeability"])],
                name="permeability", marker_color=S.AMBER, row=1, col=1,
                text=[f"{short['permeability']:.2f}", f"{long['permeability']:.2f}"], textposition="outside")
    fig.add_bar(x=x, y=[float(short["retention"]), float(long["retention"])],
                name="retention", marker_color=S.TEAL, row=1, col=1,
                text=[f"{short['retention']:.2f}", f"{long['retention']:.2f}"], textposition="outside")
    # thickness annotated on each group (different unit → annotation, not a third bar axis)
    for xi, c in zip(x, (short, long)):
        fig.add_annotation(x=xi, y=1.08, xref="x1", yref="y1", showarrow=False,
                           text=f"{c['thickness_nm']:.2f} nm", font=S.FONT(10, S.INK_SOFT))
    fig.update_yaxes(title_text="permeability (normalized) · retention (fraction)",
                     range=[0, 1.2], row=1, col=1)

    # --- P2: TOC benefit (persistence) vs net-flux benefit (throughput), as ratios around 1.0 ---
    toc_b = float(bd["toc_benefit"]); flux_b = float(bd["flux_benefit"])
    fig.add_bar(x=["standing pool<br>(TOC)", "fixation<br>(net flux)"], y=[toc_b, flux_b],
                marker_color=[S.TEAL, S.RUST], row=1, col=2,
                text=[f"{toc_b:.2f}×", f"{flux_b:.2f}×"], textposition="outside", showlegend=False)
    fig.add_hline(y=1.0, line=dict(color=S.SLATE, width=1, dash="dash"), row=1, col=2)
    fig.update_yaxes(title_text=S.quantity_label("benefit", unit="× vs no-membrane ablation"),
                     range=[0, max(toc_b, 1.0) * 1.25], row=1, col=2)

    # --- P3: net integrity vs k_deg, with the maintained boundary ---
    ks = [float(p["k_deg"]) for p in kdeg]
    integ = [float(p["net_integrity"]) for p in kdeg]
    maint = [bool(p["maintained"]) for p in kdeg]
    fig.add_scatter(x=ks, y=integ, mode="lines+markers", line=dict(color=S.INK, width=2),
                    marker=dict(color=[S.TEAL if m else S.RUST for m in maint], size=7),
                    name="net integrity", row=1, col=3, showlegend=False)
    fig.add_vline(x=kdeg_max, line=dict(color=S.AMBER, width=2, dash="dot"), row=1, col=3)
    fig.add_annotation(x=kdeg_max, y=max(integ), xref="x3", yref="y3", showarrow=False, yshift=6,
                       text=f"maintained ≤ {kdeg_max:g}/s", font=S.FONT(10, S.AMBER))
    fig.update_xaxes(title_text=S.quantity_label("k_deg", unit="s⁻¹"), type="log", row=1, col=3)
    fig.update_yaxes(title_text="net integrity (dimensionless)", row=1, col=3)

    fig.update_layout(S.base_layout(height=430, barmode="group",
                                    legend=dict(orientation="h", y=-0.18, x=0.0)))
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})

    plat = (md or {}).get("platform", "?"); tk = (md or {}).get("temp_k"); steps = (md or {}).get("prod_steps")
    apl = (md_res.get("DLPC") or {}).get("area_per_lipid_nm2")
    sim = (f"short Martini 3 CG-MD ({plat}"
           + (f", {tk:g} K" if isinstance(tk, (int, float)) else "")
           + (f", {int(steps)} steps" if isinstance(steps, (int, float)) else "")
           + (f", area/lipid {apl:g} nm²" if isinstance(apl, (int, float)) else "")
           + ")")
    cap = (
        f"<b>Left (Mechanism):</b> a thicker bilayer (long di-C16, {long['thickness_nm']:.2f} nm) has LOWER "
        f"permeability ({long['permeability']:.2f} vs {short['permeability']:.2f}, normalized) and HIGHER retention "
        f"({long['retention']:.2f} vs {short['retention']:.2f}) than the short di-C12 ({short['thickness_nm']:.2f} nm) "
        f"— a resolved composition→permeability→retention coupling, not a free knob. <b>These are phosphatidylcholine "
        f"Martini STAND-INS (DLPC/DPPC), NOT fatty acids.</b> <b>Middle (Decision):</b> the endogenous membrane raises "
        f"the standing metabolite pool to {toc_b:.2f}× the no-membrane ablation (persistence, TEAL) while net fixation "
        f"flux is {flux_b:.2f}× (throughput, RUST) — persistence_pays={bd['persistence_pays']}, "
        f"throughput_pays={bd['throughput_pays']} (feed-limited), beats_ablation={bd['beats_ablation']}. "
        f"<b>Right (boundary):</b> integrity is maintained for k_deg ≤ {kdeg_max:g}/s. Sim complexity: {sim} — a "
        f"MD-INFORMED structural proxy, NOT a PMF/free-energy closure (og-32a tracked). <b>Verdict QUALIFIED</b>: "
        f"persistence not throughput, windowed; metabolism = the sustained A1 network, not autocatalysis (A2 refuted)."
    )
    return S.frame(inner, title=(title or "The first self-maintaining protocell holds its pool"),
                   phase="Gate C", view="Mechanism · Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1180)


class OgSelfMaintainingProtocellViz(Visualization):
    """og-32 Gate C: composition→permeability→retention (MD-informed), the membrane's
    persistence-not-throughput benefit vs the matched no-membrane ablation, and the k_deg
    integrity window. Reads gate_c_full.json (+ md_bilayer_observables.json). Qualified."""

    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string",
                        "_default": "workspace/studies/og-self-compartmentation/artifacts/og-32-first-self-maintaining-protocell/gate_c_full.json"},
        "md_json": {"_type": "string",
                    "_default": "workspace/studies/og-self-compartmentation/artifacts/og-32-first-self-maintaining-protocell/md_bilayer_observables.json"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        gate_c = _load(self.config["report_json"])
        if gate_c is None:
            return {"html": _missing("gate_c_full.json")}
        md = _load(self.config["md_json"])   # optional — the MD caption degrades if absent
        return {"html": self_maintaining_protocell_figure(gate_c, md, title=self.config["title"])}


# =========================================================================== #
# og-34 — Chemical Heredity & Selection (Gate D, QUALIFIED — clearest positive)
# =========================================================================== #
def heredity_selection_figure(rep: dict, title: str = "") -> str:
    from plotly.subplots import make_subplots

    corr = rep["parent_offspring_correlation"]
    shift = rep["population_shift"]
    inh = rep["inheritance_arm"]; nul = rep["no_inheritance_arm"]
    m = rep.get("meta", {})

    fig = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.12,
        subplot_titles=("Inherited fitness correlation & population shift (vs null)",
                        "Per-seed selection response (every seed)"),
    )

    # --- P1: paired inheritance-vs-null bars for the two selection readouts ---
    xcats = ["parent–offspring<br>correlation", "population<br>shift"]
    fig.add_bar(x=xcats, y=[corr["inheritance_mean"], shift["inheritance_mean"]],
                name="inheritance", marker_color=S.TEAL, row=1, col=1,
                text=[f"{corr['inheritance_mean']:+.3f}", f"{shift['inheritance_mean']:+.3f}"], textposition="outside")
    fig.add_bar(x=xcats, y=[corr["null_mean"], shift["null_mean"]],
                name="shuffled null", marker_color=S.SLATE, row=1, col=1,
                text=[f"{corr['null_mean']:+.3f}", f"{shift['null_mean']:+.3f}"], textposition="outside")
    fig.add_hline(y=0.0, line=dict(color=S.MUTED, width=1), row=1, col=1)
    for xi, blk in zip(xcats, (corr, shift)):
        fig.add_annotation(x=xi, y=1.02, xref="x1", yref="y1", showarrow=False,
                           text=f"perm p={blk['perm_p']:.1e}", font=S.FONT(10, S.INK_SOFT))
    fig.update_yaxes(title_text="correlation · shift (dimensionless)", range=[-0.12, 1.12], row=1, col=1)

    # --- P2: every seed's shift — inheritance vs no-inheritance (honest spread) ---
    seeds = [a.get("seed", i) for i, a in enumerate(inh)]
    fig.add_scatter(x=seeds, y=[a["shift"] for a in inh], mode="markers",
                    marker=dict(color=S.TEAL, size=10, line=dict(color=S.PAPER, width=1)),
                    name="inheritance", row=1, col=2)
    fig.add_scatter(x=[a.get("seed", i) for i, a in enumerate(nul)], y=[a["shift"] for a in nul], mode="markers",
                    marker=dict(color=S.SLATE, size=10, symbol="diamond", line=dict(color=S.PAPER, width=1)),
                    name="no inheritance", row=1, col=2)
    fig.add_hline(y=0.0, line=dict(color=S.MUTED, width=1), row=1, col=2)
    fig.update_xaxes(title_text="seed (count)", row=1, col=2)
    fig.update_yaxes(title_text="population shift (fraction)", row=1, col=2)

    fig.update_layout(S.base_layout(height=430, barmode="group",
                                    legend=dict(orientation="h", y=-0.18, x=0.0)))
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    cap = (
        f"<b>Left (Decision):</b> inherited network composition drives a parent–offspring fitness correlation of "
        f"{corr['inheritance_mean']:+.3f} (TEAL) versus {corr['null_mean']:+.3f} for the shuffled null (SLATE), "
        f"permutation p={corr['perm_p']:.1e}; and a selected population shift of {shift['inheritance_mean']:+.3f} vs "
        f"{shift['null_mean']:+.3f}, p={shift['perm_p']:.1e}. <b>Right (Mechanism):</b> every one of the "
        f"{m.get('n_seeds', len(inh))} seeds is plotted (honest spread) — the inheritance arm shifts positively, the "
        f"no-inheritance arm sits at zero. Fitness is grounded in the real study-32/33 coupling "
        f"(composition→retention→standing pool→division rate), not a toy; the vasas-2010 evolvability caveat is tested "
        f"(declared σ={m.get('sigma', '?')}, not tuned). Sim: Wright-Fisher, {m.get('n_seeds','?')} seeds × "
        f"{m.get('n_generations','?')} generations, dependency-free permutation test (n_perm={m.get('n_perm','?')}; "
        f"PyMC noted, not installed). <b>Verdict QUALIFIED</b> on compositional inheritance (template copying = og-34a); "
        f"metabolism = sustained A1 network, not autocatalysis (A2 refuted)."
    )
    return S.frame(inner, title=(title or "Selectable compositional heredity"),
                   phase="Gate D", view="Decision · Mechanism", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1180)


class OgChemicalHeredityViz(Visualization):
    """og-34 Gate D: inherited-composition fitness correlation + selected population shift vs a
    shuffled null (permutation p), and the per-seed selection response across all seeds. Reads
    gate_d_heredity.json. Qualified — the clearest positive. (No lineage-tree panel: the artifact
    carries no per-generation lineage composition, so it is honestly omitted rather than invented.)"""

    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string",
                        "_default": "workspace/studies/og-heredity/artifacts/og-34-chemical-heredity-and-selection/gate_d_heredity.json"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        rep = _load(self.config["report_json"])
        if rep is None:
            return {"html": _missing("gate_d_heredity.json")}
        return {"html": heredity_selection_figure(rep, title=self.config["title"])}


# =========================================================================== #
# og-35 — Chemical Energy Coupling (Gate E, QUALIFIED)
# =========================================================================== #
def energy_coupling_figure(rep: dict, title: str = "") -> str:
    from plotly.subplots import make_subplots

    car = rep["carrier_arm"]; grad = rep["gradient_only_arm"]
    crit = rep["criteria"]; win = rep["k_hydrolyze_window"]
    bond = rep.get("meta", {}).get("bond_energy_kjmol")

    fig = make_subplots(
        rows=1, cols=3, horizontal_spacing=0.08,
        subplot_titles=("Useful work: carrier vs gradient-only",
                        "Free-energy ledger closure",
                        "Total work vs hydrolysis leak"),
    )

    # --- P1 (THE headline): carrier WINS the dip, LOSES on total (gradient-only higher) ---
    x = ["work through<br>the dip", "total useful<br>work"]
    fig.add_bar(x=x, y=[car["dip_useful_work"], car["total_useful_work"]], name="thioester carrier",
                marker_color=[S.TEAL, S.AMBER], row=1, col=1,
                text=[f"{car['dip_useful_work']:.3f}", f"{car['total_useful_work']:.3f}"], textposition="outside")
    fig.add_bar(x=x, y=[grad["dip_useful_work"], grad["total_useful_work"]], name="gradient-only null",
                marker_color=[S.RUST, S.SLATE], row=1, col=1,
                text=[f"{grad['dip_useful_work']:.3f}", f"{grad['total_useful_work']:.3f}"], textposition="outside")
    fig.update_yaxes(title_text=S.quantity_label("net_useful_work", unit="kJ/mol"), row=1, col=1)

    # --- P2: both ledgers close to ~0 (no hidden inflow) — the no-free-lunch panel ---
    fig.add_bar(x=["carrier", "gradient-only"],
                y=[abs(car["max_budget_residual"]), abs(grad["max_budget_residual"])],
                marker_color=[S.TEAL, S.SLATE], row=1, col=2, showlegend=False,
                text=[f"{car['max_budget_residual']:.1e}", f"{grad['max_budget_residual']:.1e}"], textposition="outside")
    fig.add_annotation(x=0.5, y=0.5, xref="x2 domain", yref="y2 domain", showarrow=False,
                       text=(f"ledger_closes={crit['ledger_closes']}<br>max|residual| ≈ machine precision<br>"
                             f"no hidden inflow"
                             + (f"<br>thioester bond {bond:g} kJ/mol" if bond else "")),
                       font=S.FONT(11, S.INK_SOFT), align="center")
    fig.update_yaxes(title_text=S.quantity_label("budget_residual", unit="kJ/mol"), row=1, col=2)

    # --- P3: carrier total vs k_hydrolyze, always below the gradient-only total (never pays) ---
    sw = win["sweep"]
    ks = [float(p["k_hydrolyze"]) for p in sw]
    ct = [float(p["carrier_total"]) for p in sw]
    cd = [float(p.get("carrier_dip", 0.0)) for p in sw]
    fig.add_scatter(x=ks, y=ct, mode="lines+markers", line=dict(color=S.AMBER, width=2),
                    name="carrier total", row=1, col=3)
    fig.add_scatter(x=ks, y=cd, mode="lines+markers", line=dict(color=S.TEAL, width=2, dash="dot"),
                    name="carrier dip", row=1, col=3)
    fig.add_hline(y=grad["total_useful_work"], line=dict(color=S.SLATE, width=1.5, dash="dash"), row=1, col=3)
    fig.add_annotation(x=ks[len(ks) // 2], y=grad["total_useful_work"], xref="x3", yref="y3", yshift=9,
                       showarrow=False, text="gradient-only total (never beaten)", font=S.FONT(10, S.RUST))
    fig.update_xaxes(title_text=S.quantity_label("k_hydrolyze", unit="s⁻¹"), row=1, col=3)
    fig.update_yaxes(title_text=S.quantity_label("net_useful_work", unit="kJ/mol"), row=1, col=3)

    fig.update_layout(S.base_layout(height=430, barmode="group",
                                    legend=dict(orientation="h", y=-0.18, x=0.0)))
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    pay = win.get("pay_boundary")
    cap = (
        f"<b>Left (Decision — the honest headline):</b> the thioester carrier does useful work THROUGH the gradient dip "
        f"({car['dip_useful_work']:.3f} kJ/mol, TEAL) where the matched gradient-only control starves "
        f"({grad['dip_useful_work']:.3f}, RUST) — persistence_pays={crit['persistence_pays']}; BUT total useful work is "
        f"NOT improved (carrier {car['total_useful_work']:.3f} vs gradient-only {grad['total_useful_work']:.3f}, drawn "
        f"higher in SLATE) — throughput_pays={crit['throughput_pays']}. The carrier banks/time-shifts energy into the "
        f"dip, it does not net more. <b>Middle (Mechanism):</b> the full free-energy ledger closes in both arms "
        f"(max|budget_residual| ≈ {car['max_budget_residual']:.0e} kJ/mol) — no hidden inflow, a real no-free-lunch "
        f"accounting. <b>Right (boundary):</b> carrier total stays BELOW the gradient-only total at every hydrolysis "
        f"leak rate (pay_boundary={pay} — never beats it, even at zero hydrolysis). <b>Verdict QUALIFIED</b>: "
        f"dip-persistence, not throughput (the acyl-phosphate / microkinetic resolution is og-35a); metabolism = the "
        f"sustained A1 network, not autocatalysis (A2 refuted)."
    )
    return S.frame(inner, title=(title or "The carrier buys gradient-dip resilience, not throughput"),
                   phase="Gate E", view="Decision · Mechanism", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1180)


class OgEnergyCouplingViz(Visualization):
    """og-35 Gate E: thioester carrier vs matched gradient-only control — wins the gradient dip
    (persistence) but not total useful work (throughput), with the free-energy ledger closing
    (no hidden inflow) and a k_hydrolyze sweep that never beats gradient-only. Reads
    gate_e_energy.json. Qualified — persistence not throughput."""

    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string",
                        "_default": "workspace/studies/og-energetics/artifacts/og-35-chemical-energy-coupling/gate_e_energy.json"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        rep = _load(self.config["report_json"])
        if rep is None:
            return {"html": _missing("gate_e_energy.json")}
        return {"html": energy_coupling_figure(rep, title=self.config["title"])}


# =========================================================================== #
# og-33 — Chemically-Coupled Growth & Division (Gate D, QUALIFIED positive)
# =========================================================================== #
def growth_division_figure(rep: dict, title: str = "") -> str:
    from plotly.subplots import make_subplots

    coup = rep["coupled"]; deco = rep["decoupled"]; imp = rep["imposed"]
    crit = rep["criteria"]; m = rep.get("meta", {})

    fig = make_subplots(
        rows=1, cols=3, horizontal_spacing=0.085,
        subplot_titles=("Division rate scales with metabolic flux",
                        "Coupled beats both nulls (equal feed)",
                        "Measured area-doubling geometry"),
    )

    # --- P1: division rate vs net carbon flux, coupled vs the two nulls ---
    cf = [p["net_carbon_flux"] for p in coup]; cr = [p["division_rate"] for p in coup]
    df = [p["net_carbon_flux"] for p in deco]; dr = [p["division_rate"] for p in deco]
    fig.add_scatter(x=cf, y=cr, mode="lines+markers", line=dict(color=S.TEAL, width=2),
                    name="coupled (metabolism-driven)", row=1, col=1)
    fig.add_scatter(x=df, y=dr, mode="lines+markers", line=dict(color=S.SLATE, width=2, dash="dash"),
                    name="growth-decoupled null", row=1, col=1)
    fig.add_hline(y=imp["division_rate"], line=dict(color=S.AMBER, width=1.5, dash="dot"), row=1, col=1)
    fig.add_annotation(x=cf[len(cf) // 2], y=imp["division_rate"], xref="x1", yref="y1", yshift=9,
                       showarrow=False, text="imposed-division null (timer)", font=S.FONT(10, S.AMBER))
    fig.update_xaxes(title_text=S.quantity_label("net_carbon_flux", unit="mol/s"), row=1, col=1)
    fig.update_yaxes(title_text=S.quantity_label("division_rate", unit="per step"), row=1, col=1)

    # --- P2: division rate at the canonical (max) flux, three arms + daughters viable ---
    cmax = coup[-1]["division_rate"]; dmax = deco[-1]["division_rate"]
    fig.add_bar(x=["coupled", "growth-<br>decoupled", "imposed<br>(timer)"],
                y=[cmax, dmax, imp["division_rate"]], marker_color=[S.TEAL, S.SLATE, S.AMBER],
                row=1, col=2, showlegend=False,
                text=[f"{cmax:.3f}", f"{dmax:.3f}", f"{imp['division_rate']:.3f}"], textposition="outside")
    fig.add_annotation(x=0.5, y=1.0, xref="x2 domain", yref="y2 domain", showarrow=False, yshift=4,
                       text=f"daughters viable = {imp.get('daughter_viable', 1.0):.0f}", font=S.FONT(11, S.TEAL))
    fig.update_yaxes(title_text=S.quantity_label("division_rate", unit="per step"), row=1, col=2)

    # --- P3: the measured geometry from the real data — membrane area grows and reduced
    # volume falls toward the area-doubling budding threshold ONLY in the coupled arm ---
    fig.add_scatter(x=cf, y=[p["membrane_area"] for p in coup], mode="lines+markers",
                    line=dict(color=S.TEAL, width=2), name="coupled area", row=1, col=3)
    fig.add_scatter(x=df, y=[p["membrane_area"] for p in deco], mode="lines+markers",
                    line=dict(color=S.SLATE, width=2, dash="dash"), name="decoupled area", row=1, col=3)
    fig.update_xaxes(title_text=S.quantity_label("net_carbon_flux", unit="mol/s"), row=1, col=3)
    fig.update_yaxes(title_text="membrane area (nm²)", row=1, col=3)

    fig.update_layout(S.base_layout(height=430, legend=dict(orientation="h", y=-0.2, x=0.0)))
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    rv = [p["reduced_volume"] for p in coup]
    cap = (
        f"<b>Left (Mechanism):</b> when division is driven by the cell's OWN metabolic amphiphile production "
        f"(coupled, TEAL), the division rate SCALES with net carbon flux ({coup[0]['division_rate']:.3f}→"
        f"{coup[-1]['division_rate']:.3f} per step, slope {rep.get('coupled_slope', 0):.0f}); the growth-decoupled "
        f"null (SLATE) stays flat ({dr[0]:.3f}, flux-independent), and the imposed-division null (AMBER) fires on a "
        f"fixed timer ({imp['division_rate']:.3f}). <b>Right (Decision):</b> at equal feed the coupled arm beats BOTH "
        f"nulls and the daughters are viable ({imp.get('daughter_viable', 1.0):.0f}) — "
        f"growth_from_metabolism={crit['growth_from_metabolism']}, division_at_geometry={crit['division_at_geometry']}, "
        f"beats_null={crit['beats_null']}. <b>Right (geometry):</b> only the coupled arm GROWS its membrane with flux "
        f"({coup[0]['membrane_area']:.1f}→{coup[-1]['membrane_area']:.1f} nm², reduced volume {rv[0]:.2f}→{rv[-1]:.2f} "
        f"toward the budding threshold); the decoupled arm is flat — so division fires at a "
        f"{m.get('division_geometry', 'measured area-doubling geometry')}, no imposed event. Rate is per model step "
        f"(each run's preferred_time is 6 h over n_steps). <b>Verdict QUALIFIED</b> on the measured-geometry first cut "
        f"(og-33a); metabolism = the sustained A1 network, not autocatalysis (A2 refuted)."
    )
    return S.frame(inner, title=(title or "Metabolism-driven growth & division"),
                   phase="Gate D", view="Mechanism · Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1180)


class OgGrowthDivisionViz(Visualization):
    """og-33 Gate D: division rate scales with metabolic (net-carbon) flux when coupled, flat when
    growth-decoupled, timer-fixed when imposed — the coupled arm beats both nulls at equal feed with
    viable daughters, division firing at a measured area-doubling geometry (ratio 2.0). Reads
    gate_d_growth_division.json (a 3-arm comparison, not a grid — hence a dedicated reader, not
    GrowthDivisionMap). Qualified."""

    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string",
                        "_default": "workspace/studies/og-33-chemically-coupled-growth-and-division/artifacts/gate_d_growth_division.json"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        rep = _load(self.config["report_json"])
        if rep is None:
            return {"html": _missing("gate_d_growth_division.json")}
        return {"html": growth_division_figure(rep, title=self.config["title"])}


# =========================================================================== #
# og-36 — Stochastic Protocell Ecology (Gate E, QUALIFIED — productivity-yes, robustness-no)
# =========================================================================== #
def stochastic_ecology_figure(rep: dict, title: str = "") -> str:
    from plotly.subplots import make_subplots

    sto = rep["stochastic"]; det = rep["deterministic"]; sweep = rep["omega_sweep"]
    crit = rep["criteria"]; m = rep.get("meta", {})
    comm = sto["community"]; best = sto["best_single"]; ko = sto["knockout"]

    fig = make_subplots(
        rows=1, cols=3, horizontal_spacing=0.085,
        subplot_titles=("Community out-produces the best single lineage",
                        "Cross-feeding is causal (knockout)",
                        "The robustness cost (system-size sweep)"),
    )

    # --- P1: community vs best-single vs knockout cumulative productivity, equal feed ---
    fig.add_bar(x=["community", "best single<br>lineage", "cross-feeding<br>knockout"],
                y=[comm["mean"], best["mean"], ko["mean"]],
                error_y=dict(type="data", array=[comm.get("sd", 0), best.get("sd", 0), ko.get("sd", 0)], visible=True),
                marker_color=[S.TEAL, S.SLATE, S.RUST], row=1, col=1, showlegend=False,
                text=[f"{comm['mean']:.0f}", f"{best['mean']:.0f}", f"{ko['mean']:.0f}"], textposition="outside")
    fig.add_annotation(x=0, y=comm["mean"], xref="x1", yref="y1", yshift=22, showarrow=False,
                       text=f"{comm['mean'] / best['mean']:.2f}× best single", font=S.FONT(11, S.TEAL))
    fig.update_yaxes(title_text=S.quantity_label("cumulative_productivity", unit="births"), row=1, col=1)

    # --- P2: the causal margin — community margin vs the collapsed knockout margin ---
    cm = sto["margin"]; km = sto["ko_margin"]
    fig.add_bar(x=["community<br>margin", "knockout<br>margin"], y=[cm, km],
                marker_color=[S.TEAL, S.RUST], row=1, col=2, showlegend=False,
                text=[f"+{cm:.0f}", f"+{km:.0f}"], textposition="outside")
    fig.add_annotation(x=0.5, y=0.9, xref="x2 domain", yref="y2 domain", showarrow=False,
                       text=f"knockout keeps only<br>{sto['ko_margin_fraction'] * 100:.0f}% of the margin",
                       font=S.FONT(11, S.RUST), align="center")
    fig.update_yaxes(title_text="productivity margin over best single (births)", row=1, col=2)

    # --- P3: stochastic vs deterministic margin across system size; extinction rises as counts fall ---
    om = [p["omega"] for p in sweep]
    ssa = [p["ssa_margin"] for p in sweep]; dete = [p["det_margin"] for p in sweep]
    fig.add_scatter(x=om, y=ssa, mode="lines+markers", line=dict(color=S.TEAL, width=2),
                    name="stochastic (SSA)", row=1, col=3)
    fig.add_scatter(x=om, y=dete, mode="lines+markers", line=dict(color=S.SLATE, width=2, dash="dash"),
                    name="deterministic", row=1, col=3)
    for p in sweep:
        fig.add_annotation(x=p["omega"], y=p["ssa_margin"], xref="x3", yref="y3", yshift=-14, showarrow=False,
                           text=f"{p['extinction_frac'] * 100:.0f}% ext", font=S.FONT(9, S.RUST))
    fig.update_xaxes(title_text=S.quantity_label("omega", unit="system size, count"), row=1, col=3)
    fig.update_yaxes(title_text="margin (births)", row=1, col=3)

    fig.update_layout(S.base_layout(height=440, legend=dict(orientation="h", y=-0.2, x=0.0)))
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
    cap = (
        f"<b>Left (Decision):</b> at equal feed a cross-feeding community of {m.get('n_lineages', '?')} lineages "
        f"out-produces the BEST single lineage {comm['mean'] / best['mean']:.2f}× ({comm['mean']:.0f} vs "
        f"{best['mean']:.0f} cumulative births; margin positive in {sto['frac_seeds_positive'] * 100:.0f}% of seeds) — "
        f"the one place in the campaign productivity genuinely improves. <b>Middle (Mechanism):</b> the margin is "
        f"CAUSALLY cross-feeding — the knockout (cross-feeding off, same feed) collapses it to {km:.0f} "
        f"({sto['ko_margin_fraction'] * 100:.0f}% of the community margin), and coexistence is stabilised by depletable "
        f"byproduct pools (deterministic: all {det['community'].get('n_alive', '?'):.0f} lineages persist; knockout "
        f"excludes to {det['knockout'].get('n_alive', '?'):.0f}). <b>Right (the robustness cost):</b> under low-count "
        f"demographic noise the community is MORE variable than the rock-stable monoculture (cv {comm['cv']:.2f} vs "
        f"{best['cv']:.2f}) and loses a lineage in {comm['extinction_frac'] * 100:.0f}% of runs; the system-size sweep "
        f"shows the stochastic margin falling below the mean-field as counts drop (to {sweep[0]['extinction_frac'] * 100:.0f}% "
        f"extinction at Ω {sweep[0]['omega']}). So productivity-YES, robustness-NO — the COUNTERPOINT to the spine's "
        f"persistence-not-throughput mechanisms (B/C/study-35), not a repeat. <b>Verdict QUALIFIED</b>: lightweight "
        f"dependency-free Gillespie SSA (og-36a = GillesPy2/COBRApy); metabolism = sustained A1 community, not "
        f"autocatalytic (A2 refuted)."
    )
    return S.frame(inner, title=(title or "Stochastic protocell ecology — productivity, not robustness"),
                   phase="Gate E", view="Decision · Mechanism", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1180)


class OgStochasticEcologyViz(Visualization):
    """og-36 Gate E: a cross-feeding community out-produces the best single lineage (~1.9×, causal
    via knockout) but PAYS in robustness under low-count stochasticity (more variable, lineage loss
    rising as counts fall) — the productivity↔robustness counterpoint to the spine. Reads
    gate_e_ecology.json. Qualified."""

    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string",
                        "_default": "workspace/studies/og-36-stochastic-protocell-ecology/artifacts/gate_e_ecology.json"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        rep = _load(self.config["report_json"])
        if rep is None:
            return {"html": _missing("gate_e_ecology.json")}
        return {"html": stochastic_ecology_figure(rep, title=self.config["title"])}


# =========================================================================== #
# og-32b — Fatty-Acid Vesicle Stability (Gate C, real amphiphile — QUALIFIED)
# =========================================================================== #
def fatty_acid_vesicle_stability_figure(rep: dict, title: str = "") -> str:
    from plotly.subplots import make_subplots

    arms = rep.get("arms", [])
    thr = rep.get("verdict_thresholds", {})
    inner_min = float(thr.get("inner_leaflet_min", 0.20))
    cv_max = float(thr.get("head_radial_cv_max", 0.35))
    hd = rep.get("headline", {})

    prot = sorted([a for a in arms if a.get("protonated")], key=lambda a: a["chain"])
    null = sorted([a for a in arms if not a.get("protonated")], key=lambda a: a["chain"])

    def tone(a):
        return S.TEAL if a["verdict"] == "stable_vesicle" else S.RUST

    fig = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.14,
        subplot_titles=("Protonated fatty-acid vesicles hold a bilayer (C10-C16)",
                        "The charged-only null micellises at the short-chain corner"))

    # P1 — inner-leaflet retention vs chain, protonated arms (bilayer-vs-micelle)
    xs = [a["chain"] for a in prot]
    ys = [a["inner_leaflet_fraction"] for a in prot]
    es = [a.get("inner_leaflet_fraction_std", 0.0) for a in prot]
    fig.add_scatter(
        x=xs, y=ys, mode="lines+markers",
        line=dict(color=S.SLATE, width=1.5),
        marker=dict(color=[tone(a) for a in prot], size=12,
                    line=dict(color=S.INK, width=1)),
        error_y=dict(type="data", array=es, visible=True, color=S.SLATE, thickness=1),
        showlegend=False, row=1, col=1)
    fig.add_hline(y=inner_min, line=dict(color=S.SLATE, width=1, dash="dot"), row=1, col=1)
    fig.add_annotation(x=xs[len(xs) // 2] if xs else 13, y=inner_min, yshift=-12,
                       xref="x1", yref="y1", showarrow=False,
                       text=f"bilayer threshold (inner-leaflet >= {inner_min:g})",
                       font=S.FONT(9, S.SLATE))
    fig.update_xaxes(title_text="fatty-acid chain length (carbons)",
                     tickvals=xs, row=1, col=1)
    fig.update_yaxes(title_text=S.quantity_label("inner_leaflet_fraction",
                                                  unit="dimensionless"),
                     range=[0, max(0.5, (max(ys) if ys else 0.4) + 0.1)], row=1, col=1)

    # P2 — head-radial CV (dispersal), protonated vs charged-null at shared chains
    null_chains = [a["chain"] for a in null]
    pairs = [c for c in null_chains]
    cats = [f"C{c}" for c in pairs]
    prot_by = {a["chain"]: a for a in prot}
    cv_prot = [prot_by[c]["head_radial_cv"] if c in prot_by else 0.0 for c in pairs]
    cv_prot_e = [prot_by[c].get("head_radial_cv_std", 0.0) if c in prot_by else 0.0 for c in pairs]
    null_by = {a["chain"]: a for a in null}
    cv_null = [null_by[c]["head_radial_cv"] for c in pairs]
    cv_null_e = [null_by[c].get("head_radial_cv_std", 0.0) for c in pairs]
    fig.add_bar(x=cats, y=cv_prot, name="protonated (COOH)", marker_color=S.TEAL,
                error_y=dict(type="data", array=cv_prot_e, visible=True, color=S.INK, thickness=1),
                row=1, col=2)
    fig.add_bar(x=cats, y=cv_null, name="charged-only null (COO-)", marker_color=S.RUST,
                error_y=dict(type="data", array=cv_null_e, visible=True, color=S.INK, thickness=1),
                row=1, col=2)
    fig.add_hline(y=cv_max, line=dict(color=S.AMBER, width=1.5, dash="dot"), row=1, col=2)
    fig.add_annotation(x=0.5, y=cv_max, xref="x2 domain", yref="y2", yshift=9, showarrow=False,
                       text=f"micelle threshold (CV > {cv_max:g})", font=S.FONT(9, S.AMBER))
    fig.update_yaxes(title_text=S.quantity_label("head_radial_cv", unit="dimensionless"),
                     row=1, col=2)

    fig.update_layout(S.base_layout(height=430))
    fig.update_layout(barmode="group", legend=dict(orientation="h", y=-0.22, x=0.55))
    inner = fig.to_html(full_html=False, include_plotlyjs="cdn",
                        config={"displayModeBar": False})

    win = hd.get("stable_chain_window", [])
    nseed = prot[0]["n_seeds"] if prot else "?"
    cap = (
        f"<b>Left (chain-length window):</b> real single-chain fatty-acid vesicles (viva-openmm Martini 3, "
        f"{nseed} independent MD seeds/arm) retain a closed bilayer - a populated INNER leaflet above the "
        f"{inner_min:g} threshold (a water lumen + two leaflets, not a single-surface micelle) - across the "
        f"protonated C10-C16 axis (stable chains: {win}; TEAL=bilayer, RUST=micelle). <b>Right (matched "
        f"null):</b> the SAME fatty acid with fully-ionised charged-only heads (COO-) micellises at the "
        f"short-chain corner - its head-radial CV crosses the {cv_max:g} dispersal threshold while the "
        f"protonated arm stays coherent - the control that should fail. Longer charged chains do NOT disrupt "
        f"within this short CPU-MD window. <b>Honest scope:</b> a SHORT-MD stability TREND (~0.8 ns/seed), "
        f"not a converged micellisation equilibrium; the converged chain-length/charge window + the pH-resolved "
        f"(mixed-protonation) boundary are the GPU gold-standard follow-ups (og-32c self-assembly, og-32a PMF). "
        f"The SP2/SQ5n head is a tracked Martini-3 building-block proposed_input; the C1 tails are authoritative. "
        f"This replaces og-32's DLPC/DPPC phospholipid stand-in with the real protocell amphiphile. Verdict "
        f"<b>qualified</b>."
    )
    return S.frame(inner, title=(title or "Fatty-acid vesicle stability"),
                   phase="Gate C", view="Decision", tier="mechanistic_prediction",
                   caption_text=cap, caption_prefix="How to read", tone="neutral", max_width=1120)


class OgFattyAcidVesicleStabilityViz(Visualization):
    """og-32b Gate C: REAL single-chain fatty-acid vesicles (viva-openmm Martini 3) hold a closed
    bilayer across the C10-C16 chain window over >=3 MD seeds, while the matched charged-only null
    micellises at the short-chain corner. Reads vesicle_stability.json. Replaces og-32's DLPC/DPPC
    phospholipid stand-in with the real amphiphile. Qualified (short-MD trend)."""

    config_schema = {
        "title": {"_type": "string", "_default": ""},
        "report_json": {"_type": "string",
                        "_default": "workspace/studies/og-self-compartmentation/artifacts/og-32b-fatty-acid-vesicle-stability/vesicle_stability.json"},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        rep = _load(self.config["report_json"])
        if rep is None:
            return {"html": _missing("vesicle_stability.json")}
        return {"html": fatty_acid_vesicle_stability_figure(rep, title=self.config["title"])}
