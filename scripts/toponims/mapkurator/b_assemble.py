#!/usr/bin/env python3
"""Assemble the approach-B extraction (window workflow output) into the web/table
schema. Self-contained (no dependency on the retired A-path scripts).

Each B toponym carries its box numbers -> position = centroid of those boxes
(from the per-window box files). Box ownership is unique per window, so dedup is a
light safety net (same reading key + same ~cell).

    nix-shell scripts/toponims/shell.nix \
        --run "python3 scripts/toponims/mapkurator/b_assemble.py <wf_output.json>"

Writes data/toponims/toponims.json (the production table the web/georef read).
"""
import json, os, re, sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
# per-sheet support: B_WINDIR points at the sheet's window dir (its w##.json box
# files); positions come out in that sheet crop's pixel space.
WIN = os.path.join(ROOT, os.environ.get("B_WINDIR", "data/toponims/mapkurator/b"))
OUT = os.environ.get("TOPONIMS_JSON") or os.path.join(ROOT, "data/toponims/toponims.json")
# optional coastal (deskewed) track: a second window dir + its extract output. Its
# tilted toponyms supersede the interior toponyms built from the same boxes (which
# the axis-aligned windowing read badly). Interior ids stay stable (hand-curation
# keyed by id survives); coastal toponyms get a "C" id prefix.
COAST_WIN = os.environ.get("B_COAST_WINDIR")
COAST_EXTRACT = os.environ.get("B_COAST_EXTRACT")

# ---- normalisation (engraving reading -> nom / tipus) ----
TOWNS = {
    "palma": "Palma", "capital": "Palma", "inca": "Inca", "calvia": "Calvià",
    "andraix": "Andratx", "soller": "Sóller", "pollensa": "Pollença",
    "alcudia": "Alcúdia", "muro": "Muro", "selva": "Selva", "banalbufar": "Banyalbufar",
    "buñola": "Bunyola", "binisalem": "Binissalem", "sansellas": "Sencelles",
    "alaro": "Alaró", "san juan": "Sant Joan", "montuiri": "Montuïri",
    "manacor": "Manacor", "felanitx": "Felanitx", "campos": "Campos",
    "lluchmajor": "Llucmajor", "porreras": "Porreres", "puebla": "La Puebla (sa Pobla)",
    "santagni": "Santanyí", "santagn": "Santanyí", "algaida": "Algaida", "petra": "Petra",
    "espor": "Esporles", "puigpuñent": "Puigpunyent", "puigpunyent": "Puigpunyent",
    "sineu": "Sineu", "valldemossa": "Valldemossa", "arta": "Artà", "campanet": "Campanet",
    "marratxi": "Marratxí", "sta maria": "Santa Maria del Camí",
    "sta margarita": "Santa Margalida",
}
NUCLI_EXTRA = {"la calobra", "colonia", "cabrera", "escorca", "caimari", "fornalutx",
               "biniaraix", "lluc alcari", "lluc", "de lluc", "orient", "biniamar",
               "llubi", "maria", "consell", "llorito", "deya", "deia", "mancor",
               "bujer", "vila", "galilea", "establiments", "raxa", "buger"}
POSSES = ("son", "so", "can", "ca", "casa", "cas", "cal")
COSTA = ("cala", "calo", "cabo", "cap", "punta", "pta", "illot", "illa", "morro",
         "playa", "puerto", "port", "carregador", "ensenada", "freu", "escar",
         "caleta", "estaca", "moll", "muelle", "carrador", "barranc", "sal",
         "salinas", "estanq")
ORONIM = ("puig", "coll", "serra", "talaia", "talaya", "mola", "bec", "penyal",
          "mirador", "atalaya", "monte")
HIDRO = ("font", "fuente", "pou", "estany", "sinia", "aljub", "cova", "cueva")

# The 8 place classes of the Mut 1683 legend ("Notarū Explicatio"), plus "altre"
# for coastal/geographic names the legend does not classify. Order = legend order.
MUT_TIPUS = [
    "Bisbat",           # Episcopatus
    "Abadia",           # Abbatia
    "Vila parroquial",  # Villa parochialis
    "Llogaret",         # Pagus
    "Castell",          # Castrum munitum
    "Casa d'estudis",   # Domus studiorum
    "Torre de guaita",  # Turres speculatoriae
    "Torre de senyals",  # Turres ignibus navium admonitrices
    "Ciutat",           # Civitas — Maiorica (Palma) & Alcudia
    "altre",
]
# The two civitates of the island (only class the *name* can place; every other
# class is shown by the drawn symbol, not the text, so it is set by hand).
CITIES = {"mallorca", "palma", "alcudia", "alcvdia"}


# The engraving's nasal-abbreviation mark is a flat bar (macron): Sā = San,
# Mōtesió = Montesió. Normalise any circumflex/tilde a vision reader may have used
# for it to the macron, so the diplomatic grafia is consistent (ñ is a real letter,
# left untouched).
MACRON = {"â": "ā", "ê": "ē", "î": "ī", "ô": "ō", "û": "ū",
          "ã": "ā", "ẽ": "ē", "ĩ": "ī", "õ": "ō", "ũ": "ū",
          "Â": "Ā", "Ê": "Ē", "Î": "Ī", "Ô": "Ō", "Û": "Ū",
          "Ã": "Ā", "Ẽ": "Ē", "Ĩ": "Ī", "Õ": "Ō", "Ũ": "Ū"}


def macronize(s):
    return "".join(MACRON.get(c, c) for c in (s or ""))


def deacc(s):
    for a, b in (("ô", "o"), ("â", "a"), ("î", "i"), ("ê", "e"), ("û", "u"),
                 ("ā", "a"), ("ē", "e"), ("ī", "i"), ("ō", "o"), ("ū", "u"),
                 ("ã", "a"), ("ẽ", "e"), ("ĩ", "i"), ("õ", "o"), ("ũ", "u")):
        s = s.replace(a, b)
    return s


def key(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", deacc((s or "").lower()))).strip()


def normalize_nom(text):
    out = []
    for i, w in enumerate(text.split()):
        wl = deacc(w.lower().strip(".,"))
        if i == 0 and wl in ("sô", "so"):
            out.append("Son"); continue
        if i == 0 and wl in ("câ", "ca"):
            out.append("Can"); continue
        out.append(deacc(w))
    return " ".join(out)


def tipus_of(k):
    """Mut's legend classes come from the drawn SYMBOL, not the name, so the name
    can only place the two cities (and, trivially, castle names). Everything else
    defaults to 'altre' for the human to set from the symbol during curation."""
    head = k.split()[0] if k else ""
    if head in CITIES or k in CITIES:
        return "Ciutat"
    if head in ("castell", "castillo"):
        return "Castell"
    return "altre"


def tipus_for(graf, k):
    """Mut legend has no 'predi' class, so the grafia adds nothing over tipus_of."""
    return tipus_of(k)


def emit(windows, windir, prefix, out, seen, skip_steep=None):
    """Build toponyms from one extraction track into `out` (deduping via `seen`).
    If `skip_steep` (a set of (cx,cy)) is given, drop toponyms whose member boxes are
    mostly in it -- they belong to the coastal track instead."""
    for win in windows:
        boxes = {b["n"]: b for b in json.load(open(f"{windir}/w{win['w']:02d}.json"))["words"]}
        for i, t in enumerate(win["toponims"]):
            pts = [boxes[n] for n in t["boxes"] if n in boxes]
            graf = macronize((t["reading"] or "").strip())
            if not pts or not graf:
                continue
            if skip_steep is not None:
                nsteep = sum(1 for p in pts if (p["cx"], p["cy"]) in skip_steep)
                if nsteep * 2 >= len(pts):       # majority tilted -> coastal track owns it
                    continue
            x = round(sum(p["cx"] for p in pts) / len(pts))
            y = round(sum(p["cy"] for p in pts) / len(pts))
            k = key(graf)
            cellkey = (k, x // 40, y // 40)
            if not k or cellkey in seen:
                continue
            seen.add(cellkey)
            out.append({"id": f"{prefix}{win['w']:02d}_{i + 1}", "graf": graf,
                        "nom": TOWNS.get(k) or normalize_nom(graf),
                        "tipus": tipus_for(graf, k), "subtile": "", "x": x, "y": y, "dubte": False})


def main():
    wf = json.load(open(sys.argv[1]))
    W = wf["result"]["windows"] if "result" in wf else wf["windows"]
    out, seen = [], set()
    # coastal track (if configured): its tilted boxes supersede interior toponyms
    steep = None
    if COAST_WIN and COAST_EXTRACT:
        cb = json.load(open(os.path.join(ROOT, COAST_WIN, "coast-boxes.json")))["boxes"]
        steep = {(cx, cy) for cx, cy in cb}
    emit(W, WIN, "B", out, seen, skip_steep=steep)        # interior (ids stable)
    if steep is not None:
        cw = json.load(open(os.path.join(ROOT, COAST_EXTRACT)))
        CW = cw["result"]["windows"] if "result" in cw else cw["windows"]
        emit(CW, os.path.join(ROOT, COAST_WIN), "C", out, seen)   # coastal (deskewed)
        print(f"coastal track: {sum(1 for r in out if r['id'][0]=='C')} toponyms; "
              f"interior {sum(1 for r in out if r['id'][0]=='B')}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"font": "Topònims del mapa de Despuig (1785). El spotter de mapKurator "
                       "detecta les caixes de paraula; Claude vision les agrupa en "
                       "topònims i en llegeix la grafia, finestra a finestra.",
               "comptador": {"toponims": len(out)}, "toponims": out},
              open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"toponyms: {len(out)}  tipus: {dict(Counter(r['tipus'] for r in out))}")
    print(f"✓ {OUT}")


if __name__ == "__main__":
    main()
