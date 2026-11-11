# Toponym pipeline and curation tool

How the toponym data behind the website is produced and hand-curated. Moved here
from the top-level README.

The repository holds **two applications** — a public website (see
[`WEBSITE.md`](WEBSITE.md)) and an internal curation tool — plus the **data
pipeline** that feeds them.

## Input data (`data/raw/`, hand-prepared in GIMP)

- `Insula_Maioricae_Vicentius_Mut_1683.jpg` — the clean engraving.
- `..._dots.jpg` — blue dots hand-marked on identifiable towns/capes → GCP source.
- `..._boxes.jpg` — the same canvas with the sea/margins masked red and the dots
  hidden → the input the spotter runs on (masking keeps sea noise out).
- `..._1683.xcf` — the GIMP master with the layers.

## `scripts/toponims/` — the toponym pipeline

The data engine. The whole island is worked as **one sheet**: GCPs from
hand-marked dots → mapKurator spotter (Apple MPS) → Approach-B vision reading →
assemble → single global georeference → NGIB gazetteer match. Quality is recorded
on two orthogonal axes: **confidence** (`decision`) and **human review** (`review`).

Full reproducible recipe: [`scripts/toponims/mapkurator/SHEET.md`](../scripts/toponims/mapkurator/SHEET.md).
Detection setup: [`scripts/toponims/mapkurator/README.md`](../scripts/toponims/mapkurator/README.md).
Pipeline overview: [`scripts/toponims/README.md`](../scripts/toponims/README.md).

**Environment (Nix, reproducible).** One `flake.nix` with a pinned `flake.lock`
provides the whole pipeline env (Python geometry/fuzzy/georef + Node). Enter it
with `nix develop`. Text **detection** is delegated to the sibling Apple-Silicon
port [`../mapkurator-mps`](https://github.com/acpicornell/mapkurator-mps) (no
CUDA); `detect.sh` calls it. All repo content is in English.

## `scripts/toponims/review-server.mjs` — the curation tool (internal)

A local, single-file web app to hand-curate the toponyms. It is **not part of the
deployed website**. Three views over the same data: **Taula** (editable grid),
**Fitxes** (one toponym at a time with the engraving crop, NGIB candidates and a
map), and **Mapa** (all toponyms on a geographic layer, coloured by confidence).
All hand edits persist to a single `data/toponims/curation.json` overlay.

```bash
nix develop --command node scripts/toponims/review-server.mjs   # http://localhost:4400
```

After a curation round, **bake** and rebuild the website data:

```bash
nix develop --command python3 scripts/toponims/mapkurator/bake.py
cd web && npm run data
```
