"""Spatial PDE field snapshots for og-spatial-concentration (Tier-1 figure).

Figure-review request: a 2x3 PDE snapshot grid of the eight-solute concentration
fields at t=0 / transient / steady, pore vs open-pore control, on identical
colour scales, plus axial profiles, per-species enrichment factors, the species
co-localization index, a mass-conservation (FVM flux-divergence) residual, and a
decomposition of the thermophoretic vs advective/diffusive drivers.

Everything written here is a REAL field read from the genuine FiPy accumulation
column (``viva_genesis.transport.thermophoretic_trap.ThermophoreticTrapProcess``,
the ``thermophoretic_concentration`` composite's trap) via the read-only
``trap_field_snapshots`` accessor. Each of the eight chemically-necessary prebiotic
solutes is transported with its OWN literature-bracketed Soret coefficient and
diffusivity (``multisolute_localization._DEFAULT_TRANSPORT``), so the fractionation
is the solver's result, not an assignment.

HONEST-BAR: the trap solver is a 1-D vertical accumulation column (Grid1D), so the
genuine fields are AXIAL c(z). A true 2-D (x,y) radial pore-geometry field and the
radial profile are NOT computed by this composite — they require the 3-D dolfinx
FEM reference (``FenicsMultisolutePoreProcess``), which is conda-only and runs under
viva-fenics's pixi env. Those are flagged ``requested_future_simulation`` in the
artifact and labelled as such in the figure, never fabricated.

Matched control: the open-pore arm uses porosity=0.99 (epsilon-away from the
wash-through limit), NOT 1.0 — a bare 0.0/limit knob is backfilled to the default
by the pbg is_empty rule and would silently reproduce the favourable arm.
"""
from __future__ import annotations

import json
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ART_DIR = STUDY_DIR / "artifacts" / "og-03-dilution-to-localized-individuals"
OUT = ART_DIR / "spatial_pde_fields.json"
COLOC_GRID = ART_DIR / "colocalization_grid.json"

# Snapshot sweeps: 0 = uniform feed (t=0), 1 = transient, 4 = settled column.
CAPTURES = (0, 1, 4)
CAPTURE_LABELS = {"0": "t = 0 (uniform feed)", "1": "transient", "4": "steady"}

# Favourable serpentinite pore vs the open-pore wash-through control (epsilon, not 1.0).
ARMS = {"pore": {"porosity": 0.30, "flow_velocity": 1.0e-4},
        "open_pore": {"porosity": 0.99, "flow_velocity": 1.0e-4}}

CANONICAL_RUN = (
    "viva_genesis.composites.thermophoretic_concentration."
    "thermophoretic_concentration__1791944471__df60ba"
)


def main() -> int:
    from viva_genesis.core import build_core
    from viva_genesis.multisolute_localization import (
        COLOCALIZATION_SPECIES, _DEFAULT_TRANSPORT,
    )
    from viva_genesis.transport.thermophoretic_trap import (
        ThermophoreticTrapProcess, trap_field_snapshots,
    )

    core = build_core()

    # Species ordered weak -> strong thermophoresis (Soret), for the heatmap y-axis.
    species = sorted(COLOCALIZATION_SPECIES, key=lambda s: _DEFAULT_TRANSPORT[s][1])

    def run_species(name: str, arm: dict) -> dict:
        D_1e9, soret, *_ = _DEFAULT_TRANSPORT[name]
        proc = ThermophoreticTrapProcess(
            config={"soret_coeff": soret, "solute_diffusivity": D_1e9 * 1e-9}, core=core)
        f = trap_field_snapshots(proc, arm, captures=CAPTURES)
        f["species"] = name
        return f

    arms_out: dict = {}
    z_mm = None
    max_resid = 0.0
    for arm_name, arm in ARMS.items():
        per_species = {}
        for name in species:
            fs = run_species(name, arm)
            if z_mm is None:
                z_mm = fs["z_mm"]
            max_resid = max(max_resid, fs["flux_divergence_residual"])
            per_species[name] = fs
        # Single-tracer headline trap (default Soret 0.10) for this arm.
        headline = trap_field_snapshots(
            ThermophoreticTrapProcess(config={}, core=core), arm, captures=CAPTURES)
        max_resid = max(max_resid, headline["flux_divergence_residual"])
        arms_out[arm_name] = {"params": arm, "species": per_species, "headline": headline}

    def coloc(per_species: dict, key: str) -> float:
        vals = [per_species[s][key] for s in species]
        mx = max(vals)
        return (min(vals) / mx) if mx > 0 else float("nan")

    coloc_resolved = coloc(arms_out["pore"]["species"], "enrichment_resolved")
    coloc_emitted = coloc(arms_out["pore"]["species"], "enrichment_emitted")

    # Reference the study's canonical surrogate/FEM co-localization (do NOT recompute
    # or alter it) — the strong-Soret FEM audit point from colocalization_grid.json.
    canonical_coloc = None
    if COLOC_GRID.exists():
        try:
            cg = json.loads(COLOC_GRID.read_text())
            audit = cg.get("meta", {}).get("fem_audit", [])
            strong = [a for a in audit if a.get("soret_scale", 0) >= 8.0]
            canonical_coloc = (strong or audit or [{}])[0].get("fem_coloc_index")
        except Exception:
            canonical_coloc = None

    artifact = {
        "study": "og-spatial-concentration",
        "figure": "spatial-pde-field-grid (Tier-1)",
        "composite": "viva_genesis.composites.thermophoretic_concentration.thermophoretic_concentration",
        "process": "viva_genesis.transport.thermophoretic_trap.ThermophoreticTrapProcess (real FiPy FVM)",
        "run_ref": CANONICAL_RUN,
        "description": (
            "Real FiPy accumulation-column concentration fields for the eight "
            "chemically-necessary prebiotic solutes, each with its own Soret "
            "coefficient and diffusivity, at successive FVM sweeps (t=0 / transient "
            "/ settled) in a favourable serpentinite pore vs an open-pore wash-through "
            "control. All fields are read from the genuine FiPy solve; co-localization, "
            "enrichment and the flux residual are derived from those fields."
        ),
        "geometry": {
            "dimensionality": "1-D vertical accumulation column (Grid1D)",
            "axis": "z (axial, along pore); base z=0 (trapped), feed z=L (top)",
            "z_mm": z_mm,
            "pore_length_m": arms_out["pore"]["headline"]["extent_m"][1],
            "units": {"z": "mm", "concentration": "dimensionless (c/c_feed)",
                      "soret": "1/kelvin (process knob)", "delta_T": "kelvin",
                      "D": "meter**2/second", "pe_conv": "dimensionless",
                      "enrichment": "dimensionless"},
        },
        "captures": list(CAPTURES),
        "capture_labels": CAPTURE_LABELS,
        "species_order": species,
        "arms": arms_out,
        "colocalization_index": {
            "resolved_field_base_over_top": coloc_resolved,
            "emitted_exp_peclet": coloc_emitted,
            "method": "min/max of per-species steady enrichment (1=co-localized, ->0=fractionating)",
            "canonical_surrogate_fem_reference": canonical_coloc,
            "canonical_source": (
                "workspace/studies/og-spatial-concentration/artifacts/"
                "og-03-dilution-to-localized-individuals/colocalization_grid.json "
                "(strong-Soret FEM audit point; the study's headline ~0.18 — reported, not changed)"
            ),
        },
        "mass_conservation": {
            "max_abs_flux_divergence_residual": max_resid,
            "note": "FVM flux-divergence residual across all arms/species (direct LU); ~machine epsilon.",
        },
        "transport_decomposition": {
            "note": (
                "beta = geom * (soret * delta_T) * pe_conv / pore_width * (1 - porosity); "
                "accumulation Peclet = beta * pore_length = ln(enrichment). "
                "THERMOPHORESIS = soret * delta_T (Soret drift toward the cold wall); "
                "ADVECTION = pe_conv = flow_velocity * pore_width / D (convective Peclet); "
                "DIFFUSION = D (smooths the column); CONFINEMENT = 1 - porosity "
                "(the open-pore control sends this -> ~0)."
            ),
            "per_species": {
                s: arms_out["pore"]["species"][s]["terms"] for s in species
            },
        },
        "requested_future_simulation": {
            "fields": ["2-D (x,y) radial pore-geometry concentration field",
                       "radial concentration profile"],
            "reason": (
                "The thermophoretic_concentration trap solver is a 1-D vertical "
                "accumulation column (Grid1D), so it resolves the AXIAL field only. "
                "A true 2-D/3-D radial field (converging-diverging throat geometry) "
                "requires the dolfinx FEM reference FenicsMultisolutePoreProcess, which "
                "is conda-only and runs under viva-fenics's pixi env (dolfinx not "
                "importable in this uv venv). Flagged here, never fabricated."
            ),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2))

    print(f"pore co-localization index (resolved field): {coloc_resolved:.4g}")
    print(f"pore co-localization index (emitted exp Pe):  {coloc_emitted:.4g}")
    print(f"canonical surrogate/FEM coloc (unchanged):    {canonical_coloc}")
    print(f"max FVM flux-divergence residual:             {max_resid:.3e}")
    print("per-species steady enrichment (pore arm, resolved base/top | emitted exp(Pe)):")
    for s in species:
        fs = arms_out["pore"]["species"][s]
        print(f"  {s:22s} soret={fs['terms']['soret']:.3f}  "
              f"resolved={fs['enrichment_resolved']:.3g}  emitted={fs['enrichment_emitted']:.3g}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
