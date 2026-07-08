#!/usr/bin/env python3
"""Convert our per-sheet GCP files into QGIS Georeferencer .points files.

For each data/toponims/<q>/gcps-<q>.json it writes a sidecar
    <crop>.points
next to the canvas crop the GCPs were measured on, so opening that raster in
the QGIS Georeferencer auto-loads every control point (no hand-clicking).

QGIS .points format (CSV):
    mapX,mapY,sourceX,sourceY,enable,dX,dY,residual
where mapX/mapY are the target CRS coords (EPSG:4326 lng/lat here) and
sourceY is the NEGATIVE pixel row (QGIS stores raster Y as -row).

Run:  nix-shell -p python3 --run 'python3 scripts/toponims/mapkurator/gcps_to_qgis_points.py'
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
QUADS = ["nw", "ne", "se", "sw"]


def rows_from(gcps):
    """Yield (lng, lat, x, y, enable, group) for interior + coast dots."""
    for pt in gcps.get("interior", []):
        yield pt["lng"], pt["lat"], pt["x"], pt["y"], 1, "interior"
    # coastal capes are lower trust -> loaded but DISABLED (enable=0); tick them
    # in the GUI if you want a tighter warp.
    for pt in gcps.get("coast", []):
        yield pt["lng"], pt["lat"], pt["x"], pt["y"], 0, "coast"


def main():
    for q in QUADS:
        src = os.path.join(ROOT, "data", "toponims", q, f"gcps-{q}.json")
        if not os.path.exists(src):
            print(f"skip {q}: no {src}")
            continue
        with open(src) as fh:
            gcps = json.load(fh)
        crop = os.path.join(ROOT, gcps["crop"])
        if not os.path.exists(crop):
            # some sheets store a bare filename; the real crop lives in data/jpg/<Q>/
            alt = os.path.join(ROOT, "data", "jpg", q.upper(), os.path.basename(gcps["crop"]))
            if os.path.exists(alt):
                crop = alt
        out = crop + ".points"
        lines = ["mapX,mapY,sourceX,sourceY,enable,dX,dY,residual"]
        n_i = n_c = 0
        for lng, lat, x, y, enable, group in rows_from(gcps):
            lines.append(f"{lng},{lat},{x},{-y},{enable},0,0,0")
            if group == "interior":
                n_i += 1
            else:
                n_c += 1
        with open(out, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"{q.upper()}: {n_i} interior + {n_c} coast -> {out}")
        print(f"     raster: {crop}  (exists={os.path.exists(crop)})")


if __name__ == "__main__":
    main()
