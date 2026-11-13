# S06 Evolutionary Individuality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the S06 "evolutionary individuality" study on the real viva-cpm substrate — many clonal founder groups whose heritable adhesion set-point is selected at the GROUP level across a discrete generational life cycle — and let the spatial run earn an honest verdict on whether stable, heritable among-group fitness variance emerges and whether it collapses under non-clonal (mixed-founder) seeding.

**Architecture:** Founder identity = cell type (division preserves type, so lineage propagates through mitosis with no Rust change). The heritable group trait = adhesion ∈ [0,1] → homotypic contact energy via the EXISTING `homotypic_j` mapping (reuses S04 verbatim). A new `GroupSelectionProcess` (viva_genesis) is the real `cell ↔ population` feedback loop: each process update = one group-generation (seed N founders on a fresh CPM lattice → grow+divide for the 40-update transient window at mcs_per_update=16 → score each group by `largest_cluster_fraction` toughness → Price-partition selection into among-group and within-group components → select top groups and reseed next-generation founders with inherited + mutated adhesion). The study grades the Price partition, trait heritability across the life cycle, and the multi-generation response to selection; the mixed-founder arm is the adversarial control.

**Tech Stack:** Python 3.12, viva_cpm (Rust CPM via the existing `.so`, imported as a library), process-bigraph composites, numpy, the vivarium-workbench study runner + grader, pytest behavior tests.

**Spec:** `docs/superpowers/specs/2026-11-12-multicellularity-multiscale-design.md` §7.4 (S06), §10.2 (owner call: ecological-scaffolding frame), §11 (reset-to-unproven), plus the owner's 2026-11-12 decision that the heritable group trait = **adhesion set-point** (reuses S04).

## Global Constraints

- **No viva-cpm change.** S06 is viva_genesis-only content on the `multicellularity` branch. Founder=type + the existing bindings (`add_cell`, `set_contact`, `divide_cells`, `grow`, `step`, `snapshot`, `cell_types`, `cell_volumes`, `largest_cluster_fraction`, `aggregate_components`) cover it. The Price-partition is study analysis, not a substrate primitive. *(Ruling — recorded in the ledger.)*
- **Provided-mechanisms-only honesty.** The ONLY sanctioned S06 mechanism is group-level selection on the adhesion set-point. Do NOT add any term, cap, or parameter to force "individuality evolves" or "mixed collapses." Report whatever the run gives. If stability or collapse is partial, say so (the spike already shows mixed-founder response attenuates to ~54%, NOT to zero — report that honestly).
- **Reuse S04 verbatim where it exists:** `homotypic_j`, `J_MEDIUM`, `J_MIN/J_MAX`, the 2×2 gapped seed blocks, `grow_rate=2.0`, `divide_threshold=55.0`, `seed_volume=30.0`, `lambda_volume=2.0`, `lambda_surface=0.2`, `temperature=8.0`, **`mcs_per_update=16`**, **window=40 updates**. These reproduce S04's proven fracture (adhesion 0→lcf 0.19, 0.3→0.57, ≥0.5→1.0) — verified in the de-risk spike.
- **Spike-validated parameters:** per-founder space `region=60` sites (grid = cols*region+8); start adhesions varied in [0.0, 0.6]; mutation_sd=0.08; selection keeps the top 50% by toughness, each winner reseeds 2 offspring founders; ≥5 generations.
- **No AI attribution** in any commit or PR (overrides base guidance). Squash-merge to main; never auto-merge.
- **Reset-to-unproven:** S06 starts `status: investigating` / `simulation_status: not_run` with no asserted verdict; the spatial run earns it.

## Review Focus

- **Fitness-variance saturation.** If per-founder toughness saturates near 1.0 (too much space, or adhesions already high), selection has nothing to act on and the response is drift. Task 2's generation builder MUST reproduce real variance (adhesion 0 → lcf ≈ 0.19 at region=60, mcs=16); a behavior test pins adhesion-0 toughness < 0.4 and adhesion-0.5 toughness = 1.0.
- **Lineage leakage through division.** A daughter must keep its founder's type (and thus adhesion). Test: after a window with division, every cell's type is one of the seeded founder/cheater types — no stray types, and `n_cells` grew (division happened).
- **Price partition sign/identity.** among_group + within_group must sum to the realized Δ(mean adhesion) per generation (Price identity) within numerical tolerance. Test this exactly.
- **Mixed-founder within-group term.** In the mixed arm the within-group component must be ≤ 0 (cheaters erode group adhesion); in the pure clonal arm it must be ≈ 0 (no within-group adhesion variance). Test both.
- **Selection-off drift null.** With selection disabled, the multi-generation response d(mean adhesion) must be ≈ 0 (no directional trend) — the null that proves the clonal response is selection, not reseeding artifact.

---

### Task 1: Group-partition analysis helper (Price inputs)

**Files:**
- Modify: `viva_genesis/composites/multicellularity_world.py` (add `group_partition`)
- Test: `tests/test_s06_group_partition.py`

**Interfaces:**
- Consumes: `viva_cpm.metrics.largest_cluster_fraction`, `world.snapshot()`, `world.cell_types()`, `world.cell_volumes()`.
- Produces: `group_partition(world, founder_types: list[int]) -> dict` returning, per founder type f: `{"toughness": largest_cluster_fraction(world,[f]), "n_cells": <count>, "volume": <sum>}`; and a top-level `by_cell_type` map used by the Price partition. Pure function, no mutation.

- [ ] **Step 1: Write the failing test** — build a small 2-founder world (types 1,2) with distinct adhesions, run a few updates with division, assert `group_partition` returns a per-founder dict whose `toughness` matches `largest_cluster_fraction(world,[f])` and whose `n_cells` sums to the non-medium cell count.
- [ ] **Step 2: Run it, verify it fails** (`group_partition` undefined).
- [ ] **Step 3: Implement `group_partition`** in `multicellularity_world.py` over the existing metrics/bindings.
- [ ] **Step 4: Run test, verify pass.**
- [ ] **Step 5: Commit** `feat(s06): group_partition helper for Price-equation inputs`.

### Task 2: GroupSelectionProcess — the generational cell↔population loop

**Files:**
- Create: `viva_genesis/s06_process.py`
- Test: `tests/test_s06_process.py`

**Interfaces:**
- Consumes: `viva_cpm.schema.load_world`, `homotypic_j`, `J_MEDIUM`, `group_partition` (Task 1).
- Produces: `GroupSelectionProcess(Process)` with config `{n_founders=6, generations, window=40, mcs_per_update=16, grow_rate=2.0, divide_threshold=55.0, seed_volume=30.0, region=60, mutation_sd=0.08, selection=True, clonality="clonal"|"mixed", cheater_adhesion=0.0, selection_fraction=0.5, init_adhesion=[lo,hi], seed}`. One `update()` advances ONE generation and emits: `generation`, `mean_adhesion`, `among_group`, `within_group`, `delta_adhesion` (= among+within, the Price identity), `mean_toughness`, `heritability` (slope of offspring-group adhesion on parent-group adhesion). Internal state carries the current founders' adhesions across generations.

Mechanism (exact, spike-validated): seed each founder as S04's 2×2 gapped blocks of a distinct type with `set_contact(f,f)=homotypic_j(adh_f)`, `set_contact(0,f)=J_MEDIUM`; mixed arm replaces 2 of the 4 sub-blocks with a shared cheater type at `homotypic_j(cheater_adhesion)`. Per window update: `grow` every live type by grow_rate, `step(mcs_per_update)`, `divide_cells(divide_threshold, seed_volume)`. Group fitness `w_k` = founder toughness. Price: `among_group = Cov_k(w_k, z_k)/w̄` with `z_k` = group mean adhesion at generation start; `within_group = E_k(w_k·Δz_k)/w̄` with `Δz_k` = (group mean adhesion at window end − at start, computed from the per-cell-type adhesion map weighted by cell count). Selection: keep top `selection_fraction` by `w_k`; each winner seeds 2 offspring founders at `clip(adh_winner + N(0,mutation_sd), 0, 1)`; `selection=False` reseeds the same founders in random order (drift null).

- [ ] **Step 1: Write failing tests** — (a) one generation emits all keys; (b) `among_group + within_group == delta_adhesion` within 1e-6 (Price identity); (c) clonal arm: `within_group ≈ 0` (|·|<0.02); (d) division happened (`n_cells` final > seeded); (e) every final cell type ∈ seeded types (no lineage leak).
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement `GroupSelectionProcess`.**
- [ ] **Step 4: Run tests, verify pass.**
- [ ] **Step 5: Commit** `feat(s06): GroupSelectionProcess generational cell<->population loop`.

### Task 3: s06_individuality composite + arms

**Files:**
- Modify: `viva_genesis/composites/multicellularity_world.py` (add `s06_individuality` generator + `_S06_EMIT_PATHS`)
- Test: `tests/test_s06_individuality_composite.py`

**Interfaces:**
- Consumes: `GroupSelectionProcess` (Task 2).
- Produces: `@composite_generator` `s06_individuality(core=None, *, clonality="clonal", selection=True, generations=6, seed=1)` registered as `viva_genesis.composites.multicellularity_world.s06_individuality`, `default_n_steps = generations`. Emits the process outputs to top-level stores. Four arms selectable by `(clonality, selection)`.

- [ ] **Step 1: Write failing tests** — generator registers; `default_n_steps==generations`; a short clonal+selection run raises mean_adhesion from gen 0 to last (response > 0); a selection-off run shows |response| small (drift); adhesion-0 toughness < 0.4 and adhesion-0.5 toughness == 1.0 (fitness-variance guard, via a direct one-generation probe).
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement the generator + emit wiring.**
- [ ] **Step 4: Run tests, verify pass.**
- [ ] **Step 5: Commit** `feat(s06): s06_individuality composite with clonal/mixed x selection arms`.

### Task 4: S06 study + grader + out-of-sample

**Files:**
- Create: `workspace/studies/s06-individuality/study.yaml`
- Create: `workspace/studies/s06-individuality/analysis/grade_individuality.py`
- Test: `tests/test_s06_individuality_study.py`

**Interfaces:**
- Consumes: the registered `s06_individuality` composite.
- Produces: arms = {clonal, mixed} × {selection-on, selection-off} × seeds (≥3), n_steps = generations. Grader computes, per arm: multi-generation response d(mean_adhesion), mean among-group vs within-group Price components, realized heritability, and an OUT-OF-SAMPLE check (evolved adhesion's toughness measured on held-out potts seeds not used during evolution). Verdict markers (`verdict`, `confidence`, `evidence_tier=mechanistic_prediction`, `evaluation_status`, `gate_status`) set by the actual graded result (Task 6 finalizes).

- [ ] **Step 1: Write failing test** — study.yaml parses; declares the 4 arm families + ≥3 seeds; grader importable and returns the per-arm metrics dict on a fixture run.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Author study.yaml (rigor fields: controls incl. selection-off null + mixed adversarial; alternative_hypotheses; tiered findings; falsifiability; limitations) + grader.**
- [ ] **Step 4: Run the study (workbench runner, ≥3 seeds), record `runs[].outcomes`, run the grader, run the test.**
- [ ] **Step 5: Commit** `feat(s06): out-of-sample individuality grading on the generational composite`.

### Task 5: S06 visualization

**Files:**
- Create: `viva_genesis/visualizations/viz_s06_individuality.py`
- Create: `workspace/studies/s06-individuality/viz/individuality.html`
- Test: assertion inside the viz (frame data == emitted outcomes)

**Interfaces:**
- Consumes: the study's emitted outcomes (among_group, within_group, mean_adhesion, mean_toughness per generation, per arm).
- Produces: `IndividualityViz` — (1) among-group vs within-group selection over generations (stacked/opposed bars), (2) mean-adhesion trajectories clonal vs mixed vs selection-off, (3) toughness (group-fitness) gain. Must render from REAL run data; assert a frame value equals an emitted outcome.

- [ ] **Step 1: Write the viz with a built-in data-consistency assertion.**
- [ ] **Step 2: Render against the Task-4 run; verify it matches.**
- [ ] **Step 3: Commit** `viz(s06): among/within-group selection + adhesion trajectories`.

### Task 6: Honest verdict + investigation roll-up

**Files:**
- Modify: `workspace/studies/s06-individuality/study.yaml` (final verdict/claim/confidence from the run)
- Modify: `workspace/investigations/multicellularity/investigation.yaml` (S06 acceptance criterion → actual state; update `computed_acceptance`)
- Test: `tests/test_studies_have_markers.py` (must stay green), `tests/test_workspace_integrity.py`

- [ ] **Step 1: Set the study's verdict from the graded result** (supported/qualified/mixed per the honest outcome — the spike suggests clonal individuality evolves decisively while mixed attenuates, which maps to `supported` with a documented caveat or `qualified`; the RUN decides, not this plan).
- [ ] **Step 2: Update investigation.yaml** S06 criterion to its earned state; refresh `computed_acceptance`.
- [ ] **Step 3: Run the marker + integrity tests, verify green.**
- [ ] **Step 4: Commit** `feat(s06): honest evolutionary-individuality verdict + investigation roll-up`.

---

## Self-Review

- **Spec coverage:** §7.4 mechanism (clonal groups, group-level selection, heritable trait, fracture-reuse) → Tasks 2–4; Price partition + heritability readout → Tasks 2,4; mixed-founder adversarial control → Tasks 2–4; generational reseed loop as a real cell↔population process → Task 2; ecological-scaffolding frame → study framing Task 4; reset-to-unproven → Global Constraints + Task 6. Covered.
- **Review Focus:** fitness-variance saturation (Task 3 guard test), lineage leak (Task 2 test), Price identity (Task 2 test), mixed within-group sign (Task 2/4), selection-off null (Task 3/4). Each pinned to an owning task's test.
- **Proportion:** one new file + edits to the shared world module; parameters are S04's, reused not re-derived. Plan carries decisions (Price formulas, arm matrix, spike-validated params), not transcribed bodies.
