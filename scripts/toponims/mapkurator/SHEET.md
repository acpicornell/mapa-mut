# Single-sheet extraction & georeference recipe (Mut 1683)

The Mut map is a **single plate**, so — unlike despuig's 4 quadrants — the whole
island is worked as one sheet and georeferenced from one set of control points.
All data lives directly under `data/toponims/` (no `<q>` subdirectory). Run
everything inside the pinned Nix shell: `nix develop --command <cmd>`.

## Inputs (hand-prepared in GIMP, in `data/raw/`)

- `Insula_Maioricae_Vicentius_Mut_1683.jpg` — the clean engraving (3840×2849).
- `..._dots.jpg` — blue dots on identifiable towns/capes → GCP source.
- `..._boxes.jpg` — same canvas, sea/margins masked red, dots hidden → spotter input.

## Step 0 — GCPs from the blue dots

```bash
DOTS=data/raw/Insula_Maioricae_Vicentius_Mut_1683_dots.jpg \
OUT=data/toponims/dots-detected.json OVERLAY=data/toponims/dots-overlay.png \
AREA_MIN=100 nix develop --command python3 scripts/toponims/mapkurator/detect_dots.py
nix develop --command python3 scripts/toponims/mapkurator/crop_dots.py   # gcp-crops/dotNN.jpg
```

Read the town/cape beside each dot from `gcp-crops/dotNN.jpg` and record it in the
`DOT_TOWN` table of `build_gcps.py`; it resolves each to NGIB coordinates:

```bash
nix develop --command python3 scripts/toponims/mapkurator/build_gcps.py   # -> gcps.json
```

Mut: **19 dots** → 12 interior municipality seats + 7 coastal capes.

## Step 1 — spotter detection

```bash
scripts/toponims/mapkurator/detect.sh          # -> data/toponims/mapkurator/detections.json
```

(pretile with overlap + ×2 upscale → `../mapkurator-mps` spotter on Apple MPS →
merge; see [`README.md`](README.md)). Mut: ~300 word polygons.

## Step 2 — window → vision read → assemble

```bash
B_DET=data/toponims/mapkurator/detections.json \
B_MASTER=data/raw/Insula_Maioricae_Vicentius_Mut_1683.jpg \
B_OUTDIR=data/toponims/mapkurator/b \
  nix develop --command python3 scripts/toponims/mapkurator/b_windows.py 0 0 3840 2849
nix develop --command python3 scripts/toponims/mapkurator/split_windows.py data/toponims/mapkurator/b
```

Then one Claude-vision agent per window (`w##.png` + `w##.json`) groups the spotter
boxes into toponyms and reads them **diplomatically** (period spelling: Sô/Câ kept).
Save the combined `{windows:[{w,toponims:[{boxes,reading}]}]}` to
`data/toponims/mapkurator/b/extract.json`, then:

```bash
B_WINDIR=data/toponims/mapkurator/b TOPONIMS_JSON=data/toponims/toponims.json \
  nix develop --command python3 scripts/toponims/mapkurator/b_assemble.py \
    data/toponims/mapkurator/b/extract.json          # -> toponims.json
```

Mut: 6 windows → **137 toponyms**. The map's coastal names are only mildly tilted
and few windows cover them, so a single (interior) track is enough — no separate
deskewed coastal track is needed here.

## Step 3 — georeference (single global fit)

```bash
GCPS_NW=data/toponims/gcps.json TOPONIMS_JSON=data/toponims/toponims.json \
  nix develop --command python3 scripts/toponims/mapkurator/georef_sheet.py
```

Fits the mapKurator family (affine / poly2 / tps) and picks by leave-one-out on the
control points. **Mut is essentially an affine picture of reality** (LOO median
≈ 1972 m; poly2/tps overfit the ~2 km per-point noise of a schematic 1683 map), so
`affine` is chosen on the 12 interior dots. Writes lon/lat into every toponym.

## Step 4 — NGIB match + bake

```bash
nix develop --command python3 scripts/toponims/mapkurator/bake.py    # overlay + ngib_match
nix develop --command python3 scripts/toponims/mapkurator/quality_audit.py   # -> quality_flags.json
```

`bake.py` is the single entry point run after each curation round: it applies the
hand overlay `data/toponims/curation.json` and re-runs the NGIB match. Two
orthogonal axes: `decision` (confidence, always recomputed) and `review` (human
validation, persistent). Mut first automated pass: confirmat 56 / suggerit 51 /
sense 26 / probable 2 / posicional 2.

## Outputs (tracked)

`data/toponims/`: `dots-detected.json`, `gcps.json`, `toponims.json`,
`matches.json`, `recheck.json`, `gcps-used.json`, `curation.json` (hand edits),
`quality_flags.json`. Detection intermediates under `data/toponims/mapkurator/`
are gitignored (regenerable via `detect.sh` + `b_windows.py`).
