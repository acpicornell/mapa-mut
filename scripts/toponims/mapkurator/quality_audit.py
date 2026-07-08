#!/usr/bin/env python3
"""Read-only quality audit of the per-sheet toponym notations.

Surfaces likely problems WITHOUT modifying anything:
  - truncation / fragment suspects (very short, lowercase, dangling tokens,
    a name that is a prefix of a near neighbour)
  - duplicates (same reading repeated; same NGIB reused; near-identical
    coordinates with similar names = probable double-detection)
  - junk (digits / odd characters / empty)
  - spatial outliers (georef position outside the Mallorca bbox)

Homonyms are real (two Bini, Son Sureda Vell/Nou…), so duplicates are only
REPORTED, never acted on. Writes a JSON report for later triage.
"""
import json, math, os, re, sys, unicodedata
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
QS = ["nw", "ne", "se", "sw"]
BBOX = (2.30, 3.55, 39.20, 40.10)  # lon_min, lon_max, lat_min, lat_max (Mallorca)

try:
    from rapidfuzz.distance import Levenshtein
    def ratio(a, b):
        return Levenshtein.normalized_similarity(a, b)
except Exception:
    import difflib
    def ratio(a, b):
        return difflib.SequenceMatcher(None, a, b).ratio()


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load():
    rows = []
    # Single-sheet map: one table under data/toponims/ (no quadrants).
    base = f"{ROOT}/data/toponims"
    topo = {t["id"]: t for t in json.load(open(f"{base}/toponims.json"))["toponims"]}
    try:
        cur = json.load(open(f"{base}/curation.json"))
    except FileNotFoundError:
        cur = {}
    try:
        matches = {m["id"]: m for m in json.load(open(f"{base}/matches.json"))}
    except FileNotFoundError:
        matches = {}
    if True:
        for tid, t in topo.items():
            c = cur.get(tid, {})
            if c.get("verdict") == "trash":
                continue  # already discarded by hand
            m = matches.get(tid, {})
            rows.append({
                "uid": tid, "q": "mut", "id": tid,
                "graf": t.get("graf", ""), "nom": t.get("nom", ""),
                "tipus": t.get("tipus", ""), "dubte": t.get("dubte", False),
                "x": t.get("x"), "y": t.get("y"), "subtile": t.get("subtile", ""),
                "lon": t.get("lon"), "lat": t.get("lat"),
                "decision": m.get("decision"), "ngib": m.get("ngib"),
                "municipi": m.get("municipi"), "km": m.get("km"),
                "review": m.get("review"),
            })
    return rows


def audit(rows):
    rep = defaultdict(list)

    # ---- junk / truncation per-row ----
    STOP = {"de", "den", "des", "del", "la", "el", "es", "sa", "so", "son", "can",
            "ca", "na", "ses", "els", "les", "puig", "coll", "cap", "pou", "font"}
    for r in rows:
        nom = (r["nom"] or "").strip()
        n = norm(nom)
        if not n:
            rep["empty"].append(r); continue
        if re.search(r"\d", nom):
            rep["has_digit"].append(r)
        if re.search(r"[^A-Za-zÀ-ÿ0-9 '·\-\.]", nom):
            rep["odd_char"].append(r)
        # truncation suspects: very short single token, or lowercase start, or dangling
        toks = n.split()
        if len(n) <= 3 and n not in STOP:
            rep["very_short"].append(r)
        if nom[:1].islower():
            rep["lower_start"].append(r)
        if re.search(r"[\-']$", nom) or re.search(r"^[\-']", nom):
            rep["dangling_edge"].append(r)
        if len(toks) == 1 and len(n) <= 4 and n not in STOP:
            rep["short_single"].append(r)

    # ---- exact duplicate readings (same normalized nom) ----
    bynom = defaultdict(list)
    for r in rows:
        n = norm(r["nom"])
        if n:
            bynom[n].append(r)
    for n, group in bynom.items():
        if len(group) > 1:
            rep["dup_nom"].append({"nom": n, "count": len(group),
                                   "items": [g["uid"] for g in group]})

    # ---- same NGIB reused across toponyms ----
    byngib = defaultdict(list)
    for r in rows:
        if r["ngib"]:
            byngib[norm(r["ngib"])].append(r)
    # A SHARED NGIB across DIFFERENT sheets with a far georef distance is a real match
    # error (not a legit homonym): the same NGIB record was assigned to labels that sit
    # km apart, so at least one pick is wrong. Flag those members (km >= 1.5).
    NGIB_FAR_KM = 1.5
    for g, group in byngib.items():
        if len(group) > 1:
            rep["dup_ngib"].append({"ngib": group[0]["ngib"], "count": len(group),
                                    "items": [{"uid": x["uid"], "nom": x["nom"],
                                               "km": x["km"], "municipi": x["municipi"]}
                                              for x in group]})
            if len({x["q"] for x in group}) > 1:          # spans >1 sheet
                for x in group:
                    if x["km"] is not None and x["km"] >= NGIB_FAR_KM:
                        rep["ngib_far"].append(x)

    # ---- near-identical coordinates with similar names (double-detection) ----
    # group by quadrant+subtile, compare pixel distance
    bytile = defaultdict(list)
    for r in rows:
        if r["x"] is not None:
            bytile[(r["q"], r["subtile"])].append(r)
    seen = set()
    for key, group in bytile.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                d = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5
                if d <= 40:
                    sim = ratio(norm(a["nom"]), norm(b["nom"]))
                    if sim >= 0.6:
                        pair = tuple(sorted((a["uid"], b["uid"])))
                        if pair in seen:
                            continue
                        seen.add(pair)
                        rep["near_dup"].append({"a": a["uid"], "anom": a["nom"],
                                                "b": b["uid"], "bnom": b["nom"],
                                                "px": round(d, 1), "sim": round(sim, 2)})

    # ---- cross-window near-duplicates (same name, very close, DIFFERENT spotter window) ----
    # The extraction windows don't overlap-read (each spotter box -> exactly one window),
    # but the interior (B) and coast (C) tracks can both pick up a coastal label. Flag
    # same-name points <600 m apart that come from a different window so they can be
    # adjudicated by hand. Legitimate homonyms (the two Bini, Son X Vell/Nou) get flagged
    # too — that's fine, the human decides; nothing is merged automatically.
    def _hav(a, b):
        R = 6371000.0
        la1, lo1, la2, lo2 = map(math.radians, [a["lat"], a["lon"], b["lat"], b["lon"]])
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        return 2 * R * math.asin(math.sqrt(h))
    byq = defaultdict(list)
    for r in rows:
        if r["lon"] is not None and r["lat"] is not None and norm(r["nom"]):
            byq[r["q"]].append(r)
    dup_hit = {}
    for qk, group in byq.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a["id"].split("_")[0] == b["id"].split("_")[0]:
                    continue  # same window -> legitimate distinct neighbours
                na, nb = norm(a["nom"]), norm(b["nom"])
                if len(na) < 3 or ratio(na, nb) < 0.85:
                    continue
                d = _hav(a, b)
                if d < 600:
                    cross = a["id"][0] != b["id"][0]  # interior (B) vs coast (C) track
                    dup_hit[a["uid"]] = a
                    dup_hit[b["uid"]] = b
                    rep["dup_near_pairs"].append({"a": a["uid"], "anom": a["nom"],
                                                  "b": b["uid"], "bnom": b["nom"],
                                                  "m": round(d), "cross_track": cross})
    rep["dup_near"] = list(dup_hit.values())

    # ---- spatial outliers ----
    for r in rows:
        if r["lon"] is None or r["lat"] is None:
            continue
        if not (BBOX[0] <= r["lon"] <= BBOX[1] and BBOX[2] <= r["lat"] <= BBOX[3]):
            rep["geo_outlier"].append(r)

    return rep


def main():
    rows = load()
    rep = audit(rows)
    slim = {"total": len(rows)}
    print(f"\n=== QUALITY AUDIT — {len(rows)} toponyms (trashed excluded) ===\n")
    order = ["empty", "very_short", "short_single", "lower_start", "dangling_edge",
             "has_digit", "odd_char", "dup_nom", "dup_ngib", "ngib_far", "near_dup",
             "dup_near", "geo_outlier"]
    DESC = {
        "empty": "buit (sense lectura)",
        "very_short": "molt curt (≤3) — possible truncat",
        "short_single": "token únic curt (≤4) — possible truncat",
        "lower_start": "comença en minúscula — possible fragment",
        "dangling_edge": "comença/acaba en - o '",
        "has_digit": "conté dígits",
        "odd_char": "caràcters estranys",
        "dup_nom": "lectures idèntiques repetides (pot ser homònim!)",
        "dup_ngib": "mateix NGIB reusat en ≥2 topònims",
        "ngib_far": "NGIB compartit entre fulls + km alt (match probablement erroni)",
        "near_dup": "coords quasi idèntiques + nom semblant (doble detecció)",
        "dup_near": "mateix nom + <600 m + finestra distinta (possible duplicat de pista)",
        "geo_outlier": "posició fora de Mallorca",
    }
    for k in order:
        v = rep.get(k, [])
        print(f"{len(v):>5}  {k:<14} {DESC[k]}")
        slim[k] = v
    # a few concrete examples for the eye
    def ex(k, n, fmt):
        v = rep.get(k, [])
        if not v:
            return
        print(f"\n  · {k} (mostra {min(n, len(v))}/{len(v)}):")
        for it in v[:n]:
            print("     " + fmt(it))
    ex("very_short", 12, lambda r: f'{r["uid"]:<10} "{r["nom"]}"  [{r["decision"]}] {r["municipi"] or ""}')
    ex("short_single", 12, lambda r: f'{r["uid"]:<10} "{r["nom"]}"  [{r["decision"]}]')
    ex("lower_start", 12, lambda r: f'{r["uid"]:<10} "{r["nom"]}"')
    ex("near_dup", 15, lambda p: f'{p["a"]} "{p["anom"]}"  ≈  {p["b"]} "{p["bnom"]}"  ({p["px"]}px, sim {p["sim"]})')
    ex("dup_ngib", 12, lambda d: f'{d["ngib"]:<22} ×{d["count"]}  ' + " · ".join(f'{i["uid"]}({i["nom"]})' for i in d["items"][:4]))
    # dup_near pairs (auxiliary list; the flagged entries are in rep["dup_near"])
    dnp = rep.get("dup_near_pairs", [])
    if dnp:
        ncross = sum(1 for p in dnp if p["cross_track"])
        print(f'\n  · dup_near_pairs (mostra {min(15, len(dnp))}/{len(dnp)}; {ncross} interior↔costa):')
        for p in sorted(dnp, key=lambda x: (not x["cross_track"], x["m"]))[:15]:
            tag = "B↔C" if p["cross_track"] else "   "
            print(f'     {tag} {p["m"]:>4}m  {p["a"]} "{p["anom"]}"  <>  {p["b"]} "{p["bnom"]}"')
    ex("geo_outlier", 10, lambda r: f'{r["uid"]:<10} "{r["nom"]}" lon={r["lon"]} lat={r["lat"]}')

    out = f"{ROOT}/data/toponims/quality_report.json"
    json.dump(slim, open(out, "w"), ensure_ascii=False, indent=1, default=str)

    # Flags per-entry for the curation tool. NOTATION problems + the ngib_far match
    # errors (cross-sheet shared NGIB at high km). Plain name/NGIB duplicates are still
    # NOT flagged — Mallorcan homonyms are legitimate — but ngib_far is a real mismatch.
    PROB = ["empty", "very_short", "short_single", "lower_start",
            "dangling_edge", "has_digit", "odd_char", "ngib_far", "dup_near"]
    flags = defaultdict(list)
    for k in PROB:
        for r in rep.get(k, []):
            flags[r["uid"]].append(k)
    fp = f"{ROOT}/data/toponims/quality_flags.json"
    json.dump(flags, open(fp, "w"), ensure_ascii=False, indent=1)
    print(f"\n✓ informe complet → {out}")
    print(f"✓ flags ({len(flags)} entrades) → {fp}\n")


if __name__ == "__main__":
    main()
