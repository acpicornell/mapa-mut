#!/usr/bin/env python3
"""Approach B — COASTAL oriented windows (deskewed strips).

Interior place-names on the Despuig map are horizontal and the axis-aligned
windowing (`b_windows.py`) reads them well. Coastal names are written *along the
coastline at an angle*: their axis-aligned boxes overlap their neighbours and a
rectangular window crop both MERGES adjacent names and MUTILATES the diagonal
ones at the cut. ~23 % of the spotter boxes are tilted >20 deg.

This module handles ONLY the tilted boxes, using the spotter's per-box polygon
(which captures the writing direction):

  1. ORIENT  — each box's text axis = PCA of its `poly` points.
  2. RIBBON  — union-find that connects two tilted boxes only when they are close
               AND the segment between their centres runs along *both* boxes'
               text axis (so two parallel coastal names whose boxes overlap are
               NOT merged). Each ribbon is one toponym (or a short run).
  3. DESKEW  — render each ribbon rotated to horizontal (PIL AFFINE), drawing the
               real oriented box outlines + numbers; stack several ribbons into a
               montage "window" (~TARGET boxes) the vision agent reads like any
               other window. Box positions stay in ORIGINAL crop pixel space (the
               words file carries original cx,cy) so georef is unaffected.

Output dir (B_OUTDIR, default a sibling `b-coast/`) uses the SAME schema as
`b_windows.py` (w##.png + windows.json + words[{n,text,cx,cy}]), so
`split_windows.py`, the `b-extract-sheet` workflow and `b_assemble.py` consume it
unchanged. It also writes `coast-boxes.json` (the [cx,cy] of every tilted box it
claimed) so `b_assemble.py` can drop the interior toponyms it supersedes.

    B_DET=data/toponims/mapkurator/nw/detections.json \
    B_MASTER=data/jpg/NW/despuig-1785-original-NW-canvas.jpg \
    B_OUTDIR=data/toponims/mapkurator/nw/b-coast \
      nix-shell scripts/toponims/mapkurator/shell.nix \
      --run "python3 scripts/toponims/mapkurator/b_coast_windows.py 0 0 9560 7299"
"""
import glob, json, math, os, sys
from PIL import Image, ImageDraw, ImageFont
Image.MAX_IMAGE_PIXELS = None


def _font(size):
    for pat in ("/nix/store/*/share/fonts/**/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/**/DejaVuSans-Bold.ttf"):
        for p in glob.glob(pat, recursive=True):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


FONT = _font(24)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(ROOT, os.environ.get("B_OUTDIR", "data/toponims/mapkurator/b-coast"))
DET_PATH = os.path.join(ROOT, os.environ.get("B_DET", "data/toponims/mapkurator/detections.json"))
MASTER_IMG = os.path.join(ROOT, os.environ.get("B_MASTER", "data/jpg/despuig-1785-original.jpg"))

MIN_TILT = float(os.environ.get("B_MIN_TILT", "20"))   # deg: boxes tilted more than this are "coastal"
DIST = float(os.environ.get("B_RIBBON_DIST", "300"))   # px: max centre gap to join along a ribbon
TOL = float(os.environ.get("B_RIBBON_TOL", "24"))      # deg: max axis/segment misalignment to join
PERP_FRAC = float(os.environ.get("B_RIBBON_PERP", "0.7"))  # max perp offset, in median box heights
TARGET = int(os.environ.get("B_TARGET", "70"))         # aim ~this many boxes per montage window
MARGIN = 26          # px around a ribbon (along+perp) before scaling
SCALE = 2.0          # upscale the deskewed strip for legibility
GAP = 22             # px between stacked strips in a montage
PAD = 16             # px montage border
AREA = list(map(int, sys.argv[1:5])) if len(sys.argv) >= 5 else [330, 470, 18600, 14430]


def norm90(a):
    """Fold a degree angle into (-90, 90] (text axis is undirected)."""
    a = (a + 90) % 180 - 90
    return a


def pca_angle(pts):
    """Principal-axis angle (deg, in (-90,90]) of a point cloud."""
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sxy = syy = 0.0
    for x, y in pts:
        dx, dy = x - mx, y - my
        sxx += dx * dx; sxy += dx * dy; syy += dy * dy
    return norm90(math.degrees(0.5 * math.atan2(2 * sxy, sxx - syy)))


def axis(b):
    """Writing direction of a box = chord of its poly's top edge (deg, (-90,90]).
    The spotter poly is [top-left .. top-right, bottom-right .. bottom-left], so the
    first->last top point runs along the baseline -- far more reliable than PCA over
    a single round glyph."""
    p = b["poly"]; n = len(p) // 2
    return norm90(math.degrees(math.atan2(p[n - 1][1] - p[0][1], p[n - 1][0] - p[0][0])))


def mean_axis(boxes):
    """Circular mean of member box axes (undirected, mod 180)."""
    s = sum(math.sin(math.radians(2 * axis(b))) for b in boxes)
    c = sum(math.cos(math.radians(2 * axis(b))) for b in boxes)
    return norm90(math.degrees(0.5 * math.atan2(s, c)))


def tilt(b):
    return abs(axis(b))


def box_height(b):
    """Extent of the box perpendicular to its own text axis."""
    a = math.radians(axis(b)); ca, sa = math.cos(a), math.sin(a)
    perp = [-x * sa + y * ca for x, y in b["poly"]]
    return max(perp) - min(perp)


def angdiff(a, b):
    """Smallest difference between two undirected axes (deg, 0..90)."""
    d = abs(a - b) % 180
    return min(d, 180 - d)


def ribbons(boxes):
    """Union-find: join boxes that are near AND collinear along their text axis."""
    ax = [axis(b) for b in boxes]
    hs = sorted(box_height(b) for b in boxes)
    medh = hs[len(hs) // 2] if hs else 1.0
    perp_max = PERP_FRAC * medh
    parent = list(range(len(boxes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    cell = DIST
    grid = {}
    for i, b in enumerate(boxes):
        grid.setdefault((int(b["cx"] // cell), int(b["cy"] // cell)), []).append(i)
    for (gx, gy), idxs in grid.items():
        near = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                for j in grid.get((gx + dx, gy + dy), [])]
        for i in idxs:
            for j in near:
                if j <= i:
                    continue
                dx = boxes[j]["cx"] - boxes[i]["cx"]; dy = boxes[j]["cy"] - boxes[i]["cy"]
                dist = math.hypot(dx, dy)
                if dist >= DIST or dist == 0:
                    continue
                seg = norm90(math.degrees(math.atan2(dy, dx)))
                if angdiff(seg, ax[i]) > TOL or angdiff(seg, ax[j]) > TOL \
                        or angdiff(ax[i], ax[j]) > TOL:
                    continue
                # perpendicular separation: keep parallel ribbons apart
                perp = abs(dist * math.sin(math.radians(angdiff(seg, ax[i]))))
                if perp > perp_max:
                    continue
                parent[find(i)] = find(j)
    groups = {}
    for i, b in enumerate(boxes):
        groups.setdefault(find(i), []).append(b)
    return list(groups.values())


def deskew_strip(master, boxes):
    """Return (PIL strip, [(box, [poly_px...])]) with the ribbon rotated horizontal."""
    phi = mean_axis(boxes)
    a = math.radians(phi); ca, sa = math.cos(a), math.sin(a)
    rot = lambda x, y: (x * ca + y * sa, -x * sa + y * ca)        # world -> rotated frame
    wpts = [rot(x, y) for b in boxes for x, y in b["poly"]]
    minx = min(p[0] for p in wpts) - MARGIN; maxx = max(p[0] for p in wpts) + MARGIN
    miny = min(p[1] for p in wpts) - MARGIN; maxy = max(p[1] for p in wpts) + MARGIN
    outW = max(1, int((maxx - minx) * SCALE)); outH = max(1, int((maxy - miny) * SCALE))
    # AFFINE maps output (xo,yo) -> source (in_x,in_y): inverse of (rotate, offset, scale)
    coef = (ca / SCALE, -sa / SCALE, ca * minx - sa * miny,
            sa / SCALE,  ca / SCALE, sa * minx + ca * miny)
    strip = master.transform((outW, outH), Image.AFFINE, coef, Image.BICUBIC)
    drawn = []
    for b in boxes:
        px = [(((x * ca + y * sa) - minx) * SCALE, ((-x * sa + y * ca) - miny) * SCALE)
              for x, y in b["poly"]]
        drawn.append((b, px))
    return strip, drawn


def main():
    os.makedirs(OUT, exist_ok=True)
    det = json.load(open(DET_PATH))["detections"]
    X0, Y0, X1, Y1 = AREA
    steep = [b for b in det if X0 <= b["cx"] < X1 and Y0 <= b["cy"] < Y1
             and len(b.get("poly", [])) >= 4 and tilt(b) > MIN_TILT]
    print(f">> area {AREA}: {len(steep)} tilted boxes (>{MIN_TILT} deg)")
    ribs = ribbons(steep)
    ribs.sort(key=lambda r: (min(b["cy"] for b in r), min(b["cx"] for b in r)))
    print(f"   {len(ribs)} ribbons")

    # bin ribbons into montage windows of ~TARGET boxes
    wins, cur, n = [], [], 0
    for r in ribs:
        if cur and n + len(r) > TARGET:
            wins.append(cur); cur, n = [], 0
        cur.append(r); n += len(r)
    if cur:
        wins.append(cur)

    master = Image.open(MASTER_IMG).convert("RGB")
    index = []
    for wi, win in enumerate(wins, 1):
        strips = []
        for r in win:
            r = sorted(r, key=lambda b: b["cx"] * math.cos(math.radians(axis(b)))
                       + b["cy"] * math.sin(math.radians(axis(b))))
            strips.append(deskew_strip(master, r))
        cw = max(s.width for s, _ in strips) + 2 * PAD
        ch = sum(s.height for s, _ in strips) + GAP * (len(strips) - 1) + 2 * PAD
        canvas = Image.new("RGB", (cw, ch), (246, 241, 231))
        dr = ImageDraw.Draw(canvas)
        words = []
        n = 0
        y = PAD
        for strip, drawn in strips:
            canvas.paste(strip, (PAD, y))
            for b, px in drawn:
                n += 1
                pts = [(PAD + x, y + yy) for x, yy in px]
                dr.line(pts + [pts[0]], fill=(200, 0, 0), width=2)
                tx, ty = min(p[0] for p in pts), min(p[1] for p in pts) - 12
                lab = str(n)
                ty -= 12  # lift the (now larger) label clear of the box top
                for ox, oy in ((-2, -2), (2, -2), (-2, 2), (2, 2), (0, 0)):
                    dr.text((tx + ox, ty + oy), lab, fill=(255, 255, 255), font=FONT)  # halo
                dr.text((tx, ty), lab, fill=(190, 0, 0), font=FONT)
                words.append({"n": n, "text": b["text"], "cx": b["cx"], "cy": b["cy"]})
            dr.line((PAD, y + strip.height + GAP // 2, cw - PAD, y + strip.height + GAP // 2),
                    fill=(220, 210, 195), width=1)
            y += strip.height + GAP
        canvas.save(os.path.join(OUT, f"w{wi:02d}.png"))
        xs = [b["cx"] for r in win for b in r]; ys = [b["cy"] for r in win for b in r]
        index.append({"w": wi, "file": f"w{wi:02d}.png",
                      "bounds": [min(xs), min(ys), max(xs), max(ys)],
                      "n_boxes": len(words), "words": words})

    json.dump({"area": AREA, "scale": SCALE, "coast": True, "windows": index},
              open(os.path.join(OUT, "windows.json"), "w"), ensure_ascii=False, indent=1)
    json.dump({"boxes": [[b["cx"], b["cy"]] for b in steep]},
              open(os.path.join(OUT, "coast-boxes.json"), "w"), ensure_ascii=False, indent=1)
    sizes = sorted(x["n_boxes"] for x in index) or [0]
    print(f"   boxes/window: min {sizes[0]} median {sizes[len(sizes)//2]} max {sizes[-1]}")
    print(f"✓ {len(index)} coast windows -> {OUT}/w##.png + windows.json + coast-boxes.json")


if __name__ == "__main__":
    main()
