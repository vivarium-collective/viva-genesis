# PROTOTYPE — og-00 under the collapsed narrative schema (DO NOT MERGE as-is)

This branch rewrites `og-00-vent-reactor-baseline/study.yaml` to the single-source
schema from the field-redundancy review. **It is illustrative**: the live
study-detail (SD) and exported single-study report (SSR) still read the removed
fields, so the paired **workbench render-diff below must land first** or SSR shows
blanks. Kept on its own branch so the before→after `study.yaml` diff is exact.

## What changed in og-00 (authored narrative)

Removed (derived or single-sourced instead):
- `result` prose → the numbers live once in top-level `key_metrics`; the Result
  section renders that table.
- the entire `report:` block — `title` → top-level `title`; `verdict` → computed
  from `gate_status` + `claim`; `confidence` → top-level `confidence`;
  `main_insight` → `claim`; `conclusion` → `claim`; `caveat` → `limitations[0]`;
  `key_metrics` → promoted to top-level.
- top-level `conclusion` → folded into `claim` (the testbed / no-OoL clause).
- `discovery_implications.resolved_uncertainties` → it restated `findings[]`; the
  Discovery tab renders the findings instead.

Kept (the only authored prose): `title`, `question`, `objective`, `claim` (the one
headline), `findings[]`, `conclusion_verdicts` (result only), `limitations[]`,
`discovery_implications.{remaining_uncertainties, followup_study_proposals}`,
`readouts[]`, `behavior_tests[]`; plus `key_metrics` as data.

Effect: authored narrative fields ~13 → ~6; every number sourced once (the fix
that would have prevented the og-02 "~3 vs 29.5" / og-03 "1e6–1e7 vs 9.6e7"
drift). No view loses content — each slot maps to a kept field (see below).

## Workbench render-diff (must land with a schema migration of all studies)

### `vivarium_workbench/lib/single_study_report.py` (SSR) — the bulk of the change
SSR is the only renderer that reads the `report.*` block; repoint it at the
top-level/computed fields SD already uses:

| SSR today (file:line) | read instead |
|---|---|
| `report.title` (2141, 2405, 2455) | `study["title"]` |
| `report.verdict` (2142, 2152) | computed verdict (`gate_status` + `claim`), as SD's header pill |
| `report.confidence` (2143, 2203–2204) | `study["confidence"]` |
| `report.main_insight` (2147, 2228–2232) | `study["claim"]` |
| `report.conclusion` (2146, 2222–2227) | `study["claim"]` (drop the separate Conclusion block) |
| `report.caveat` (2148, 2234–2239) | `study["limitations"][0]` |
| `report.result` (370) and `report.key_metrics` (2150, 2155, 323) | top-level `key_metrics` |

### `vivarium_workbench/templates/study-detail.html` (SD) — two small changes
- Result block (`768`): render the `key_metrics` table (769–776) as the Result;
  stop reading top-level `result` / `report.main_insight`.
- Discovery tab (`2150–2153`): render `findings[]` where it now reads
  `resolved_uncertainties`.
- Unchanged (SD already single-sources these): Caveat ← `limitations[0]` (878);
  Confidence ← `study.confidence` (872); verdict pill ← computed.

### Migration
One-time: apply the same field collapse to the other 16 studies. A script can do
it mechanically (promote `report.key_metrics`→`key_metrics`, drop the rest of
`report`, drop `result`/top-level `conclusion`/`resolved_uncertainties`), since the
kept fields already exist in every study.

## Not mergeable until the render-diff lands
If this `study.yaml` merged alone, SSR's Main-insight/Conclusion/Caveat/verdict/
confidence/title blocks would render empty. Land the workbench change + migration
together, or treat this branch purely as the design reference.
