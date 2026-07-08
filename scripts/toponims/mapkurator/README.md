# mapKurator spotter — text detection (Apple MPS)

Detect-then-read text spotting for the toponym pipeline (see
[`docs/mapkurator-text-spotting.md`](../../../docs/mapkurator-text-spotting.md)
for the *why*). This folder is the **detection** side: run the mapKurator
spotter-v2 to get whole-word polygons over the map. Recognition (Claude vision)
comes after — we keep only the boxes.

Unlike despuig (which built a CUDA Docker image), detection here is delegated to
the sibling Apple-Silicon port **[`../mapkurator-mps`](https://github.com/acpicornell/mapkurator-mps)**:
the spotter runs natively on the Apple GPU (Metal/MPS), no CUDA, packaged as a
reproducible Nix flake. This project just calls it.

## Run it

```bash
# one command: pretile (overlap + upscale) -> spotter (MPS) -> merge
scripts/toponims/mapkurator/detect.sh
# -> data/toponims/mapkurator/detections.json
```

`detect.sh` chains three steps:

1. **`pretile.py`** — cut the masked canvas (`data/raw/..._boxes.jpg`) into
   overlapping patches, upscaled ×2 and sharpened so the small engraved lettering
   is at a scale the spotter reads well. Blank (all-sea) patches are skipped.
   Tune per map with `MK_PATCH` / `MK_OVERLAP` / `MK_SCALE` / `MK_MIN_INK_STD` —
   every scan is a different world.
2. **`../mapkurator-mps`** (tile-directory mode) — spot each patch → one JSON per
   patch (`polygon_x`, `polygon_y`, `text`, `score`).
3. **`merge_detections.py`** — shift each patch's polygons back into master pixel
   coordinates and dedup the same word seen in overlapping patches (shapely IoU)
   → `detections.json` (the handoff to `b_windows.py`).

The weights (`model_v2_en.pth`) are the sibling repo's — point at them with
`MK_WEIGHTS` (default `../mapkurator-mps/weights/model_v2_en.pth`). Fetch them
there with `nix develop --command scripts/get-weights.sh`.

**Judge Phase 0:** does it draw boxes around whole words on this 1683 engraving
(not the possession-marker symbols, not noise)? On the Mut scan (3840×2849) it
does — ~300 word polygons at median score 0.93. The spotter's own *text* is rough
on this historical font; that is fine, only the boxes are used downstream.

## Files

- `detect.sh` — orchestrate pretile → spotter → merge.
- `pretile.py` — slice the masked canvas into overlapping, upscaled patches.
- `merge_detections.py` — map patch polygons back to master pixels, de-overlap →
  `detections.json`.

## Paths (all under data/toponims/mapkurator/, gitignored, regenerable)

- `in/` — input patches for detection.
- `out/` — per-patch JSON (`polygon_x`/`polygon_y`/`text`/`score`).
- `patches.json` — patch manifest (offsets + scale) for the merge.
- `detections.json` — merged word polygons in master pixel space.
