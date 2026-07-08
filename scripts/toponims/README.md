# Toponym pipeline (single sheet)

Extracts the place names engraved on the **Vicenç Mut 1683** map of Mallorca,
georeferences them, and matches them against the **NGIB** gazetteer. The map is a
single plate, so the whole island is worked as one sheet (no quadrants).

> **Detection by the mapKurator spotter (Apple MPS); reading + grouping by Claude
> vision.** The spotter finds every word box but is weak at recognition and at
> grouping words into names, so we keep only its boxes and let Claude vision read
> the engraving and group the boxes into toponyms, window by window ("Approach B").
> Detection setup: [`mapkurator/README.md`](mapkurator/README.md).

## The recipe

The full, reproducible step-by-step (GCPs → spotter → windows → vision extraction →
assemble → georeference → NGIB match → review) lives in
**[`mapkurator/SHEET.md`](mapkurator/SHEET.md)**. Tracked outputs are written to
`data/toponims/`; detection intermediates under `data/toponims/mapkurator/` are
regenerable (gitignored).

## Two-axis quality model (`ngib_match.py`)

Each toponym carries two **orthogonal** fields (don't conflate "how sure" with "who
says so" — the TEI `@cert` / `@resp` model):

- **`decision` = confidence** (algorithmic, always recomputed): `confirmat` /
  `probable` / `suggerit` / `posicional` / `sense`. Distance only disambiguates
  homonyms, never discards a unique name. Name scoring uses a rapidfuzz token-sort
  on article-stripped cores, raised by an orthographic fold (1683 Mallorquí →
  modern grafia) and a metaphone pass.
- **`review` = human validation** (persistent): `revisat` / `corregit` /
  `descartat` / `null`. Fed by the curation overlay; re-running the match refreshes
  confidence without destroying the human layer.

## Environment (Nix, reproducible)

One `flake.nix` (pinned `flake.lock`) provides the whole pipeline env — Python
(rapidfuzz, jellyfish, scipy, numpy, scikit-learn, unidecode, shapely, pillow) plus
Node. Enter it with `nix develop`. `ngib-fetch.mjs` (re)downloads the NGIB Mallorca
subset → `data/toponims/ngib/llocs.json`. Text detection is delegated to the sibling
Apple-Silicon port `../mapkurator-mps` (no CUDA). Repo content is in English.
