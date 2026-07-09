# El mapa de Mallorca de Vicenç Mut (1683)

Outreach project around the *Insula Maioricae* — the map of Mallorca engraved by
**Vicenç Mut** in **1683** (`data/raw/Insula_Maioricae_Vicentius_Mut_1683.jpg`).

**Live site:** <https://mapa-mut.cloudflare-d82.workers.dev>

Modelled on the [despuig](https://github.com/acpicornell/despuig) project (the
1785 Cardinal Despuig map) but adapted to a **single-sheet** map — Mut's engraving
is one plate, so there are no NW/NE/SE/SW quadrants and the whole island is
georeferenced from one set of control points. It is also a simpler outreach site:
no census, no town vignettes.

The repository holds **two applications** — a public website and an internal
curation tool — plus the **data pipeline** that feeds them.

## `web/` — the public website (Astro, static)

The published site: a filterable/sortable table of the **137** curated toponyms,
an interactive **Mapa** (geographic layer + deep-zoom of the engraving), a page on
the engraving itself (**El gravat**), the method, and statistics. Catalan UI;
readings kept in their original 1683 spelling. It is **self-contained**: it only
reads the versioned JSON under `web/src/data/`.

```bash
cd web
npm install
npm run data        # build src/data/*.json from the pipeline output
npm run hero        # homepage hero crop
npm run map         # DZI tiles for the engraving deep-zoom on /mapa (slow; only when the master changes)
npm run dev         # http://localhost:4330
npm run build       # → web/dist  (prebuild runs data + hero)
```

Deploy = **Cloudflare Workers (Static Assets)** (build locally): `npm run deploy`
(= build + `wrangler deploy`, config in `web/wrangler.toml`).

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

## `scripts/toponims/` — the toponym pipeline

The data engine. The whole island is worked as **one sheet**: GCPs from
hand-marked dots → mapKurator spotter (Apple MPS) → Approach-B vision reading →
assemble → single global georeference → NGIB gazetteer match. Quality is recorded
on two orthogonal axes: **confidence** (`decision`) and **human review** (`review`).

Full reproducible recipe: [`scripts/toponims/mapkurator/SHEET.md`](scripts/toponims/mapkurator/SHEET.md).
Detection setup: [`scripts/toponims/mapkurator/README.md`](scripts/toponims/mapkurator/README.md).

**Environment (Nix, reproducible).** One `flake.nix` with a pinned `flake.lock`
provides the whole pipeline env (Python geometry/fuzzy/georef + Node). Enter it
with `nix develop`. Text **detection** is delegated to the sibling Apple-Silicon
port [`../mapkurator-mps`](https://github.com/acpicornell/mapkurator-mps) (no
CUDA); `detect.sh` calls it. All repo content is in English.

## `docs/` — background

- [`vicenc-mut-1683-map.md`](docs/vicenc-mut-1683-map.md) — a cited research
  dossier on Vicenç Mut and the 1683 *Insula Maioricae* (biography, authorship and
  engravers, the *Notarū Explicatio* legend, editions and holdings, and the map's
  place in Balearic cartography). It is the source of the historical text on the
  site's **El gravat** page.
- [`mapkurator-text-spotting.md`](docs/mapkurator-text-spotting.md) — notes on the
  text-spotting detection step.

## License

- **Code** (the pipeline, the `web/` site, all scripts) — **© Antonio Picornell,
  [AGPL-3.0-only](https://www.gnu.org/licenses/agpl-3.0.html)** (see [`LICENSE`](LICENSE)).
  Strong copyleft with a network clause: anyone who uses, modifies, or runs this
  code as a network service must release their complete source under the AGPL too,
  keeping attribution.
- **Toponym data** (`data/toponims/*.json` and the derived `web/src/data/`) —
  **© Antonio Picornell, [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**:
  free to reuse for non-commercial purposes **with attribution**. The attribution
  is also embedded inside the JSON so it travels with a copy. See
  [`data/toponims/LICENSE.md`](data/toponims/LICENSE.md).
- Canonical name forms come from the **NGIB** and keep their own terms; the
  vendored web libraries/fonts keep theirs (see `web/public/vendor/`).

## Input data (`data/raw/`, hand-prepared in GIMP)

- `Insula_Maioricae_Vicentius_Mut_1683.jpg` — the clean engraving.
- `..._dots.jpg` — blue dots hand-marked on identifiable towns/capes → GCP source.
- `..._boxes.jpg` — the same canvas with the sea/margins masked red and the dots
  hidden → the input the spotter runs on (masking keeps sea noise out).
- `..._1683.xcf` — the GIMP master with the layers.
