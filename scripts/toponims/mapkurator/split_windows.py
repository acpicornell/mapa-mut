#!/usr/bin/env python3
"""Split a sheet's windows.json into per-window w##.json box files (one per window),
which the Approach-B vision agents read alongside each w##.png.

    nix-shell scripts/toponims/mapkurator/shell.nix \
      --run "python3 scripts/toponims/mapkurator/split_windows.py <window-dir>"
"""
import json, os, sys

D = sys.argv[1] if len(sys.argv) > 1 else "data/toponims/mapkurator/b"
W = json.load(open(os.path.join(D, "windows.json")))["windows"]
for w in W:
    json.dump(w, open(os.path.join(D, "w%02d.json" % w["w"]), "w"),
              ensure_ascii=False, indent=1)
print("wrote %d per-window json files -> %s" % (len(W), D))
