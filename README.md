# El mapa de Mallorca de Vicenç Mut (1683)

[![Deploy](https://github.com/acpicornell/mapa-mut/actions/workflows/deploy.yml/badge.svg)](https://github.com/acpicornell/mapa-mut/actions/workflows/deploy.yml)

Outreach edition of the *Insula Maioricae*, the map of Mallorca engraved by
**Vicenç Mut** in **1683** (`data/raw/Insula_Maioricae_Vicentius_Mut_1683.jpg`):
its place names are read off the engraving, curated by hand, georeferenced and
matched against the NGIB gazetteer.

**Live site:** <https://mut.corpusbalear.org> — part of
[Corpus Balear](https://corpusbalear.org).

## What's in it

- A filterable/sortable table of the **137** curated toponyms, readings kept in
  their original 1683 spelling.
- **Mapa** — an interactive geographic layer with every toponym.
- **El gravat** — a page on the engraving itself with a deep-zoom viewer.
- The method and statistics. Catalan UI.

## How it was made

Modelled on the [despuig](https://github.com/acpicornell/despuig) project (the
1785 Cardinal Despuig map) but adapted to a **single-sheet** map — Mut's engraving
is one plate, so there are no NW/NE/SE/SW quadrants and the whole island is
georeferenced from one set of control points. It is also a simpler outreach site:
no census, no town vignettes. A mapKurator text spotter finds the word boxes,
vision reading groups them into names, and each toponym is hand-curated in an
internal tool before being baked into the site's data.

## Run locally

```bash
cd web
npm install
npm run dev         # http://localhost:4330  (npm run build → web/dist)
```

The pipeline environment is a pinned Nix flake (`nix develop`). Every npm script,
the deploy and the curation round are in the documentation below.

## Documentation

- [`docs/WEBSITE.md`](docs/WEBSITE.md) — the Astro site: npm scripts, generated
  data, deploy to Cloudflare Workers, self-hosted vendor assets and CSP.
- [`docs/PIPELINE.md`](docs/PIPELINE.md) — input data, the single-sheet toponym
  pipeline and its Nix environment, and the internal curation tool.
- [`docs/vicenc-mut-1683-map.md`](docs/vicenc-mut-1683-map.md) — a cited research
  dossier on Vicenç Mut and the 1683 *Insula Maioricae* (biography, authorship and
  engravers, the *Notarū Explicatio* legend, editions and holdings, and the map's
  place in Balearic cartography). It is the source of the historical text on the
  site's **El gravat** page.
- [`docs/mapkurator-text-spotting.md`](docs/mapkurator-text-spotting.md) — notes on the
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
