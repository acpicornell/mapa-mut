#!/usr/bin/env python3
"""In-sample poly2 residual per control point — a mislabeled dot shows as a lone
large residual against an otherwise smooth gradient.

  GCPS=data/toponims/se/gcps-se.json nix-shell scripts/toponims/mapkurator/shell.nix --run 'python3 scripts/toponims/mapkurator/gcp_residuals.py'
"""
import json
import math
import os

import numpy as np

g = json.load(open(os.environ["GCPS"]))
pts = [(*[p["x"], p["y"]], p["lng"], p["lat"], p["town"], k)
       for k in ("interior", "coast") for p in g.get(k, [])]
X = np.array([[p[0], p[1]] for p in pts], float)
LON = np.array([p[2] for p in pts])
LAT = np.array([p[3] for p in pts])


def design(xy):
    x, y = xy[:, 0], xy[:, 1]
    return np.column_stack([np.ones_like(x), x, y, x * x, x * y, y * y])


A = design(X)
clon, *_ = np.linalg.lstsq(A, LON, rcond=None)
clat, *_ = np.linalg.lstsq(A, LAT, rcond=None)
plon, plat = A @ clon, A @ clat

# meters per degree at ~39.5N
mlat = 111132.0
mlon = 111320.0 * math.cos(math.radians(39.5))
res = []
for i, p in enumerate(pts):
    dx = (plon[i] - LON[i]) * mlon
    dy = (plat[i] - LAT[i]) * mlat
    res.append((math.hypot(dx, dy), p[4], p[5]))
res.sort(reverse=True)
print(f"in-sample poly2 residuals ({len(pts)} pts), worst first:")
for r, town, kind in res:
    print(f"  {r:7.0f} m  {kind:8} {town}")
