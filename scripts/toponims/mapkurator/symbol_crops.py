#!/usr/bin/env python3
"""Crop the engraving SYMBOL window for the 'altre' toponyms (those the name rule
can't type) into montages of 12 for a Sonnet vision pass that classifies each
symbol against the LITERAL 1785 legend.

Lessons baked in:
  - 12 crops/montage -> image 1360x1248, UNDER the 1568px read cap, so it is NOT
    downscaled (24 was too tall and became illegible).
  - Header shows "#<idx>  <nom>"; results are mapped back BY INDEX via the manifest,
    never by the id the model reads (Sonnet misreads C->D / digits).

Outputs per quadrant under data/toponims/mapkurator/<q>/sym/ (gitignored):
  batch_NNN.jpg  + a global manifest data/toponims/mapkurator/sym_manifest.json
  = {q: [[id0,id1,...id11], ...]}  (ordered ids per montage).

  nix-shell scripts/toponims/mapkurator/shell.nix --run \
    "python3 scripts/toponims/mapkurator/symbol_crops.py"
"""
import json
import os
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CW, CH, LAB = 680, 180, 28
COLS, ROWS = 2, 6
PER = COLS * ROWS  # 12

manifest = {}
for q in ("nw", "ne", "se", "sw"):
    top = os.path.join(ROOT, f"data/toponims/{q}/toponims.json")
    img = os.path.join(ROOT, f"data/jpg/{q.upper()}/despuig-1785-original-{q.upper()}.jpg")
    if not (os.path.exists(top) and os.path.exists(img)):
        continue
    ts = json.load(open(top))["toponims"]
    im = Image.open(img).convert("RGB")
    W, H = im.size
    sel = [t for t in ts if t["tipus"] == "altre"]
    outdir = os.path.join(ROOT, f"data/toponims/mapkurator/{q}/sym")
    os.makedirs(outdir, exist_ok=True)
    batches = []
    for b in range((len(sel) + PER - 1) // PER):
        chunk = sel[b * PER:b * PER + PER]
        mont = Image.new("RGB", (COLS * CW, ROWS * (CH + LAB)), (255, 255, 255))
        dr = ImageDraw.Draw(mont)
        ids = []
        for i, t in enumerate(chunk):
            x, y = t["x"], t["y"]
            x0 = min(max(x - CW // 2, 0), W - CW)
            y0 = min(max(y - CH // 2, 0), H - CH)
            crop = im.crop((x0, y0, x0 + CW, y0 + CH))
            r, c = divmod(i, COLS)
            ox, oy = c * CW, r * (CH + LAB)
            dr.rectangle([ox, oy, ox + CW, oy + LAB], fill=(20, 20, 20))
            dr.text((ox + 6, oy + 7), f"#{i}   {t['nom']}", fill=(255, 255, 255))
            mont.paste(crop, (ox, oy + LAB))
            dr.line([(ox + (x - x0), oy + LAB), (ox + (x - x0), oy + LAB + 10)], fill=(255, 0, 0), width=2)
            ids.append(t["id"])
        mont.save(os.path.join(outdir, f"batch_{b:03d}.jpg"), quality=90)
        batches.append(ids)
    manifest[q] = batches
    print(f"{q}: {len(sel)} altre -> {len(batches)} montages")

mpath = os.path.join(ROOT, "data/toponims/mapkurator/sym_manifest.json")
json.dump(manifest, open(mpath, "w"), ensure_ascii=False)
print(f"counts={{ {', '.join(f'{q}:{len(v)}' for q,v in manifest.items())} }}  "
      f"TOTAL {sum(len(v) for v in manifest.values())} montages -> {mpath}")
