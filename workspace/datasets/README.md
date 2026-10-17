# Datasets

Provenance-first data registry for the origins-of-life campaign. Every dataset is
stored separately from model code and linked to a DOI + condition vector (see
`../notes/provenance-schema.md` and `../notes/data-acquisition.md`).

## Contents

- **`parameter-registry.yaml`** — quantitative parameters from the Campaign
  dossier §3, each tagged with a provenance class (FIELD / LAB-DIRECT /
  LAB-ANALOG / MODEL / RECONSTRUCTION / HYPOTHESIS) and a `papers.bib` citation
  key. Laboratory values are experimental outcomes, **not** Hadean environmental
  concentrations.
- **`source-databases.yaml`** — external public databases the new studies
  (27-37) draw on (Rhea, ChEBI, PubChem, ORD, EarthChem/PetDB, KIDA/NIST,
  InterRidge/PANGAEA), each with an acquisition mode + the studies it feeds.
  Upstream of the derived atlas below.
- **`prebiotic-reaction-atlas/`** — the new shared, versioned, provenance-tagged
  candidate-reaction network (Study 28; `README.md` + per-record `schema.yaml`).
  **To be built** — see `../references/build-registry.yaml`.

## To acquire / digitize (priority order)

See `../notes/data-acquisition.md`. First targets:

- Field: Lost City fluid chemistry + time series; InterRidge/PANGAEA vent
  database; Hadean ocean reconstructions.
- Laboratory to digitize: Hudson 2020, Altair 2025, Preiner 2020,
  Muchowska 2017/2019, Jordan 2019, Baaske 2007 / Mast & Braun 2010, Dörr 2003.

Attach new datasets via the workbench **Inputs** tab (keeps `workspace.yaml`
`datasets:` cross-references consistent) or `scripts/add-dataset.sh`.
