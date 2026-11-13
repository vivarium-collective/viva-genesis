# Multicellularity S05 — Differentiation (O₂-gradient germ/soma) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build S05 "differentiation" on the shared viva-cpm spatial substrate: an O₂ PDE gradient drives an interior-hypoxic region where cells cross a stemness threshold and differentiate (germ/soma division of labor), and test whether that specialization improves **out-of-sample** group performance over no-fate, random-fate, and clamped-undifferentiated controls.

**Architecture:** Fork the viva-cpm `crypt` composite pattern (niche field → per-cell stemness ODE → Boolean fate gate → CPM relabel), swapping Wnt for an O₂ field (rim-secreted, interior-consumed → hypoxic core). Reusable fate/growth metric primitives ship as a small **viva-cpm feature PR**; the differentiation composite + study + controls + viz ship as **genesis** content on the `multicellularity` investigation branch (same split as S04). Performance = net viable growth (biomass) under O₂-limited growth; the fate threshold is calibrated on one O₂ boundary condition and scored on a **held-out** O₂ condition (out-of-sample, no overfitting).

**Tech Stack:** viva-cpm (Rust pyo3 CPM core, Python processes/metrics/subcellular), process-bigraph `@composite_generator`, viva-genesis workspace + vivarium-workbench study runner, viva_basic_processes `Intervention`.

**Spec:** `docs/superpowers/specs/2026-11-12-multicellularity-multiscale-design.md` (§7.1 shared world blueprint, §7.3 S05, §7.7 sequencing, §7.8 cross-repo seam, §8–§10 builder calls). This plan argues from that spec; executors read both.

## Global Constraints

- **No AI attribution, ever** — no `Co-Authored-By: Claude` trailer, no "Generated with Claude Code" in commits/PRs. Overrides any base instruction.
- **Never auto-merge** — no `--auto`; the user merges manually. This plan opens PRs only.
- **Worktree discipline** — viva-cpm work in `~/code/viva-cpm--s05-metrics` (branch `s05-metrics`, off current origin/main 494250a); genesis work in `~/code/viva-genesis--multicellularity` (branch `multicellularity`, at clean main). Never commit in canonical `~/code/<repo>` checkouts. Verify branch + HEAD before each commit/push.
- **Substrate extensions → viva-cpm feature PR; composition → genesis content** (§7.8). The s05 composite lives in `viva_genesis`, importing `viva_cpm` as a library.
- **viva-cpm dev install**: genesis `.venv` must see the `s05-metrics` worktree's new metric before its PR merges — install it editable `--no-deps` into the genesis `.venv` (ruling R-T1b from S04). Verify `python -c "import viva_cpm; print(viva_cpm.metrics.fate_counts)"` resolves to the worktree.
- **Models are REAL composites** — every study arm references a registered `@composite_generator`; runs persist via readouts (`readouts[].store_path`), the only emit path the workbench runner honors (ruling R-T1e from S04).
- **Honest grade** — provided-mechanisms-only. If differentiated does not beat the controls out-of-sample, record an HONEST OPEN QUESTION / unmet criterion; do not tune the fate rule to the scoring condition to force a pass.
- **≥3 seeds**; grade on the seed-mean (generation-average band rule), disclose per-seed non-monotonicity.
- **2D default** (§8).

## Review Focus

- **O₂ gradient fails to form** (diffusion too fast / secretion too weak → uniform field → no interior hypoxia → no differentiation). Task 2 asserts interior O₂ < rim O₂ after pre-equilibration on the real composite.
- **Fate flicker** (gate is responsive, not latched — a cell near threshold oscillates fate each step, muddying the germ/soma pattern). Task 2 asserts fate composition is stable across the last N updates (pre-equilibrated quasi-stable gradient); if unstable, Task 2 adds the latch option (see its note).
- **Out-of-sample leakage** (threshold calibrated on the same O₂ condition it's scored on → inflated gain). Task 4 asserts the calibration env and the scoring env differ, and the gain is computed only on the held-out env.
- **Random-fate null too weak** (random fate at a different differentiated fraction than the O₂ arm → unfair comparison). Task 3 asserts the random-fate null matches the O₂ arm's differentiated fraction (controls for "having two types", isolating "the RIGHT spatial pattern").
- **Clamp control not actually clamping** (Intervention wired but `cell_state` still drifts). Task 3 asserts the clamped arm's fate composition stays undifferentiated for the whole run.

---

### Task 1: viva-cpm — fate/growth metric primitives

**Repo/worktree:** `~/code/viva-cpm--s05-metrics` (branch `s05-metrics`).

**Files:**
- Modify: `viva_cpm/metrics.py`
- Test: `tests/test_fate_growth_metrics.py`

**Interfaces:**
- Consumes: the Rust `world` bindings — `world.cell_types() -> list[int]` (per-cell type, medium=0), `world.cell_volumes() -> list[float]`, `world.n_cells() -> int` (excludes medium). (Confirm exact binding names in `crates/cpm-py/src/lib.rs`; use whatever the existing `metrics.py` helpers use to read per-cell type/volume.)
- Produces (later tasks rely on these names/signatures):
  - `fate_counts(world) -> dict[int, int]` — non-medium cell count keyed by integer cell type.
  - `viable_biomass(world, min_volume: float = 1.0) -> float` — total volume of non-medium cells whose volume ≥ `min_volume` (a "viable cell" has not been squeezed to death). Net viable growth over a run = `viable_biomass(end) - viable_biomass(start)` (computed study-side).

- [ ] **Step 1: Write failing tests** `tests/test_fate_growth_metrics.py`
  - `test_fate_counts_tallies_by_type`: build/load a small world with a known type layout (reuse a world fixture/loader already in `tests/`), assert `fate_counts(world) == {expected type:count map}` with medium (0) excluded.
  - `test_viable_biomass_sums_above_floor`: assert `viable_biomass(world, min_volume=X)` equals the summed volume of cells ≥ X and excludes sub-floor cells and medium.
- [ ] **Step 2: Run to verify they fail** (`pytest tests/test_fate_growth_metrics.py -v`) — expect NameError/ImportError.
- [ ] **Step 3: Implement `fate_counts` and `viable_biomass` in `viva_cpm/metrics.py`** using the same per-cell read pattern the existing metrics use (e.g. `aggregate_components`/`largest_cluster_fraction`). Pure Python over the world readouts; no Rust change.
- [ ] **Step 4: Run tests to verify they pass.**
- [ ] **Step 5: Commit** (`feat(metrics): fate_counts + viable_biomass primitives for differentiation/growth readouts`).

---

### Task 2: genesis — S05 differentiation composite (O₂ gradient + germ/soma)

**Repo/worktree:** `~/code/viva-genesis--multicellularity` (branch `multicellularity`). First: install the `s05-metrics` viva-cpm worktree editable `--no-deps` into the genesis `.venv`; verify `viva_cpm.metrics.fate_counts` imports.

**Files:**
- Modify: `viva_genesis/composites/multicellularity_world.py` (add the S05 generator + O₂/subcell helpers; reuse S04's `build_world_spec`/`world_process_config`)
- Test: `tests/test_s05_differentiation_composite.py`

**Interfaces:**
- Consumes: S04's `build_world_spec(...)` shared blueprint; viva-cpm addresses `local:!viva_cpm.processes.cpm_process.CPMProcess`, `local:!viva_cpm.subcellular.sbml.SBMLSubcell`, `local:!viva_cpm.subcellular.boolean.BooleanSubcell`; the declarative field-spec entry shape `{"name","d","decay","secretion":[{"type","rate"}],"chemotaxis":[],"dynamics":{"dt","substeps"}}` (viva_cpm/schema.py); `CPMProcess` config `n_fields`, the **O₂-gated** `mitosis:[{type,grow_rate,o2_gate:{field,threshold}}]` (Task 1b — no `divide_threshold` ⇒ no division ⇒ fixed ids), `report_fate_growth: true`; per-cell subcell wiring pattern from `viva_cpm/composites/crypt.py` (fates store **pre-seeded** `{str(cid): 0}`, `inputs.ligand = ["field_at_cell", str(cid)]`, `outputs.state = ["cell_state", str(cid)]`, bool `inputs.state/neighbor_secretory`, `outputs.fate = ["fates", str(cid)]`).
- Produces: generator `s05_differentiation` at id `viva_genesis.composites.multicellularity_world.s05_differentiation`, with a `fate_mode` knob = `"oxygen" | "none" | "random" | "clamped"` (Task 3 uses the last three); top-level stores exposed for readouts: `fate_counts`, `viable_biomass`, plus `types`/`volumes`.

**Population (ruling S05-D):** a **FIXED** packed patch of N cells (e.g. a 5×5 grid, all type 1) large enough that the center cells go hypoxic — NOT S04's 2×2 clonal seed. **No division** (growth is target-volume increase only) so cell ids stay fixed and the per-cell subcells stay wired. **All real cell types ≥ 1** (never 0 — `fate_counts` skips type 0): undifferentiated/germ = type 1, soma = type 2.

**O₂ field (exact, ruling S05-D):** O₂ is **replenished from the medium** and **consumed by cells per type** — try the declarative medium source `secretion:[{"type":0,"rate":+R_src}]` (medium slot) with per-type consumption `set_secretion(O2, 1, −R_hi)` (germ high consumption) and `set_secretion(O2, 2, −R_lo)` (soma low consumption, so differentiation frees O₂). If medium-type secretion is unsupported by the engine, fall back to a high initial O₂ + per-type consumption so the interior depletes (transient hypoxia, measured in the pinned window). Pre-equilibrate with `world.advance_fields(n)`. Keep `dt*d*2*ndim < 1`. Because consumption is **per cell type** and fate switches the type, differentiation automatically lowers a cell's O₂ draw — no extra wiring.

**Growth (ruling S05-B, owner-sanctioned):** O₂-gated via the Task 1b `o2_gate` mitosis entry — a cell grows (target volume rises) only where its local O₂ ≥ threshold. Soma (type 2) consuming less O₂ raises O₂ for neighbors → more of the group crosses the growth threshold → higher net viable biomass. Performance = `viable_biomass(end) − viable_biomass(start)`.

**Stemness ODE (exact Antimony `STEMNESS_O2_MODEL`, keyed to O₂):**
```
S' = k_on * O2 * (1 - S) - k_off * S ;  S = 1 ;  k_on = 1.0 ; k_off = 1.0
```
driven by `SBMLSubcell(config={"model": STEMNESS_O2_MODEL, "ligand_species": "O2", "state_species": "S", "ligand_scale": <tune>})`. Steady state `S* = k_on·O2/(k_on·O2 + k_off)` — high O₂ → S→1 (stays stem/germ), low O₂ (hypoxic interior) → S→0 (differentiates). Gate reuses `BooleanSubcell` unchanged: `S ≥ stemness_threshold → stay (0)`, else differentiate to the soma type.

- [ ] **Step 1: Write failing tests** `tests/test_s05_differentiation_composite.py`:
  - `test_register_id`: the generator registers at `viva_genesis.composites.multicellularity_world.s05_differentiation`.
  - `test_o2_gradient_forms`: run the real composite a few updates; assert mean O₂ at interior cells < mean O₂ at rim cells (`world.field_mean_at_cell`), i.e. a hypoxic core.
  - `test_interior_differentiates`: after the run, assert `fate_counts` shows ≥2 types present (type 1 germ + type 2 soma) AND the differentiated (soma) cells are spatially interior (lower mean O₂ than the undifferentiated set).
  - `test_oxygen_arm_grows`: `viable_biomass` **increases** over the run (O₂-gated growth is actually wired and firing), and the growth is concentrated in oxygenated cells (the high-O₂ set's volume gain exceeds the hypoxic set's).
  - `test_cell_count_fixed`: cell id count is unchanged across the run (no division — stable ids keep subcells wired; ruling S05-D).
  - `test_fate_stable_last_window`: fate composition (the `fate_counts` map) is unchanged (or within ±1 cell) across the final N updates — no flicker. **If this fails**, add an optional `latch` bool to `BooleanSubcell` in the `s05-metrics` viva-cpm worktree (default False, preserves crypt behavior; when True, a cell that has differentiated never returns to 0) and wire `latch=True` here; fold that viva-cpm change into Task 1's PR (ruling S05-A).
  - `test_default_n_steps`: the composite declares a transient-appropriate `default_n_steps` (pin the run window; runner ignores it, Task 4 re-pins in study params — ruling from S04).
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the `s05_differentiation` generator + O₂/subcell/mitosis helpers (fork crypt's wiring; `fate_mode="oxygen"` path here). Document the transient/quasi-stable-gradient assumption in the docstring.
- [ ] **Step 4: Run tests to verify they pass.**
- [ ] **Step 5: Commit** (`feat(composites): S05 differentiation composite — O2 gradient germ/soma on the shared world`).

---

### Task 3: genesis — the three controls (no-fate, random-fate, clamped-undifferentiated)

**Files:**
- Modify: `viva_genesis/composites/multicellularity_world.py` (the `fate_mode` branches)
- Test: extend `tests/test_s05_differentiation_composite.py`

**Interfaces:**
- Consumes: Task 2's `fate_mode` knob and composite.
- Produces: three control arms on the same composite — `"none"` (no subcells / fate gate disabled → single type, no specialization), `"random"` (fate assigned randomly at **the same differentiated fraction** the `"oxygen"` arm produces under matched conditions, NOT O₂-keyed), `"clamped"` (Intervention `intervention_node(['cell_state', str(cid)], mode='set', value=1.0)` per wired cell → S held above threshold → stays undifferentiated; address `local:Intervention` via `register_intervention(core)` in the composite's `core_extensions`).

- [ ] **Step 1: Write failing tests:**
  - `test_no_fate_single_type`: `fate_mode="none"` → `fate_counts` has exactly one non-medium type for the whole run.
  - `test_random_fate_matches_oxygen_fraction`: `fate_mode="random"` differentiated fraction ≈ the `"oxygen"` arm's differentiated fraction (within tolerance) under matched conditions, but differentiated cells are **not** spatially correlated with low O₂ (controls for the pattern, not the count).
  - `test_clamped_stays_undifferentiated`: `fate_mode="clamped"` → `fate_counts` stays undifferentiated (soma count 0) across the whole run.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the three `fate_mode` branches (register Intervention in `core_extensions`).
- [ ] **Step 4: Run tests to verify they pass.**
- [ ] **Step 5: Commit** (`feat(composites): S05 no-fate / random-fate / clamped-undifferentiated controls`).

---

### Task 4: genesis — out-of-sample scoring + s05 study.yaml + grader

**Files:**
- Modify: `workspace/studies/s05-differentiation/study.yaml`
- Create: `workspace/studies/s05-differentiation/analysis/grade_specialization.py`
- Create: `workspace/studies/s05-differentiation/tests/conftest.py`, `workspace/studies/s05-differentiation/tests/test_specialization_gain.py`

**Interfaces:**
- Consumes: the four arms (oxygen + 3 controls) from Tasks 2–3; `viva_cpm.metrics.fate_counts`/`viable_biomass`; the workbench runner (emits only `readouts[].store_path` stores; `n_steps` pinned in run params — ruling R-T1e/R-T5a from S04).
- Produces: observable `specialization_out_of_sample_gain`; behavior test `specialization-improves-group-performance` graded on the seed-mean.

**Out-of-sample protocol (exact):** two O₂ boundary conditions — **A (calibration)** and **B (held-out)** — differing in O₂ secretion rate / consumption (so the hypoxic core is a different size). The stemness threshold (and any tuned knob) is fixed by a small sweep on **A** only. All four arms are then run on **B** (≥3 seeds each). `specialization_out_of_sample_gain = mean_seed[ viable-growth(oxygen, B) ] - max over controls of mean_seed[ viable-growth(control, B) ]`, where viable-growth = `viable_biomass(end) - viable_biomass(start)`.

> **⚠ Owner-flagged readout (spec §10 #4):** performance metric = **net viable growth (biomass) under O₂-limited growth**, scored out-of-sample on env B. PASS iff gain > 0 AND the oxygen arm beats all three controls on B across the seed-mean. This is the builder's call for the group-performance metric the spec left open (§8); flagged for veto before the grade is treated as final.

- [ ] **Step 1: Write failing study tests** (`data_source: all_runs`): `test_specialization_gain_positive` — seed-mean oxygen-arm viable-growth on B > each control's seed-mean on B; `test_oxygen_beats_random` specifically (isolates spatial pattern from fate-count). Use the `runs` fixture.
- [ ] **Step 2: Run to verify they fail** (no runs yet).
- [ ] **Step 3: Author `study.yaml`** — baseline = `s05_differentiation` (fate_mode oxygen) on env A+B; variants = none/random/clamped on B; `readouts[].store_path` for `fate_counts`/`viable_biomass`; `n_steps` pinned per run; limitations (transient, quasi-static gradient, single backend); behavior test + `specialization_out_of_sample_gain`.
- [ ] **Step 4: Run the sweep + arms locally** (ruling R-T5a: 4 arms × ≥3 seeds × {A,B} = small 2D runs, minutes, on the laptop) via `vivarium-workbench run study s05-differentiation` + `outcomes.sync`. Then `grade_specialization.py` computes the seed-mean gain and sets the PASS/FAIL honestly (clear any stale computed_outcomes).
- [ ] **Step 5: Run the study tests to verify they pass** against the real runs.db. If differentiated does NOT beat the controls out-of-sample, record it as an HONEST OPEN QUESTION / unmet criterion (do not tune to force a pass).
- [ ] **Step 6: Commit** (`feat(s05): out-of-sample specialization grading on the spatial differentiation composite`).

---

### Task 5: genesis — visualization (spatial germ/soma + performance gain)

**Files:**
- Create: `viva_genesis/visualizations/viz_s05_differentiation.py`
- Create: `workspace/studies/s05-differentiation/viz/germ-soma.html` (real pre-render)

**Interfaces:**
- Consumes: the real `s05_differentiation` composite + `viva_cpm.metrics` (`heterotypic_boundary`, `radial_cell_counts`, `fate_counts`); the study runs.
- Produces: a `DifferentiationViz` that (a) runs the real composite and colors cells by fate over the O₂ field (germ/soma pattern along the gradient), asserting the frame's differentiated count matches emitted `fate_counts`; (b) a performance-gain panel (oxygen vs 3 controls on env B). Warn loudly before any fallback (no fabricated previews).

- [ ] **Step 1: Implement `DifferentiationViz`** (real composite, assert frame↔emitted consistency).
- [ ] **Step 2: Render** `germ-soma.html` from the real run.
- [ ] **Step 3: Wire it into `study.yaml` `visualizations:`** with `covers: [specialization_out_of_sample_gain]`.
- [ ] **Step 4: Commit** (`viz(s05): germ/soma spatial pattern + out-of-sample performance gain`).

---

### Task 6: genesis — findings, verdict, investigation roll-up + lint/tests green

**Files:**
- Modify: `workspace/studies/s05-differentiation/study.yaml` (findings, claim, verdict, confidence)
- Modify: `workspace/investigations/multicellularity/investigation.yaml` (executive `computed_acceptance` S05 criterion → honest result)

**Interfaces:**
- Consumes: Task 4 grade.
- Produces: an honest S05 verdict (earned by the run, not asserted — §10 #3); the investigation's S05 computed_acceptance criterion updated to `passing`/`failing` per the real grade.

- [ ] **Step 1:** Write `findings` (tiered: observation = O₂ gradient + spatial fate split; mechanism = threshold-crossing differentiation; interpretation = specialization improves/again doesn't out-of-sample), `claim`, `verdict`, `confidence`, `inferential_scope` (transient, quasi-static, single backend, out-of-sample on one held-out env), `falsifiability`, `limitations`.
- [ ] **Step 2:** Update `investigation.yaml` executive `computed_acceptance` S05 criterion to the real result.
- [ ] **Step 3:** Run `scripts/lint-workspace.py` (exit 0) and the full not-slow `pytest` + the s05 study tests; fix any gate.
- [ ] **Step 4: Commit** (`feat(s05): honest differentiation verdict + investigation roll-up`).

---

## Finish (post-plan)

- viva-cpm `s05-metrics`: verify → commit → push → `gh pr create` (feature PR to main, ready-for-review; conventional title). Not merged.
- genesis `multicellularity`: push; the S05 content rides the investigation branch. Open/refresh its PR to main (per the S04 "Option A" precedent the user chose) — not draft, not merged.
- Surface all SDD rulings; delete the SDD workspace; `superpowers:finishing-a-development-branch`.
