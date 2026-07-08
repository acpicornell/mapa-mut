#!/usr/bin/env python3
"""Phase 1 tiler for the mapKurator spotter: cut the masked map canvas into
overlapping patches. Overlap lets a word cut at one patch edge stay whole in a
neighbour; merge_detections.py dedups by polygon IoU afterwards.

    MK_MASTER=data/raw/..._boxes.jpg \
      nix develop --command python3 scripts/toponims/mapkurator/pretile.py

Writes patch JPEGs to data/toponims/mapkurator/in/ and a manifest with each
patch's master offset (gx,gy) + scale to data/toponims/mapkurator/patches.json.

Sizing note: this map is a single sheet (~3840 px wide). Each patch is upscaled
×SCALE and sharpened so the spotter sees the small engraved lettering at a scale
it reads well. Tune PATCH / OVERLAP / SCALE per map with the MK_* env vars — every
scan is a different world (resolution, lettering size, density).
"""
import json
import os

from PIL import Image, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(ROOT, "data/toponims/mapkurator")

MASTER_REL = os.environ.get("MK_MASTER")
if not MASTER_REL:
    raise SystemExit(
        "Set MK_MASTER to the masked sheet canvas, e.g. "
        "MK_MASTER=data/raw/Insula_Maioricae_Vicentius_Mut_1683_boxes.jpg")
MASTER = os.path.join(ROOT, MASTER_REL)
IN = os.path.join(BASE, os.environ.get("MK_INDIR", "in"))
PATCHES = os.path.join(BASE, os.environ.get("MK_PATCHES", "patches.json"))

PATCH = int(os.environ.get("MK_PATCH", "1100"))       # master px per patch
OVERLAP = float(os.environ.get("MK_OVERLAP", "0.28"))  # fraction → boundary words survive
SCALE = int(os.environ.get("MK_SCALE", "2"))           # upscale + sharpen
# Skip patches that carry almost no ink (fully sea/masked): saves compute. The
# empty-tile spotter crash is fixed upstream, so this is an optimisation only.
MIN_INK_STD = float(os.environ.get("MK_MIN_INK_STD", "3.0"))

stride = round(PATCH * (1 - OVERLAP))

Image.MAX_IMAGE_PIXELS = None
master = Image.open(MASTER).convert("RGB")
MW, MH = master.size
print(f">> master {MW}x{MH}  patch={PATCH} overlap={OVERLAP} scale={SCALE} stride={stride}")


def pick_region():
    r = os.environ.get("MK_REGION", "FULL")
    if r == "FULL":
        return 0, 0, MW, MH
    x, y, w, h = (int(v) for v in r.split(","))
    return x, y, w, h


X, Y, W, H = pick_region()


def patch_origins():
    last_x, last_y = X + W - PATCH, Y + H - PATCH
    xs, ys = [], []
    x = X
    while x < last_x:
        xs.append(x)
        x += stride
    xs.append(last_x)
    y = Y
    while y < last_y:
        ys.append(y)
        y += stride
    ys.append(last_y)
    out = []
    for r, gy in enumerate(ys):
        for c, gx in enumerate(xs):
            left = max(0, round(gx))
            top = max(0, round(gy))
            w = min(PATCH, X + W - left)
            h = min(PATCH, Y + H - top)
            out.append({"id": f"p{r:02d}_{c:02d}", "row": r, "col": c,
                        "gx": left, "gy": top, "w": w, "h": h, "scale": SCALE})
    return out


def ink_std(crop):
    """Cheap ink measure: std of the greyscale, downsampled."""
    g = crop.convert("L").resize((64, 64))
    px = list(g.getdata())
    mean = sum(px) / len(px)
    return (sum((p - mean) ** 2 for p in px) / len(px)) ** 0.5


os.makedirs(IN, exist_ok=True)
for f in os.listdir(IN):
    if f.endswith(".jpg"):
        os.remove(os.path.join(IN, f))

all_patches = patch_origins()
kept = []
skipped = 0
for i, p in enumerate(all_patches):
    crop = master.crop((p["gx"], p["gy"], p["gx"] + p["w"], p["gy"] + p["h"]))
    if ink_std(crop) < MIN_INK_STD:
        skipped += 1
        continue
    up = crop.resize((round(p["w"] * SCALE), round(p["h"] * SCALE)), Image.LANCZOS)
    up = up.filter(ImageFilter.UnsharpMask(radius=1.0, percent=80, threshold=1))
    up.save(os.path.join(IN, f"{p['id']}.jpg"), quality=88)
    kept.append(p)
    if (i + 1) % 20 == 0:
        print(f"   {i + 1}/{len(all_patches)}")

with open(PATCHES, "w") as fh:
    json.dump({"master": MASTER_REL, "region": {"x": X, "y": Y, "w": W, "h": H},
               "dims": {"w": MW, "h": MH}, "patch": PATCH, "overlap": OVERLAP,
               "stride": stride, "scale": SCALE, "count": len(kept),
               "patches": kept}, fh, indent=2)
print(f"✓ {len(kept)} patches -> {os.path.relpath(IN, ROOT)}  (skipped {skipped} blank)")
