#!/usr/bin/env python3
"""EXPERIMENT (report-only): refit the sheet transform using the many NGIB-confirmed
toponyms as dense ground control, instead of just the ~14 hand-marked dots.

Each confirmat toponym gives a tie point: its engraving pixel (x,y) ↔ the true
NGIB coord of the place it matched. We use only UNIQUE-name matches (no homonym →
no circularity with the initial transform), fit a polynomial with iterative robust
outlier rejection (drops bad matches / large label offsets), and VALIDATE by
predicting the hand-marked interior dots, which are held entirely out of the fit.

  Q=se nix-shell scripts/toponims/mapkurator/shell.nix --run 'python3 scripts/toponims/mapkurator/georef_refine.py'
"""
import json
import math
import os

import numpy as np

Q = os.environ["Q"].lower()
ORDER = int(os.environ.get("ORDER", "2"))
ROOT = "."
top = json.load(open(f"{ROOT}/data/toponims/{Q}/toponims.json"))["toponims"]
mm = json.load(open(f"{ROOT}/data/toponims/{Q}/matches.json"))
matches = mm if isinstance(mm, list) else mm["matches"]
llocs = json.load(open(f"{ROOT}/data/toponims/ngib/llocs.json"))
gcps = json.load(open(f"{ROOT}/data/toponims/{Q}/gcps-{Q}.json"))

MLAT = 111132.0
MLON = 111320.0 * math.cos(math.radians(39.5))


def norm(s):
    s = (s or "").lower()
    out = []
    for ch in s:
        import unicodedata
        if unicodedata.category(ch).startswith("M"):
            continue
        out.append(ch)
    s = "".join(unicodedata.normalize("NFD", c) for c in s)
    s = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
    return "".join(c for c in s if c.isalnum() or c == " ").strip()


# unique NGIB grafia -> coord
from collections import defaultdict
by = defaultdict(list)
for x in llocs:
    by[norm(x["grafia"])].append((x["lng"], x["lat"]))

posById = {t["id"]: (t["x"], t["y"]) for t in top}

tie = []
for m in matches:
    if m.get("decision") != "confirmat" or not m.get("ngib"):
        continue
    cand = by.get(norm(m["ngib"]))
    if not cand or len(cand) != 1:           # unique names only
        continue
    if m["id"] not in posById:
        continue
    x, y = posById[m["id"]]
    lng, lat = cand[0]
    tie.append((x, y, lng, lat))

tie = np.array(tie, float)


def design(xy, order):
    x, y = xy[:, 0], xy[:, 1]
    cols = [np.ones_like(x)]
    for d in range(1, order + 1):
        for i in range(d + 1):
            cols.append((x ** (d - i)) * (y ** i))
    return np.column_stack(cols)


def fit(xy, lon, lat, order):
    A = design(xy, order)
    clon = np.linalg.lstsq(A, lon, rcond=None)[0]
    clat = np.linalg.lstsq(A, lat, rcond=None)[0]
    return clon, clat


def predict(xy, clon, clat, order):
    A = design(xy, order)
    return A @ clon, A @ clat


def resid_m(xy, lon, lat, clon, clat, order):
    plon, plat = predict(xy, clon, clat, order)
    return np.hypot((plon - lon) * MLON, (plat - lat) * MLAT)


# iterative robust fit
xy = tie[:, :2]
lon = tie[:, 2]
lat = tie[:, 3]
keep = np.ones(len(tie), bool)
for it in range(8):
    clon, clat = fit(xy[keep], lon[keep], lat[keep], ORDER)
    r = resid_m(xy, lon, lat, clon, clat, ORDER)
    med = np.median(r[keep])
    thr = max(2.5 * med, 350.0)
    newkeep = r <= thr
    if (newkeep == keep).all():
        keep = newkeep
        break
    keep = newkeep

clon, clat = fit(xy[keep], lon[keep], lat[keep], ORDER)
r = resid_m(xy, lon, lat, clon, clat, ORDER)
print(f"[{Q}] order{ORDER} tie points: {len(tie)} unique-confirmat, kept {keep.sum()} (dropped {(~keep).sum()})")
print(f"      in-sample residual on kept:  median {np.median(r[keep]):.0f} m   p90 {np.percentile(r[keep],90):.0f} m")

# VALIDATION: predict the hand-marked interior dots (held out of this fit)
dots = gcps.get("interior", [])
dxy = np.array([[d["x"], d["y"]] for d in dots], float)
dlon = np.array([d["lng"] for d in dots])
dlat = np.array([d["lat"] for d in dots])
dr = resid_m(dxy, dlon, dlat, clon, clat, ORDER)
print(f"      ↳ predicting the {len(dots)} hand dots (out-of-sample): median {np.median(dr):.0f} m   max {dr.max():.0f} m")
order = np.argsort(dr)[::-1]
for i in order[:4]:
    print(f"         {dr[i]:6.0f} m  {dots[i]['town']}")

if os.environ.get("APPLY") == "1":
    # Final model: kept unique-confirmat tie points + ALL hand dots (precise
    # anchors, interior+coast), refit robustly, then re-project EVERY toponym.
    alldots = gcps.get("interior", []) + gcps.get("coast", [])
    cxy = np.vstack([xy[keep], np.array([[d["x"], d["y"]] for d in alldots], float)])
    clon_f = lon[keep].tolist() + [d["lng"] for d in alldots]
    clat_f = lat[keep].tolist() + [d["lat"] for d in alldots]
    cxy = np.array(cxy, float)
    clonv = np.array(clon_f)
    clatv = np.array(clat_f)
    kp = np.ones(len(cxy), bool)
    for it in range(8):
        cl, ca = fit(cxy[kp], clonv[kp], clatv[kp], ORDER)
        rr = resid_m(cxy, clonv, clatv, cl, ca, ORDER)
        nk = rr <= max(2.5 * np.median(rr[kp]), 350.0)
        nk[len(xy[keep]):] = True          # never drop the hand dots
        if (nk == kp).all():
            break
        kp = nk
    cl, ca = fit(cxy[kp], clonv[kp], clatv[kp], ORDER)
    tj = json.load(open(f"{ROOT}/data/toponims/{Q}/toponims.json"))
    P = np.array([[t["x"], t["y"]] for t in tj["toponims"]], float)
    plon, plat = predict(P, cl, ca, ORDER)
    for i, t in enumerate(tj["toponims"]):
        t["lon"] = round(float(plon[i]), 6)
        t["lat"] = round(float(plat[i]), 6)
    tj["georef"] = {"method": f"poly{ORDER}-dense", "control": int(kp.sum()),
                    "from": "unique-confirmat tie points + hand dots", "dot_loo_m": round(float(np.median(dr)))}
    json.dump(tj, open(f"{ROOT}/data/toponims/{Q}/toponims.json", "w"), ensure_ascii=False, indent=1)
    print(f"      ✓ APPLIED: re-projected {len(tj['toponims'])} toponyms with poly{ORDER}-dense ({kp.sum()} control)")
