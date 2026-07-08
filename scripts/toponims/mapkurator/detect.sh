#!/usr/bin/env bash
# Text detection for the single-sheet Mut 1683 map, end to end:
#   pretile (overlap + upscale)  ->  mapkurator-mps spotter (Apple MPS)  ->  merge
#
#   scripts/toponims/mapkurator/detect.sh
#
# Produces data/toponims/mapkurator/detections.json — word polygons in master
# pixel coordinates, the handoff to the rest of the pipeline (b_windows → vision
# reading → assemble → georef → NGIB match).
#
# Detection (module M2) is delegated to the sibling Apple-Silicon port
# ../mapkurator-mps (no CUDA). Only the boxes are used downstream; Claude vision
# re-reads the engraving, so the spotter's rough recognition does not matter.
#
# Tune the tiling per map — every scan is a different world (resolution, lettering
# size, density). Override the MK_* env vars (see pretile.py): MK_PATCH, MK_OVERLAP,
# MK_SCALE, MK_MIN_INK_STD, MK_REGION.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
cd "$ROOT"

MK_MASTER="${MK_MASTER:-data/raw/Insula_Maioricae_Vicentius_Mut_1683_boxes.jpg}"
MPS_FLAKE="${MPS_FLAKE:-../mapkurator-mps}"
WEIGHTS="${MK_WEIGHTS:-$MPS_FLAKE/weights/model_v2_en.pth}"
IN="$ROOT/data/toponims/mapkurator/in"
OUT="$ROOT/data/toponims/mapkurator/out"

echo "[1/3] pretiling $MK_MASTER ..."
MK_MASTER="$MK_MASTER" nix develop --command python3 \
  scripts/toponims/mapkurator/pretile.py

echo "[2/3] spotting tiles with ../mapkurator-mps (MPS) ..."
rm -rf "$OUT"; mkdir -p "$OUT"
nix run "$MPS_FLAKE" -- --input "$IN" --output "$OUT" --weights "$WEIGHTS"

echo "[3/3] merging tile detections -> detections.json ..."
nix develop --command python3 scripts/toponims/mapkurator/merge_detections.py

echo "done: data/toponims/mapkurator/detections.json"
