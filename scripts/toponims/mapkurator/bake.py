#!/usr/bin/env python3
"""Single bake step for one quadrant. Applies the hand-curation overlay
(curation.json) onto the toponym table, then re-runs the NGIB match. This is the
ONE command to run after editing a sheet in the review tool — it replaces the old
apply_graf_fixes.py + multi-env ngib_match.py dance.

  nix-shell scripts/toponims/shell.nix --run \
    "python3 scripts/toponims/mapkurator/bake.py ne"

curation.json is the SINGLE source of hand edits (one record per toponym id):
  { "B01_1": { "graf": "...", "tipus": "...", "ngib": "...", "verdict": "ok|pick|none|trash" } }
  - graf   rewrites the reading (re-derives nom + tipus)
  - tipus  overrides the type (wins over the derived one)
  - ngib   the picked NGIB place (re-sets the match)
  - verdict the human action -> feeds the orthogonal `review` axis; 'trash' drops it
Position is untouched, so only the match is recomputed (no re-georef).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import b_assemble as ba

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
NGIB_MATCH = os.path.join(os.path.dirname(HERE), "ngib_match.py")
# Hand-picked tipus from the curation tool = the 8 classes of the Mut 1683 legend
# ("Notarū Explicatio") + "altre".
VALID_TIPUS = set(ba.MUT_TIPUS)
# The Mut legend has no religious-order axis (that was despuig's 1785 map), so the
# `ordre` field is unused here.
VALID_ORDRES = set()


def _norm_multi(v, valid):
    """Overlay tipus/ordre may be a string or a list (multi-value). Keep only legal
    values; return None if empty, a bare string if one, a list if several."""
    if v is None:
        return None
    items = v if isinstance(v, list) else [v]
    items = [x for x in items if x in valid]
    if not items:
        return None
    return items[0] if len(items) == 1 else items


def apply_overlay(top_path, cur):
    """Rewrite graf/nom/tipus in toponims.json from the curation overlay. Idempotent:
    re-running with the same overlay is a no-op (only changed fields are touched)."""
    top = json.load(open(top_path))
    ng = nt = no = 0
    for t in top["toponims"]:
        c = cur.get(t["id"], {})
        g = (c.get("graf") or "").strip()
        if g and g != t["graf"]:
            k = ba.key(g)
            t["graf"] = g
            t["nom"] = ba.TOWNS.get(k) or ba.normalize_nom(g)
            t["tipus"] = ba.tipus_for(g, k)
            ng += 1
        tp = _norm_multi(c.get("tipus"), VALID_TIPUS)   # hand tipus (multi) wins over the derived one
        if tp is not None and tp != t.get("tipus"):
            t["tipus"] = tp
            nt += 1
        od = _norm_multi(c.get("ordre"), VALID_ORDRES)  # axis 2: religious order(s), overlay only
        if od is not None and t.get("ordre") != od:
            t["ordre"] = od
            no += 1
    json.dump(top, open(top_path, "w"), ensure_ascii=False, indent=1)
    return ng, nt, no


def main():
    # Single-sheet map: no quadrant, everything under data/toponims/.
    base = os.path.join(ROOT, "data", "toponims")
    top = os.path.join(base, "toponims.json")
    cur_path = os.path.join(base, "curation.json")
    if not os.path.exists(top):
        sys.exit(f"missing {top}")

    cur = json.load(open(cur_path)) if os.path.exists(cur_path) else {}
    ng, nt, no = apply_overlay(top, cur)
    print(f"overlay applied: {ng} readings + {nt} tipus + {no} ordres ({len(cur)} curated ids)")

    rel = lambda p: os.path.relpath(p, ROOT)
    env = {**os.environ,
           "TOPONIMS_JSON": rel(top),
           "MATCHES_JSON": rel(os.path.join(base, "matches.json")),
           "RECHECK_JSON": rel(os.path.join(base, "recheck.json")),
           "CURATION_JSON": rel(cur_path)}
    subprocess.run([sys.executable, NGIB_MATCH], env=env, check=True)


if __name__ == "__main__":
    main()
