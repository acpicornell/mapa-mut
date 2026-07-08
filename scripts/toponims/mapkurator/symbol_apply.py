#!/usr/bin/env python3
"""Collect the Sonnet symbol-classification results and apply them.

Each montage produced result_NNN.json = [{idx, tipus, conf}] (idx 0..11). We map
idx -> id via sym_manifest.json (NEVER trust the id the model reads). Build
data/toponims/<q>/symbol-tipus.json = {id: {tipus, conf}}, then relabel the data:
an 'altre' toponym gets the legend tipus when conf is high/med and the tipus is a
real legend category (not 'altre'/'unclear'). Human curation still wins later.

  nix-shell scripts/toponims/mapkurator/shell.nix --run \
    "python3 scripts/toponims/mapkurator/symbol_apply.py"
"""
import json
import os
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
LEGEND = {
    "Ciudad", "Villa Parroquial", "Lugar grande", "Lugar chico", "Oratorio publico",
    "Muchas casas separadas ó Establecimiento", "Dos ó tres casas", "Casa de campo ó Predio",
    "Hermita", "Casa de estudios", "Castillo", "Atalaya ó Torre", "Guarda", "Bateria",
    "Torrente", "Puente", "Puerto", "Punta", "Isla",
}
manifest = json.load(open(os.path.join(ROOT, "data/toponims/mapkurator/sym_manifest.json")))

applied_total = 0
for q, montages in manifest.items():
    symdir = os.path.join(ROOT, f"data/toponims/mapkurator/{q}/sym")
    sym = {}                                   # id -> {tipus, conf}
    missing = 0
    for n, ids in enumerate(montages):
        rp = os.path.join(symdir, f"result_{n:03d}.json")
        if not os.path.exists(rp):
            missing += 1
            continue
        try:
            res = json.load(open(rp))
        except Exception as e:
            print(f"  ! {q}/result_{n:03d}.json unreadable: {e}"); missing += 1; continue
        for e in res:
            i = e.get("idx")
            if not isinstance(i, int) or i < 0 or i >= len(ids):
                continue
            sym[ids[i]] = {"tipus": e.get("tipus"), "conf": e.get("conf", "med")}
    json.dump(sym, open(os.path.join(ROOT, f"data/toponims/{q}/symbol-tipus.json"), "w"),
              ensure_ascii=False, indent=1, sort_keys=True)

    # apply: relabel the data where the symbol gives a confident legend type
    apply = {i: v["tipus"] for i, v in sym.items()
             if v["conf"] in ("high", "med") and v["tipus"] in LEGEND}
    n_app = 0
    for fn in ("toponims.json", "matches.json", "recheck.json"):
        p = os.path.join(ROOT, f"data/toponims/{q}/{fn}")
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        items = d["toponims"] if isinstance(d, dict) and "toponims" in d else d
        c = 0
        for t in items:
            if isinstance(t, dict) and t.get("tipus") == "altre" and t.get("id") in apply:
                t["tipus"] = apply[t["id"]]; c += 1
        json.dump(d, open(p, "w"), ensure_ascii=False, indent=1)
        if fn == "toponims.json":
            n_app = c
    applied_total += n_app
    bytip = Counter(v["tipus"] for v in sym.values())
    print(f"{q}: {len(sym)} classified ({missing} montages missing) | applied {n_app} to 'altre'")
    print(f"   {dict(bytip)}")
print(f"TOTAL applied to data: {applied_total}")
