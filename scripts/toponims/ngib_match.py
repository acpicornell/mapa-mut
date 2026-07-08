#!/usr/bin/env python3
"""Match the AI-read Despuig toponyms against the NGIB gazetteer.

Validates readings, normalises spellings (UIB grafia) and clears "dubte" flags.

Pipeline:
  1. Georeference: build a pixel -> lon/lat transform from the well-identified
     nuclis (matched to the curated towns in src/data/pobles.json). We compare a
     robust 2nd-order polynomial against a smoothing thin-plate spline and keep
     whichever has the lower leave-one-out error.
  2. Project every toponym to approximate modern coordinates.
  3. For each toponym, search NGIB neighbours with a cKDTree and score candidates
     with rapidfuzz (token_set_ratio / WRatio) plus a phonetic (metaphone) bonus,
     gated by distance. Classify into confirmat / suggerit / posicional / sense.

Run inside the Nix env:
  nix-shell scripts/toponims/shell.nix --run "python3 scripts/toponims/ngib_match.py"

Writes data/toponims/ngib/matches.json (no mutation of the source cells).
"""
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from rapidfuzz import fuzz, process
from scipy.interpolate import RBFInterpolator
from scipy.spatial import cKDTree
import jellyfish
from unidecode import unidecode

ROOT = Path(__file__).resolve().parents[2]
load = lambda p: json.loads((ROOT / p).read_text())
# parallel B-track support (defaults = A); paths are relative to ROOT
TOP_REL = os.environ.get("TOPONIMS_JSON", "data/toponims/toponims.json")
MATCHES_REL = os.environ.get("MATCHES_JSON", "data/toponims/ngib/matches.json")
RECHECK_REL = os.environ.get("RECHECK_JSON", "data/toponims/recheck.json")
PICKS_REL = os.environ.get("PICKS_JSON", "data/toponims/recheck-picks.json")
REVIEWED_REL = os.environ.get("REVIEWED_JSON", "data/toponims/review-reviewed.json")
DISCARDS_REL = os.environ.get("DISCARDS_JSON", "data/toponims/discards.json")

toponims = load(TOP_REL)["toponims"]
ngib = load("data/toponims/ngib/llocs.json")

# ---------- text normalisation ----------
ARTICLES = {"de", "del", "dels", "des", "la", "el", "els", "les", "es", "sa", "ses",
            "sos", "s", "d", "l", "na", "en", "lo", "y", "i",
            "los", "las"}  # incl. the "des" (de+es) contraction and Spanish articles


def norm(s: str) -> str:
    s = unidecode(s or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def core(s: str) -> str:
    """Normalised string with articles dropped (keeps son/can/cas/sant)."""
    return " ".join(t for t in norm(s).split() if t not in ARTICLES)


def metaphone_key(s: str) -> str:
    return " ".join(jellyfish.metaphone(t) for t in core(s).split() if len(t) > 2)


def fold(s: str) -> str:
    """Canonicalise 18th-c Mallorquí engraving spelling toward the modern NGIB
    grafia, so systematic orthographic differences stop costing similarity:
    ll<->y (Mayol/Mallol), h-drop (Buch/Buc), v->b, ç/ss->s, palatal tx/ig/tj->x,
    and collapsed double letters. Conservative on purpose (no c->s, which would
    merge Can/San) — applied to BOTH sides so it only rewards true variants."""
    s = core(s).replace("ny", "n").replace("ll", "y")
    for a, b in (("tx", "x"), ("itj", "x"), ("ig", "x"), ("ç", "s"),
                 ("ss", "s"), ("v", "b"), ("h", "")):
        s = s.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", s)


def similarity(read: str, grafia: str) -> float:
    """0..1 fuzzy similarity.

    token_sort_ratio (not token_set_ratio): it handles word reordering but still
    PENALISES extra/missing tokens, so a name is not a perfect match to a longer
    NGIB entry that merely contains it ("Camí de X", "Racó de X", "Avenc de X").
    A phonetic (metaphone) pass catches historic spelling variants.
    """
    a, b = core(read), core(grafia)
    if not a or not b:
        return 0.0
    base = fuzz.token_sort_ratio(a, b) / 100.0
    # Distinctive single-token containment: a short map label (e.g. "Santueri") for a
    # place the gazetteer only lists in full ("Castell de Santueri"). Restricted to a
    # long, specific token so generic words inside longer names are not matched.
    if len(a) >= 6 and " " not in a and a in b.split():
        base = max(base, 0.86)
    # Orthographic + phonetic passes only REFINE an already-plausible literal match;
    # they must not rescue distant strings (e.g. Gomà/Coma share metaphone KM).
    if base >= 0.70:
        fa, fb = fold(read), fold(grafia)
        if fa and fb:
            orth = fuzz.token_sort_ratio(fa, fb) / 100.0
            base = max(base, 0.5 * base + 0.5 * orth)
        ma, mb = metaphone_key(read), metaphone_key(grafia)
        if ma and mb:
            phon = fuzz.token_sort_ratio(ma, mb) / 100.0
            base = max(base, 0.5 * base + 0.5 * phon)
    return base


# ---------- local planar projection (metres) ----------
# Local equirectangular projection origin = centre of the NGIB gazetteer (Mallorca).
LAT0 = float(np.mean([p["lat"] for p in ngib]))
LON0 = float(np.mean([p["lng"] for p in ngib]))
KX = 111320.0 * math.cos(math.radians(LAT0))
KY = 110540.0


def to_m(lng, lat):
    return np.array([(np.asarray(lng) - LON0) * KX, (np.asarray(lat) - LAT0) * KY]).T


def to_lonlat(mx, my):
    return mx / KX + LON0, my / KY + LAT0


# ---------- projection: precomputed exact-dot georeference ----------
# scripts/toponims/mapkurator/georef.py writes lon/lat per toponym from the user's
# EXACT town points (global thin-plate spline, every town honoured exactly). Here
# we only convert those coordinates into the local metric frame.
if not all("lon" in t and "lat" in t for t in toponims):
    raise SystemExit("toponims.json lacks lon/lat — run "
                     "scripts/toponims/mapkurator/georef.py first")
GEOREF = load(TOP_REL).get("georef", {})
proj = to_m([t["lon"] for t in toponims], [t["lat"] for t in toponims])

# ---------- NGIB spatial index ----------
ngib_m = to_m([g["lng"] for g in ngib], [g["lat"] for g in ngib])
tree = cKDTree(ngib_m)

# ---------- match ----------
# The georeference is imperfect near the map frame and the 4-sheet gutter, so a
# purely distance-gated match drops obvious names (e.g. SINEU, POLLENSA) whose
# projection lands far from the real place. We widen the search radius and add a
# "name-first" rule: a near-exact name match is trusted even when the distance is
# loose, plus a whole-corpus fallback when the projection finds nothing nearby.
RADIUS_M = 12000.0
# Positional confirmation: a candidate landing on top of the projection (the georef
# is ~1 km accurate) with a solid name IS the place, even for a homonym — same-named
# estates sit farther apart, so the close hit disambiguates which one. Two tiers,
# calibrated on the data: right on the spot (<1 km) a decent name (0.82) suffices;
# a bit farther (<1.5 km) needs a stronger name (0.85). Below ~0.82 real errors
# appear (Son Jaume Andreu -> Son Pere Andreu) even when close.
POS_NEAR, POS_NEAR_SIM = 1000.0, 0.82
POS_FAR, POS_FAR_SIM = 1500.0, 0.85
matches, counts = [], {"confirmat": 0, "probable": 0, "suggerit": 0, "posicional": 0, "sense": 0}

ngib_core = [core(g["grafia"]) for g in ngib]  # precomputed keys for the global fallback
# Distinct municipalities per name: a name in ONE municipi is a single place (safe to
# trust by name alone); the same name across SEVERAL is a homonym (needs position).
ngib_municipis = defaultdict(set)
for _g in ngib:
    ngib_municipis[core(_g["grafia"])].add(_g.get("municipi"))


def n_municipis(grafia):
    return len(ngib_municipis.get(core(grafia), ()))


def classify(unique, sim, dist):
    """Confidence tier for a chosen match (mirrors the main ladder below).
    dist in metres, or None when there is no position. Used both for the
    algorithmic pass and to RE-derive the confidence of a human pick — so the
    `decision` axis stays purely algorithmic; human action lives in `review`."""
    if dist is None:
        return "confirmat" if (unique and sim >= 0.95) else "suggerit"
    if unique and sim >= 0.88 and dist <= 6000:
        return "confirmat"
    if sim >= 0.90 and dist <= 5000:
        return "confirmat"
    if (dist <= POS_NEAR and sim >= POS_NEAR_SIM) or (dist <= POS_FAR and sim >= POS_FAR_SIM):
        return "probable"
    if unique and sim >= 0.70:
        return "suggerit"
    if sim >= 0.70 and dist <= 8000:
        return "suggerit"
    if dist <= 1500 and sim >= 0.45:
        return "posicional"
    return "posicional"

for t, pm in zip(toponims, proj):
    near = tree.query_ball_point(pm, RADIUS_M)
    best = None       # best by combined score (similarity minus distance penalty)
    best_name = None  # best by name similarity alone: (g, s, d)
    best_close = None  # best candidate that meets a positional-confirm tier: (g, s, d)
    for j in near:
        g = ngib[j]
        d = math.hypot(*(ngib_m[j] - pm))
        s = max(similarity(t["nom"], g["grafia"]), similarity(t.get("graf", ""), g["grafia"]))
        score = s - d / 60000.0
        if best is None or score > best[0]:
            best = (score, s, d, g)
        if best_name is None or s > best_name[1]:
            best_name = (g, s, d)
        if ((d <= POS_NEAR and s >= POS_NEAR_SIM) or (d <= POS_FAR and s >= POS_FAR_SIM)) \
                and (best_close is None or s > best_close[1]):
            best_close = (g, s, d)

    # Tiered decision. Distance only DISAMBIGUATES homonyms, never discards a unique
    # name. Confidence ladder:
    #   confirmat  the NAME is (near-)certain  (unique distinctive name, OR a homonym
    #              whose name AND position are both strong);
    #   probable   the POSITION is certain and the name is a looser variant — the
    #              quasi-sure tier (close hit, spelling differs from the gazetteer);
    #   suggerit   plausible, needs a look;
    #   posicional only a position, the reading is too weak to name;
    #   sense      no match.
    uniq_name = best_name and n_municipis(best_name[0]["grafia"]) <= 1
    decision, chosen = "sense", None  # chosen = (g, sim, dist_or_None)
    if uniq_name and best_name[1] >= 0.88 and best_name[2] <= 6000:
        decision, chosen = "confirmat", best_name                     # unique distinctive name
    elif best and best[1] >= 0.90 and best[2] <= 5000:
        decision, chosen = "confirmat", (best[3], best[1], best[2])   # homonym: name + position strong
    elif best_close:
        decision, chosen = "probable", best_close                    # position nails it, name a variant
    elif uniq_name and best_name[1] >= 0.70:
        decision, chosen = "suggerit", best_name                     # unique, moderate (any distance)
    elif best and best[1] >= 0.70 and best[2] <= 8000:
        decision, chosen = "suggerit", (best[3], best[1], best[2])   # homonym, moderate
    elif best and best[2] <= 1500 and best[1] >= 0.45:
        decision, chosen = "posicional", (best[3], best[1], best[2])  # position only, weak name
    if decision == "sense":
        # Whole-corpus fallback for names the georef threw beyond the search radius.
        # No position to disambiguate -> a near-exact unique name is trusted; an
        # ambiguous one stays a suggestion.
        key = core(t["nom"])
        hit = process.extractOne(key, ngib_core, scorer=fuzz.token_sort_ratio) if key else None
        if hit and hit[1] / 100.0 >= 0.92 and len(key) >= 5:
            g = ngib[hit[2]]
            s = hit[1] / 100.0
            unique = n_municipis(g["grafia"]) <= 1
            # No position at all here, so only a near-exact unique name is trusted;
            # everything else is a suggestion.
            decision = "confirmat" if (unique and s >= 0.95) else "suggerit"
            chosen = (g, s, None)

    counts[decision] += 1
    g = chosen[0] if chosen else None
    matches.append({
        "id": t["id"], "nom": t["nom"], "graf": t.get("graf"), "tipus": t["tipus"],
        "ordre": t.get("ordre"),
        "dubte": bool(t.get("dubte")), "decision": decision, "review": None,
        "ngib": g["grafia"] if g else None,
        "municipi": g["municipi"] if g else None,
        "sim": round(chosen[1], 2) if chosen else 0.0,
        "km": (round(chosen[2] / 1000, 2) if chosen and chosen[2] is not None else None),
    })

# ---------- TWO AXES: decision = algorithmic confidence; review = human layer ----------
# The matching above already set `decision` (confidence) for every toponym. The human
# curation files are applied here on a SEPARATE, orthogonal axis `review` so re-running
# the algorithm never destroys the confidence info (TEI @cert / @resp model):
#   review = 'revisat'   a human confirmed the match (verdict 'ok', or a pick that keeps
#                        the algorithmic match) — or confirmed there is no match ('none').
#            'corregit'  a human CHANGED the match (picked a different NGIB place).
#            'descartat' a human marked it garbage (discards) — then dropped from output.
#            None        not reviewed.
# Picks/'none' still re-set the MATCH (and its recomputed `decision`), but a verified
# item keeps its honest algorithmic confidence — the public combines the two axes.
# Single curation overlay (CURATION_JSON) is the source of all hand edits; a record
# is {graf?, tipus?, ngib?, verdict?}. We derive the three signals the matcher needs
# (picks = the chosen NGIB place, reviewed = the human verdict, discards = trash).
# Falls back to the legacy 3-file layout when CURATION_JSON is unset.
CURATION_REL = os.environ.get("CURATION_JSON")
if CURATION_REL:
    cur_file = ROOT / CURATION_REL
    cur = json.loads(cur_file.read_text()) if cur_file.exists() else {}
    picks = {i: r["ngib"] for i, r in cur.items() if r.get("ngib")}
    reviewed = {i: r["verdict"] for i, r in cur.items() if r.get("verdict")}
    discards = {i for i, r in cur.items() if r.get("verdict") == "trash"}
else:
    reviewed_file = ROOT / REVIEWED_REL
    reviewed = json.loads(reviewed_file.read_text()) if reviewed_file.exists() else {}
    picks_file = ROOT / PICKS_REL
    picks = json.loads(picks_file.read_text()) if picks_file.exists() else {}
    discards_file = ROOT / DISCARDS_REL
    discards = set(json.loads(discards_file.read_text())) if discards_file.exists() else set()

manual = {k for k, v in reviewed.items() if v == "pick"}
verified_ok = {k for k, v in reviewed.items() if v == "ok"}
nomatch = {k for k, v in reviewed.items() if v == "none"}

if picks:
    proj_by_id = {t["id"]: pm for t, pm in zip(toponims, proj)}
    by_name = defaultdict(list)
    for gi, g in enumerate(ngib):
        by_name[core(g["grafia"])].append(gi)
    orig_ngib = {m["id"]: m.get("ngib") for m in matches}
    applied = 0
    for m in matches:
        gra = picks.get(m["id"])
        if not gra or m["id"] not in proj_by_id:
            continue
        cand = by_name.get(core(gra))
        if not cand:
            continue
        pm = proj_by_id[m["id"]]
        gi = min(cand, key=lambda j: math.hypot(*(ngib_m[j] - pm)))
        g = ngib[gi]
        dist = math.hypot(*(ngib_m[gi] - pm))
        sim = round(max(similarity(m["nom"], g["grafia"]),
                        similarity(m.get("graf") or "", g["grafia"])), 2)
        unique = n_municipis(g["grafia"]) <= 1
        m.update(decision=classify(unique, sim, dist), ngib=g["grafia"],
                 municipi=g["municipi"], km=round(dist / 1000, 2), sim=sim)
        if m["id"] in manual:   # a hand pick is human review; auto vision picks are not
            m["review"] = "revisat" if core(gra) == core(orig_ngib.get(m["id"]) or "") else "corregit"
        applied += 1
    print(f"Picks applied (match re-set + confidence recomputed): {applied}")

# human verdicts: 'ok' = match verified (confidence unchanged, just flag review);
# 'none' = human confirms NO NGIB match exists -> sense, but still a human verdict.
ok_n = nm_n = 0
for m in matches:
    if m["id"] in verified_ok and m.get("ngib"):
        m["review"] = "revisat"; ok_n += 1
    elif m["id"] in nomatch:
        m.update(decision="sense", ngib=None, municipi=None, km=None, sim=None, review="revisat"); nm_n += 1
if ok_n or nm_n:
    print(f"Human verdicts: {ok_n} verified-ok, {nm_n} no-match")

# drop hand-discarded toponyms (brossa), then (re)compute the confidence counts
if discards:
    before = len(matches)
    matches = [m for m in matches if m["id"] not in discards]
    print(f"Discarded (brossa): {before - len(matches)}")
counts = dict(Counter(m["decision"] for m in matches))
for k in ("confirmat", "probable", "suggerit", "posicional", "sense"):
    counts.setdefault(k, 0)
review_counts = dict(Counter(m["review"] for m in matches if m["review"]))
if review_counts:
    print("Review (human): " + ", ".join(f"{k} {v}" for k, v in sorted(review_counts.items())))

(ROOT / MATCHES_REL).write_text(json.dumps(matches, ensure_ascii=False, indent=1))

# ---------- candidate lists for the vision recheck ----------
# For everything not auto-confirmed, dump the nearest gazetteer names so a vision
# pass can read the engraving and pick the right one (or none).
decision_by_id = {m["id"]: m["decision"] for m in matches}
review_by_id = {m["id"]: m["review"] for m in matches}
recheck = []
for t, pm in zip(toponims, proj):
    if t["id"] in discards or decision_by_id.get(t["id"]) == "confirmat" or review_by_id.get(t["id"]):
        continue
    scored = []
    for j in tree.query_ball_point(pm, RADIUS_M):
        g = ngib[j]
        d = math.hypot(*(ngib_m[j] - pm))
        s = max(similarity(t["nom"], g["grafia"]), similarity(t.get("graf", ""), g["grafia"]))
        scored.append((s - d / 60000.0, s, d, g))
    scored.sort(key=lambda r: r[0], reverse=True)
    cands = [{"grafia": g["grafia"], "municipi": g["municipi"], "km": round(d / 1000, 2), "sim": round(s, 2)}
             for _, s, d, g in scored[:6]]
    recheck.append({"id": t["id"], "graf": t.get("graf"), "nom": t["nom"], "tipus": t["tipus"],
                    "subtile": t["subtile"], "x": t["x"], "y": t["y"],
                    "decision": decision_by_id.get(t["id"]), "candidates": cands})
(ROOT / RECHECK_REL).write_text(json.dumps(recheck, ensure_ascii=False, indent=1))
print(f"Recheck candidates written: {len(recheck)} items -> {RECHECK_REL}")

# ---------- report ----------
dub = [t for t in toponims if t.get("dubte")]
resolved = [m for m in matches if m["dubte"] and m["decision"] == "confirmat"]
print(f"\nGeoreference (precomputed, exact town dots): "
      f"{GEOREF.get('control_points', '?')} control points, "
      f"model={GEOREF.get('model', '?')}, median error (LOO) "
      f"{GEOREF.get('loo_median_m', '?')} m\n")
print(f"Toponyms: {len(toponims)}  |  current doubts: {len(dub)}")
print("NGIB classification (confidence):")
for k in ("confirmat", "probable", "suggerit", "posicional", "sense"):
    print(f"  {k:<11} {counts[k]}")
print(f"\nDoubts a 'confirmat' match would resolve: {len(resolved)}")
print("\nSample confirmed corrections (AI reading -> NGIB):")
shown = 0
for m in matches:
    if m["decision"] == "confirmat" and core(m["nom"]) != core(m["ngib"]):
        _tp = m["tipus"][0] if isinstance(m["tipus"], list) and m["tipus"] else (m["tipus"] or "")
        print(f"  [{str(_tp)[:4]}] \"{m['nom']}\"  ->  \"{m['ngib']}\"  "
              f"(sim {m['sim']}, {m['km']} km, {m['municipi'] or '?'})")
        shown += 1
        if shown >= 25:
            break
print(f"\n✓ {MATCHES_REL}")
