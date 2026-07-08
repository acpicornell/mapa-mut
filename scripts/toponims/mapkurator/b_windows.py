#!/usr/bin/env python3
"""Approach B — window the map so no toponym is ever truncated.

Two steps, both driven by the spotter word boxes:
  1. CLUSTER the boxes into atomic groups by proximity (union-find, chebyshev
     centroid distance < DIST). A cluster is a provisional toponym (or a few
     adjacent ones); it is NEVER split across windows.
  2. BIN the clusters into a coarse grid (~TARGET boxes per cell) by their
     centroid. Each non-empty cell is a window, sized to the full extent of its
     clusters' boxes (+ MARGIN) so nothing is clipped visually either.
Because clusters are atomic and assigned whole, a cut never falls through a name,
and each box belongs to exactly one window -> later dedup is by box number, never
text. (Global XY-cut fails here: a dense field has no full-span whitespace valley.)

    nix-shell scripts/toponims/mapkurator/shell.nix \
        --run "python3 scripts/toponims/mapkurator/pilotB_windows.py [x0 y0 x1 y1]"

Writes data/toponims/mapkurator/pilotB/w##.png + windows.json (gitignored). Does
NOT touch the production pipeline.
"""
import json, math, os, sys
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(ROOT, os.environ.get("B_OUTDIR", "data/toponims/mapkurator/b"))
# per-sheet support: point at a sheet's detections + the image to crop from. For a
# sheet the detection coords already live in that crop's pixel space, so B_MASTER
# must be the SAME crop the spotter ran on.
DET_PATH = os.path.join(ROOT, os.environ.get("B_DET", "data/toponims/mapkurator/detections.json"))
MASTER_IMG = os.path.join(ROOT, os.environ.get("B_MASTER", "data/jpg/despuig-1785-original.jpg"))
DIST = 115           # px: boxes within this (chebyshev, centre-to-centre) cluster together
TARGET = int(os.environ.get("B_TARGET", "80"))   # aim for ~this many boxes per window
MARGIN = 55          # px padding around a window's box extent (context, no clip)
# per-sheet hybrid: drop tilted (coastal) boxes here so they go through the deskewed
# coastal track (b_coast_windows.py) instead. Default off -> global path unchanged.
MAX_TILT = float(os.environ["B_MAX_TILT"]) if os.environ.get("B_MAX_TILT") else None
SCALE = 1.7
# default = whole detection extent; override with argv "x0 y0 x1 y1" for a sub-area
AREA = list(map(int, sys.argv[1:5])) if len(sys.argv) >= 5 else [330, 470, 18600, 14430]


def tilt(b):
    """Writing-direction tilt from horizontal (deg), from the poly's top-edge chord.
    Matches b_coast_windows.axis(); used only to split flat (interior) from tilted
    (coastal) boxes when B_MAX_TILT is set."""
    p = b.get("poly") or []
    if len(p) < 4:
        return 0.0
    n = len(p) // 2
    a = math.degrees(math.atan2(p[n - 1][1] - p[0][1], p[n - 1][0] - p[0][0]))
    return abs((a + 90) % 180 - 90)


def cluster(boxes):
    """Union-find: connect boxes whose centres are within DIST on both axes."""
    parent = list(range(len(boxes)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    # bucket by coarse grid so we only test nearby pairs (cheap)
    cell = DIST
    grid = {}
    for i, b in enumerate(boxes):
        grid.setdefault((b["cx"] // cell, b["cy"] // cell), []).append(i)
    for (gx, gy), idxs in grid.items():
        near = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                for j in grid.get((gx + dx, gy + dy), [])]
        for i in idxs:
            for j in near:
                if j > i and abs(boxes[i]["cx"] - boxes[j]["cx"]) < DIST \
                        and abs(boxes[i]["cy"] - boxes[j]["cy"]) < DIST:
                    parent[find(i)] = find(j)
    groups = {}
    for i, b in enumerate(boxes):
        groups.setdefault(find(i), []).append(b)
    return list(groups.values())


def windows(boxes, area):
    """Recursive median split that balances box counts AND cuts in whitespace: at
    each step split along the longer axis, choosing among the central indices the
    one with the LARGEST gap between consecutive boxes -> the cut falls between
    toponyms, not through one, while keeping windows evenly sized."""
    nclust = len(cluster(boxes))                      # reported for reference only
    out = []
    stack = [boxes]
    while stack:
        bs = stack.pop()
        if len(bs) <= TARGET:
            out.append(bs)
            continue
        xs = [b["cx"] for b in bs]; ys = [b["cy"] for b in bs]
        k = "cx" if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else "cy"
        s = sorted(bs, key=lambda b: b[k])
        lo, hi = int(len(s) * 0.35), int(len(s) * 0.65)
        i = max(range(lo, max(lo + 1, hi)), key=lambda j: s[j + 1][k] - s[j][k])
        stack.append(s[:i + 1]); stack.append(s[i + 1:])
    return out, nclust


def main():
    os.makedirs(OUT, exist_ok=True)
    det = json.load(open(DET_PATH))["detections"]
    # reference overlay only (current.json) — read the SHEET's own table, never the
    # global one, so a per-sheet run has no dependency on the whole-island pipeline.
    top_path = os.path.join(ROOT, os.environ.get("TOPONIMS_JSON", "data/toponims/toponims.json"))
    top = json.load(open(top_path))["toponims"] if os.path.exists(top_path) else []
    X0, Y0, X1, Y1 = AREA
    boxes = [b for b in det if X0 <= b["cx"] < X1 and Y0 <= b["cy"] < Y1]
    if MAX_TILT is not None:
        before = len(boxes)
        boxes = [b for b in boxes if tilt(b) <= MAX_TILT]
        print(f">> kept {len(boxes)}/{before} flat boxes (tilt <= {MAX_TILT} deg); "
              f"tilted ones go to the coastal track")
    wins, nclust = windows(boxes, AREA)
    wins = [w for w in wins if w]
    wins.sort(key=lambda w: (min(b["cy"] for b in w), min(b["cx"] for b in w)))
    print(f">> area {AREA}: {len(boxes)} boxes -> {nclust} clusters -> {len(wins)} windows")

    master = Image.open(MASTER_IMG).convert("RGB")
    index = []
    for wi, w in enumerate(wins, 1):
        xs = [b["bbox"][0] for b in w] + [b["bbox"][0] + b["bbox"][2] for b in w]
        ys = [b["bbox"][1] for b in w] + [b["bbox"][1] + b["bbox"][3] for b in w]
        wx0, wy0 = max(0, min(xs) - MARGIN), max(0, min(ys) - MARGIN)
        wx1, wy1 = max(xs) + MARGIN, max(ys) + MARGIN
        crop = master.crop((wx0, wy0, wx1, wy1)).resize(
            (int((wx1 - wx0) * SCALE), int((wy1 - wy0) * SCALE)), Image.LANCZOS)
        dr = ImageDraw.Draw(crop)
        ws = sorted(w, key=lambda b: (round((b["cy"] - wy0) / 90), b["cx"]))
        words = []
        for n, b in enumerate(ws, 1):
            bx, by, bw, bh = b["bbox"]
            x = (bx - wx0) * SCALE; y = (by - wy0) * SCALE
            dr.rectangle((x, y, x + bw * SCALE, y + bh * SCALE), outline=(200, 0, 0), width=2)
            dr.text((x, y - 11), str(n), fill=(0, 0, 220))
            words.append({"n": n, "text": b["text"], "cx": b["cx"], "cy": b["cy"]})
        crop.save(os.path.join(OUT, f"w{wi:02d}.png"))
        index.append({"w": wi, "file": f"w{wi:02d}.png",
                      "bounds": [wx0, wy0, wx1, wy1], "n_boxes": len(words), "words": words})
    cur = [{"graf": t["graf"], "x": t["x"], "y": t["y"]}
           for t in top if X0 <= t["x"] < X1 and Y0 <= t["y"] < Y1]
    json.dump({"area": AREA, "scale": SCALE, "windows": index},
              open(os.path.join(OUT, "windows.json"), "w"), ensure_ascii=False, indent=1)
    json.dump({"current": cur}, open(os.path.join(OUT, "current.json"), "w"),
              ensure_ascii=False, indent=1)
    sizes = sorted(x["n_boxes"] for x in index)
    print(f"   boxes/window: min {sizes[0]} median {sizes[len(sizes)//2]} max {sizes[-1]}")
    print(f"✓ {len(index)} windows -> {OUT}/w##.png + windows.json (+ current.json, {len(cur)} toponyms)")


if __name__ == "__main__":
    main()
