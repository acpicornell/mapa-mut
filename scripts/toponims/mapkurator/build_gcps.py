#!/usr/bin/env python3
"""Build the ground-control-point table for the single-sheet Mut 1683 map.

Ties each detected blue dot (dots-detected.json, in master pixel space) to the
town/cape engraved beside it — read by hand from the native crops — and resolves
its modern coordinate from the NGIB gazetteer (authoritative UIB names). Interior
municipality seats are the reliable anchors (NGIB tipus 917 municipi / 3010
nucli); coastal capes (tipus 3027) are kept apart as lower-trust points because
the 1683 coastline is drawn loosely — georef_sheet.py only uses them with
--with-coast.

  nix develop --command python3 scripts/toponims/mapkurator/build_gcps.py

Writes data/toponims/gcps.json  (schema consumed by georef_sheet.py).
"""
import json
import os
import unicodedata

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DOTS = os.path.join(ROOT, "data/toponims/dots-detected.json")
NGIB = os.path.join(ROOT, "data/toponims/ngib/llocs.json")
OUT = os.path.join(ROOT, "data/toponims/gcps.json")

# dot number -> (town label, kind, NGIB grafia to resolve). Read by hand from the
# native gcp-crops/dotNN.jpg. "interior" = municipi seat (immutable); "coast" =
# cape drawn in the sea (lower trust).
DOT_TOWN = {
    1:  ("Cap de ses Salines", "coast",    "Cap de ses Salines"),
    2:  ("Santanyí",           "interior", "Santanyí"),
    3:  ("Capdepera",          "coast",    "Capdepera"),
    4:  ("Manacor",            "interior", "Manacor"),
    5:  ("Campos",             "interior", "Campos"),
    6:  ("Artà",               "interior", "Artà"),
    7:  ("Porreres",           "interior", "Porreres"),
    8:  ("Cap Blanc",          "coast",    "Cap Blanc"),
    9:  ("Cap de Ferrutx",     "coast",    "Cap de Ferrutx"),
    10: ("Sineu",              "interior", "Sineu"),
    11: ("Marratxí",           "interior", "Marratxí"),
    12: ("Cap de Cala Figuera", "coast",   "Cap de Cala Figuera"),
    13: ("Cap des Pinar",      "coast",    "Cap des Pinar"),
    14: ("Alcúdia",            "interior", "Alcúdia"),
    15: ("Palma",              "interior", "Palma"),
    16: ("Cap de Formentor",   "coast",    "Cap de Formentor"),
    17: ("Pollença",           "interior", "Pollença"),
    18: ("Sóller",             "interior", "Sóller"),
    19: ("Valldemossa",        "interior", "Valldemossa"),
}

# NGIB tipus preference: populated place (917 municipi, 3010 nucli) for interior,
# cape (3027) for coast.
TIPUS_PREF = {"interior": [917, 3010], "coast": [3027]}


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower())
                   if unicodedata.category(c) != "Mn")


def resolve(name, kind, ngib):
    n = norm(name)
    hits = [x for x in ngib if norm(x["grafia"]) == n]
    if not hits:
        raise SystemExit(f"NGIB: no match for {name!r}")
    for tp in TIPUS_PREF[kind]:
        for x in hits:
            if x["tipus"] == tp:
                return x
    return hits[0]  # fall back to any match


def main():
    det = json.load(open(DOTS))
    ngib = json.load(open(NGIB))
    by_n = {d["n"]: d for d in det["dots"]}

    interior, coast = [], []
    for n, (town, kind, grafia) in sorted(DOT_TOWN.items()):
        if n not in by_n:
            raise SystemExit(f"dot {n} not found in {DOTS}")
        d = by_n[n]
        rec = resolve(grafia, kind, ngib)
        entry = {"n": n, "x": d["x"], "y": d["y"], "town": town,
                 "lng": rec["lng"], "lat": rec["lat"], "src": "ngib",
                 "ngib_tipus": rec["tipus"]}
        (interior if kind == "interior" else coast).append(entry)

    out = {"sheet": "mut-1683", "crop": det.get("dots_src"),
           "crop_dims": det["crop_dims"],
           "interior": interior, "coast": coast}
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"✓ {len(interior)} interior + {len(coast)} coast GCPs -> "
          f"{os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
