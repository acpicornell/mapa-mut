#!/usr/bin/env python3
"""Per-sheet georeference: project one quadrant's toponyms from the hand-marked
control points of THAT sheet, working entirely in the sheet crop's pixel space.

Unlike the global georef.py (master-space, 60+ mixed anchors), this fits only the
exact interior-town dots the user marked on the sheet crop — immutable municipi
positions whose modern coordinates are certain (NGIB / pobles.json). Coastal dots
are kept aside (positions shifted historically); pass --with-coast to include them.

Transform: the mapKurator family (affine -order1 / polynomial -order2 / tps),
chosen by leave-one-out on the towns. poly2 is the safe default — it stays smooth
past the GCP hull (TPS rings out along the coast where no town anchors it).

    GCPS_NW=data/toponims/mapkurator/nw/gcps-nw.json \
    TOPONIMS_JSON=data/toponims/nw/toponims.json \
    nix-shell scripts/toponims/shell.nix --run \
      "python3 scripts/toponims/mapkurator/georef_sheet.py"

Writes lon/lat into every toponym of TOPONIMS_JSON and a gcps dump beside it.
"""
import json, math, os, sys
import numpy as np
from scipy.interpolate import RBFInterpolator

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GCPS = os.path.join(ROOT, os.environ.get("GCPS_NW", "data/toponims/nw/gcps-nw.json"))
TOP = os.environ.get("TOPONIMS_JSON") or os.path.join(ROOT, "data/toponims/nw/toponims.json")
GCPS_OUT = os.environ.get("GCPS_OUT") or os.path.join(os.path.dirname(TOP), "gcps-used.json")
WITH_COAST = "--with-coast" in sys.argv


def merr(lo, la, tlo, tla):
    return math.hypot((lo - tlo) * 111320 * math.cos(math.radians(la)),
                      (la - tla) * 110540)


def design(p, deg):
    x, y = p[:, 0] / 1e4, p[:, 1] / 1e4
    cols = [np.ones_like(x)]
    for d in range(1, deg + 1):
        cols += [(x ** (d - i)) * (y ** i) for i in range(d + 1)]
    return np.column_stack(cols)


def main():
    g = json.load(open(GCPS))
    pts = list(g["interior"])
    if WITH_COAST:
        pts += [p for p in g.get("coast", [])]
    P = np.array([[c["x"], c["y"]] for c in pts], float)
    LL = np.array([[c["lng"], c["lat"]] for c in pts], float)
    print(f">> {len(pts)} control points "
          f"({len(g['interior'])} interior{' + coast' if WITH_COAST else ''})")

    def make(kind):
        if kind == "tps":
            r = RBFInterpolator(P, LL, kernel="thin_plate_spline")
            return lambda Q: r(Q)
        deg = int(kind[-1])
        c, *_ = np.linalg.lstsq(design(P, deg), LL, rcond=None)
        return lambda Q: design(Q, deg) @ c

    def loo(kind):
        es = []
        for i in range(len(pts)):
            m = [j for j in range(len(pts)) if j != i]
            if kind == "tps":
                pr = RBFInterpolator(P[m], LL[m], kernel="thin_plate_spline")([P[i]])[0]
            else:
                deg = int(kind[-1])
                c, *_ = np.linalg.lstsq(design(P[m], deg), LL[m], rcond=None)
                pr = (design(P[i:i + 1], deg) @ c)[0]
            es.append(merr(pr[0], pr[1], LL[i, 0], LL[i, 1]))
        return float(np.median(es)), float(np.max(es))

    scores = {k: loo(k) for k in ("poly1", "poly2", "tps")}
    label = {"poly1": "affine(-order1)", "poly2": "polynomial(-order2)", "tps": "tps"}
    # default: lowest median LOO, but prefer poly2 over tps on a near-tie (no coastal
    # rings). Among polynomials/tps the smallest median wins.
    best = min(scores, key=lambda k: scores[k][0])
    for k, (md, mx) in scores.items():
        print(f"   {label[k]:18s} LOO median {md:5.0f} m   max {mx:5.0f} m"
              + ("   <-- chosen" if k == best else ""))
    project = make(best)

    top = json.load(open(TOP))
    Q = np.array([[t["x"], t["y"]] for t in top["toponims"]], float)
    proj = project(Q)
    oob = 0
    for t, (lon, lat) in zip(top["toponims"], proj):
        if not (2.2 <= lon <= 3.55 and 39.2 <= lat <= 40.0):  # Mallorca-wide bbox
            oob += 1
        t["lon"], t["lat"] = round(float(lon), 6), round(float(lat), 6)
    if oob:
        print(f"   note: {oob} toponyms project outside the Mallorca bbox (extrapolation)")
    top["georef"] = {"model": best, "control_points": len(pts),
                     "loo_median_m": round(scores[best][0]), "sheet": g.get("sheet", "?")}
    json.dump(top, open(TOP, "w"), ensure_ascii=False, indent=1)
    json.dump({"model": best, "count": len(pts), "gcps": pts},
              open(GCPS_OUT, "w"), ensure_ascii=False, indent=1)
    print(f"✓ lon/lat written for {len(top['toponims'])} toponyms -> {TOP}")


if __name__ == "__main__":
    main()
