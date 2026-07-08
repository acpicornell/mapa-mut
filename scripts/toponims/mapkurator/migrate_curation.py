#!/usr/bin/env python3
"""One-time migration: fold the 5 scattered per-quadrant curation files into a
single overlay `curation.json`, one record per toponym id:

  graf-fixes.json      {id: graf}    -> rec["graf"]     hand reading
  tipus-fixes.json     {id: tipus}   -> rec["tipus"]    hand type
  recheck-picks.json   {id: grafia}  -> rec["ngib"]     picked NGIB place
  review-reviewed.json {id: verdict} -> rec["verdict"]  ok|pick|none|trash
  discards.json        {id: true}    -> rec["verdict"]="trash" (if unset)

Lossless: every key/value of the old files lands in curation.json. Prints a
reconciliation line per quadrant. Does NOT delete the old files — do that only
after `bake.py` proves the new path yields an identical matches.json.

  nix-shell scripts/toponims/shell.nix --run \
    "python3 scripts/toponims/mapkurator/migrate_curation.py"
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
QUADRANTS = ["nw", "ne", "se", "sw"]


def load(p):
    return json.load(open(p)) if os.path.exists(p) else {}


for q in QUADRANTS:
    b = os.path.join(ROOT, "data", "toponims", q)
    if not os.path.isdir(b):
        continue
    graf = load(os.path.join(b, "graf-fixes.json"))
    tipus = load(os.path.join(b, "tipus-fixes.json"))
    picks = load(os.path.join(b, "recheck-picks.json"))
    reviewed = load(os.path.join(b, "review-reviewed.json"))
    discards = load(os.path.join(b, "discards.json"))
    if not any([graf, tipus, picks, reviewed, discards]):
        print(f"{q}: no curation, skipped")
        continue

    cur = {}
    rec = lambda i: cur.setdefault(i, {})
    for i, v in graf.items():
        if (v or "").strip():
            rec(i)["graf"] = v
    for i, v in tipus.items():
        if v:
            rec(i)["tipus"] = v
    for i, v in picks.items():
        if v:
            rec(i)["ngib"] = v
    for i, v in reviewed.items():
        if v:
            rec(i)["verdict"] = v
    for i, v in discards.items():
        if v and "verdict" not in rec(i):
            rec(i)["verdict"] = "trash"

    json.dump(cur, open(os.path.join(b, "curation.json"), "w"),
              ensure_ascii=False, indent=1, sort_keys=True)

    # reconciliation: counts must back out to the source files (no field dropped)
    n = lambda f: sum(f in r for r in cur.values())
    src_graf = sum(1 for v in graf.values() if (v or "").strip())
    verdict_keys = set(reviewed) | set(discards)
    print(f"{q}: {len(cur)} ids -> curation.json | "
          f"graf {n('graf')}/{src_graf}  tipus {n('tipus')}/{len(tipus)}  "
          f"ngib {n('ngib')}/{len(picks)}  "
          f"verdict {n('verdict')}/{len(verdict_keys)} "
          f"(reviewed {len(reviewed)}, discards {len(discards)})")
