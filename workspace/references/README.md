# References

- `papers.bib` — BibTeX bibliography
- `claims.yaml` — claim ID → BibTeX key mapping (drives report citations)
- `computational-resources.md` — engines, databases, standards catalog (incl. the upgrade-plan stack for studies 27-37)
- `build-registry.yaml` — tools + datasets **to be built** (per-tool `build_status` + `audit_status`); the planned-build surface the workspace registry/`/viva-catalog` can't express
- `notes/` — per-paper markdown summaries (one file per BibTeX key)
- `expert/` — curated expert documents (PDFs, lab notes, expert review docs) registered via `workspace.yaml.expert_docs`. Add via the dashboard "Expert knowledge" panel or `POST /api/expert-doc`.

See also `../datasets/source-databases.yaml` (external DB sources) and
`../datasets/prebiotic-reaction-atlas/` (new shared data asset, Study 28), and
`../notes/audit-build-capability-gaps.md` (where audit/build capabilities are missing).
