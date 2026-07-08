#!/usr/bin/env python3
"""Phase 1 merge: shift every patch's word polygons into master-image coordinates
and deduplicate the same word seen in overlapping patches, using real polygon
geometry (shapely) rather than a bbox approximation.

    nix-shell scripts/toponims/mapkurator/shell.nix \
        --run "python3 scripts/toponims/mapkurator/merge_detections.py"

Reads  data/toponims/mapkurator/{patches.json, out/<id>.json}
Writes data/toponims/mapkurator/detections.json  (one entry per distinct word).
"""
import json
import os

import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Polygon
from shapely.validation import make_valid

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(ROOT, "data/toponims/mapkurator")
# per-sheet support (defaults = the master): override for a sheet crop, e.g.
#   MK_PATCHES=nw/patches.json MK_OUTDIR=nw/out MK_DETECTIONS=nw/detections.json
PATCHES = os.path.join(BASE, os.environ.get("MK_PATCHES", "patches.json"))
OUTDIR = os.path.join(BASE, os.environ.get("MK_OUTDIR", "out"))
DETECTIONS = os.path.join(BASE, os.environ.get("MK_DETECTIONS", "detections.json"))

IOU_DUP = 0.45        # two boxes with IoU above this are the same word
CONTAIN_DUP = 0.60    # ...or one mostly inside the other (an edge fragment)


def load_raw():
    """Every detection from every patch, in master pixel coords."""
    man = json.load(open(PATCHES))
    dets = []
    for p in man["patches"]:
        f = os.path.join(OUTDIR, f"{p['id']}.json")
        if not os.path.exists(f):
            continue
        d = json.load(open(f))
        px, py = d.get("polygon_x", {}), d.get("polygon_y", {})
        for k in px:
            xs, ys = px[k], py.get(k)
            if not xs or not ys:
                continue
            pts = [(p["gx"] + x / p["scale"], p["gy"] + y / p["scale"])
                   for x, y in zip(xs, ys)]
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = make_valid(poly)
            if poly.is_empty or poly.area <= 0:
                continue
            dets.append({
                "patch": p["id"], "text": d.get("text", {}).get(k, ""),
                "score": float(d.get("score", {}).get(k, 0.0)),
                "pts": [[int(round(a)), int(round(b))] for a, b in pts],
                "poly": poly,
            })
    return man, dets


def dedup(dets):
    """Greedy: keep highest score first; drop later boxes that overlap a kept one
    (true polygon IoU, or high containment for edge fragments). KDTree on centroids
    restricts the comparison to nearby boxes so it stays near-linear."""
    for d in dets:
        c = d["poly"].centroid
        d["cx"], d["cy"] = c.x, c.y
        d["area"] = d["poly"].area
    order = sorted(range(len(dets)), key=lambda i: (-dets[i]["score"], -dets[i]["area"]))

    cents = np.array([[dets[i]["cx"], dets[i]["cy"]] for i in range(len(dets))])
    tree = cKDTree(cents)

    kept, dropped = [], 0
    alive = [False] * len(dets)
    for i in order:
        d = dets[i]
        # neighbours within ~the box diagonal — candidates for being the same word
        r = max(d["poly"].bounds[2] - d["poly"].bounds[0],
                d["poly"].bounds[3] - d["poly"].bounds[1]) + 30
        dup = False
        for j in tree.query_ball_point([d["cx"], d["cy"]], r):
            if not alive[j] or j == i:
                continue
            k = dets[j]
            inter = d["poly"].intersection(k["poly"]).area
            if inter <= 0:
                continue
            union = d["area"] + k["area"] - inter
            iou = inter / union if union else 0.0
            contain = inter / min(d["area"], k["area"])
            if iou > IOU_DUP or contain > CONTAIN_DUP:
                dup = True
                break
        if dup:
            dropped += 1
            continue
        alive[i] = True
        kept.append(i)
    return [dets[i] for i in kept], dropped


def main():
    man, dets = load_raw()
    print(f"raw detections: {len(dets)}")
    kept, dropped = dedup(dets)
    print(f"dedup: dropped {dropped} overlaps -> {len(kept)} distinct words")

    kept.sort(key=lambda d: (round(d["cy"]), round(d["cx"])))
    out = []
    for i, d in enumerate(kept):
        xs = [p[0] for p in d["pts"]]
        ys = [p[1] for p in d["pts"]]
        x0, y0 = min(xs), min(ys)
        out.append({
            "id": f"t{i:04d}", "text": d["text"], "score": round(d["score"], 4),
            "cx": int(round(d["cx"])), "cy": int(round(d["cy"])),
            "bbox": [x0, y0, max(xs) - x0, max(ys) - y0],
            "poly": d["pts"],
        })
    json.dump({"source": "mapkurator-spotter v2 (english)", "region": man["region"],
               "count": len(out), "detections": out},
              open(DETECTIONS, "w"),
              ensure_ascii=False, indent=2)
    print(f"✓ {os.path.relpath(DETECTIONS, ROOT)} - {len(out)} word polygons")


if __name__ == "__main__":
    main()
