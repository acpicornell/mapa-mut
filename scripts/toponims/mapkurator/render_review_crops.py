#!/usr/bin/env python3
"""Render one engraving crop per toponym that still needs review (suggerit /
posicional / sense), plus a review-data.json the web review tool consumes.

    nix-shell scripts/toponims/mapkurator/shell.nix \
        --run "python3 scripts/toponims/mapkurator/render_review_crops.py"

Reads data/toponims/ngib/matches.json + data/toponims/b/recheck.json + the master
scan. Writes data/toponims/review-crops/<id>.jpg + data/toponims/review-data.json
(both gitignored, regenerable).

Env overrides (default = global A pipeline; set for a per-sheet quadrant):
  MATCHES_JSON, RECHECK_JSON, TOPONIMS_JSON, MASTER_IMG, REVIEW_CROPS, REVIEW_DATA
e.g. for NW: MATCHES_JSON=data/toponims/nw/matches.json
             RECHECK_JSON=data/toponims/nw/recheck.json
             TOPONIMS_JSON=data/toponims/nw/toponims.json
             MASTER_IMG=data/jpg/NW/despuig-1785-original-NW-canvas.jpg
             REVIEW_CROPS=data/toponims/nw/review-crops
             REVIEW_DATA=data/toponims/nw/review-data.json
"""
import json, os
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
P = lambda env, default: os.environ.get(env) or os.path.join(ROOT, default)
CROPS = P("REVIEW_CROPS", "data/toponims/review-crops")
REVIEW_DATA = P("REVIEW_DATA", "data/toponims/review-data.json")
# Which decision classes to render for review. Default = only the uncertain ones
# (global pipeline unchanged); set REVIEW_WANT=all (or a comma list) to also curate
# the auto-classified confirmat/probable and catch errors there.
ALL_DEC = {"curat", "confirmat", "probable", "suggerit", "posicional", "sense"}
_w = (os.environ.get("REVIEW_WANT") or "suggerit,posicional,sense").strip()
WANT = ALL_DEC if _w == "all" else set(_w.replace(" ", "").split(","))
WW, WH, SCALE = 760, 320, 1.5

os.makedirs(CROPS, exist_ok=True)
matches = json.load(open(P("MATCHES_JSON", "data/toponims/ngib/matches.json")))
recheck = {r["id"]: r for r in json.load(open(P("RECHECK_JSON", "data/toponims/b/recheck.json")))}
master = Image.open(P("MASTER_IMG", "data/jpg/despuig-1785-original.jpg")).convert("RGB")

# geo: toponym projected lon/lat + each candidate's real NGIB position (for the modern map)
import re
from collections import defaultdict
from unidecode import unidecode
topo = {t["id"]: t
        for t in json.load(open(P("TOPONIMS_JSON", "data/toponims/toponims.json")))["toponims"]}
llocs = json.load(open(f"{ROOT}/data/toponims/ngib/llocs.json"))
core = lambda s: re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", unidecode((s or "").lower()))).strip()
by_name = defaultdict(list)
for g in llocs:
    by_name[core(g["grafia"])].append(g)


def cand_ll(grafia, lon, lat):
    cs = by_name.get(core(grafia))
    if not cs or lon is None:
        return None, None
    g = min(cs, key=lambda g: (g["lng"] - lon) ** 2 + (g["lat"] - lat) ** 2)
    return round(g["lng"], 5), round(g["lat"], 5)


items = []
for m in matches:
    if m["decision"] not in WANT:
        continue
    t = topo.get(m["id"])
    if not t:                       # position lives in the toponym table (not all are in recheck)
        continue
    x, y = t["x"], t["y"]
    crop = master.crop((x - WW // 2, y - WH // 2, x + WW // 2, y + WH // 2)).copy()
    d = ImageDraw.Draw(crop)
    cx, cy = crop.width // 2, crop.height // 2
    d.line((cx - 16, cy, cx + 16, cy), fill=(220, 0, 0), width=2)
    d.line((cx, cy - 16, cx, cy + 16), fill=(220, 0, 0), width=2)
    crop = crop.resize((int(WW * SCALE), int(WH * SCALE)), Image.LANCZOS)
    crop.save(f"{CROPS}/{m['id']}.jpg", quality=82)
    lon, lat = t.get("lon"), t.get("lat")
    cands, r = [], recheck.get(m["id"])
    if r:
        for c in r.get("candidates", [])[:6]:
            clon, clat = cand_ll(c["grafia"], lon, lat)
            cands.append({"grafia": c["grafia"], "municipi": c["municipi"],
                          "km": c["km"], "sim": c["sim"], "lon": clon, "lat": clat})
    # confirmat/probable often aren't in recheck — surface their CURRENT match so the
    # reviewer sees what it's matched to (marked as recommended via ngib) and can re-pick.
    if m.get("ngib") and not any(c["grafia"] == m["ngib"] for c in cands):
        clon, clat = cand_ll(m["ngib"], lon, lat)
        cands.insert(0, {"grafia": m["ngib"], "municipi": m.get("municipi"),
                         "km": m.get("km"), "sim": m.get("sim"), "lon": clon, "lat": clat})
    items.append({
        "id": m["id"], "graf": m["graf"], "nom": m["nom"], "tipus": m["tipus"],
        "decision": m["decision"], "x": x, "y": y, "lon": lon, "lat": lat,
        "ngib": m.get("ngib"), "sim": m.get("sim"), "km": m.get("km"),
        "candidates": cands,
    })

json.dump({"count": len(items), "items": items},
          open(REVIEW_DATA, "w"), ensure_ascii=False)
from collections import Counter
print(f"review items: {len(items)}  {dict(Counter(i['decision'] for i in items))}")
print(f"✓ {CROPS}/<id>.jpg + {REVIEW_DATA}")
