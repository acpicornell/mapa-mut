#!/usr/bin/env python3
"""Native-resolution crops around each detected GCP dot, to read the engraved
town name beside it (a small native crop stays legible). Single-sheet map, so no
quadrant: paths come from env vars.

  DOTS=data/raw/Insula_Maioricae_Vicentius_Mut_1683_dots.jpg \
  DET=data/toponims/dots-detected.json \
  OUTDIR=data/toponims/gcp-crops \
    nix develop --command python3 scripts/toponims/mapkurator/crop_dots.py
"""
import json
import os

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

DOTS = os.environ.get("DOTS", "data/raw/Insula_Maioricae_Vicentius_Mut_1683_dots.jpg")
DET = os.environ.get("DET", "data/toponims/dots-detected.json")
OUTDIR = os.environ.get("OUTDIR", "data/toponims/gcp-crops")
CW = int(os.environ.get("CW", "560"))
CH = int(os.environ.get("CH", "420"))

det = json.load(open(DET))
im = Image.open(DOTS).convert("RGB")
W, H = im.size
os.makedirs(OUTDIR, exist_ok=True)
for d in det["dots"]:
    x, y = d["x"], d["y"]
    l = int(max(0, min(W - CW, x - CW / 2)))
    t = int(max(0, min(H - CH, y - CH / 2)))
    im.crop((l, t, l + CW, t + CH)).save(f'{OUTDIR}/dot{d["n"]:02d}.jpg', quality=90)
print(f'{len(det["dots"])} crops -> {OUTDIR}')
