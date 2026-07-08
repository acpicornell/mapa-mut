#!/usr/bin/env python3
"""Detect the hand-marked blue GCP dots on a quadrant's *-dots.jpg export.

Blue dots mark every identifiable town (interior, immutable) and some coastal
points (in the sea → lower trust). They are uniform ~3400 px blobs. This reads
their centroids in the crop's own pixel space (shared with the -canvas export the
spotter uses) and writes them for the GCP table, plus a downscaled numbered
overlay to eyeball that nothing was missed / no false positive.

  DOTS=data/jpg/SE/despuig-1785-original-SE-dots.jpg \
  OUT=data/toponims/se/dots-detected.json \
  OVERLAY=data/toponims/se/dots-overlay.png \
    nix-shell scripts/toponims/mapkurator/shell.nix --run 'python3 scripts/toponims/mapkurator/detect_dots.py'
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None

DOTS = os.environ["DOTS"]
OUT = os.environ["OUT"]
OVERLAY = os.environ.get("OVERLAY")
AREA_MIN = int(os.environ.get("AREA_MIN", "800"))
AREA_MAX = int(os.environ.get("AREA_MAX", "20000"))

im = Image.open(DOTS).convert("RGB")
W, H = im.size
a = np.asarray(im, dtype=np.int16)
R, G, B = a[..., 0], a[..., 1], a[..., 2]

# Blue-dominant: blue clearly above red and green, and not too dark.
mask = (B > 110) & (B - R > 45) & (B - G > 35)

lbl, n = ndimage.label(mask)
if n == 0:
    raise SystemExit("no blue blobs found — check thresholds")
areas = ndimage.sum(np.ones_like(lbl), lbl, index=np.arange(1, n + 1))
cys, cxs = (np.array(c) for c in zip(*ndimage.center_of_mass(mask, lbl, np.arange(1, n + 1))))

dots = []
for i in range(n):
    ar = int(areas[i])
    if ar < AREA_MIN or ar > AREA_MAX:
        continue
    dots.append({"x": round(float(cxs[i]), 1), "y": round(float(cys[i]), 1), "area": ar})

# Reading order: top→bottom in coarse bands, then left→right.
band = max(1, H // 24)
dots.sort(key=lambda d: (round(d["y"] / band), d["x"]))
for i, d in enumerate(dots, 1):
    d["n"] = i

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump({"dots_src": DOTS, "crop_dims": [W, H], "count": len(dots), "dots": dots}, f, indent=1, ensure_ascii=False)
print(f"✓ {len(dots)} blue dots → {OUT}  (areas {int(areas.min())}..{int(areas.max())})")

if OVERLAY:
    scale = 2000 / W
    small = im.resize((2000, int(H * scale)))
    d = ImageDraw.Draw(small)
    try:
        font = ImageFont.truetype("/run/current-system/sw/share/X11/fonts/DejaVuSans-Bold.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    for dot in dots:
        x, y = dot["x"] * scale, dot["y"] * scale
        d.ellipse([x - 12, y - 12, x + 12, y + 12], outline=(220, 0, 0), width=3)
        d.text((x + 13, y - 12), str(dot["n"]), fill=(200, 0, 0), font=font)
    small.save(OVERLAY)
    print(f"  overlay → {OVERLAY}")
