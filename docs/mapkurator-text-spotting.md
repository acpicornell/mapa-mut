# Toponym extraction via text spotting (mapKurator + Claude vision)

Status: **implemented.** This document is the *why* — the design rationale for
extracting the place names of Vicenç Mut's **1683** map of Mallorca with a text
spotter. The working pipeline (the *how*) is documented in
[`scripts/toponims/README.md`](../scripts/toponims/README.md), the step-by-step
recipe in [`scripts/toponims/mapkurator/SHEET.md`](../scripts/toponims/mapkurator/SHEET.md)
and the detection setup in
[`scripts/toponims/mapkurator/README.md`](../scripts/toponims/mapkurator/README.md);
those are authoritative for commands.

The approach was worked out first in the sibling
[despuig](https://github.com/acpicornell/despuig) project (the 1785 Despuig map)
and adapted here. Two things differ in this repository:

- **Hardware/runtime.** Detection does not run in a CUDA Docker image. It is
  delegated to the sibling Apple-Silicon port
  [`../mapkurator-mps`](https://github.com/acpicornell/mapkurator-mps), which runs
  the spotter natively on the Apple GPU (Metal/MPS), packaged as a Nix flake.
- **One sheet.** Mut's engraving is a single plate
  (`data/raw/Insula_Maioricae_Vicentius_Mut_1683.jpg`, 3840×2849), so the whole
  island is processed and georeferenced as one sheet — there are no quadrants.

## Why text spotting

Reading a map by **blind grid tiling** — cut the map into fixed cells and have a
vision model read each cell whole — has a structural flaw: names that fall on a
cell boundary get **cut**, and each half is recorded as a separate garbage entry.

Historical-map OCR is a mature field with a better architecture. The reference
system is **mapKurator** (Univ. of Minnesota), run over 60k+ David Rumsey maps,
and there is an annual benchmark (**ICDAR MapText**). The key idea:

> **Separate detection from recognition; the unit is the WORD, not the cell.**
> A model detects a polygon around every word label (curved/rotated included),
> overlapping tiles are merged at the polygon level, so a word cut in one tile is
> whole in its neighbour. A fragment is never recorded as a final entry — by design.

Decisions taken:

- **Goal = a clean toponym list** (faithful, diplomatic transcription). Gazetteer
  (NGIB) matching is enrichment, not the quality bar: a 1683 map will never map
  cleanly onto a modern gazetteer (vanished/renamed places, real homonyms).
- **Retrieval-first (project NGIB places, verify) is rejected** for this goal: the
  NGIB differs too much from what the map actually shows.

## The hybrid

1. **Detection (mapKurator spotter-v2, English checkpoint `model_v2_en.pth`):**
   detect word polygons over the map. The masked canvas (`..._boxes.jpg`, sea and
   margins masked) is cut into overlapping patches, upscaled ×2 so the small
   engraved lettering is at a scale the spotter reads well; each patch's polygons
   are shifted back to master pixel coordinates and duplicates seen in two
   patches are removed by polygon IoU (`pretile.py` → spotter →
   `merge_detections.py`, chained by `detect.sh`). On the Mut scan this gives
   ~300 word polygons.
2. **Recognition and grouping (Claude vision):** the spotter's own recognition is
   trained on (mostly English) Rumsey maps and is rough on this historical font,
   so only its **boxes** are kept. The map is cut into windows along whitespace
   (`b_windows.py`), and one vision agent per window groups the spotter boxes into
   toponyms and reads them diplomatically (period spelling such as Sô/Câ kept) —
   "Approach B". `b_assemble.py` assembles the result into
   `data/toponims/toponims.json`. Mut: 6 windows → 137 toponyms.
3. **Georeference:** control points come from hand-marked dots on identifiable
   towns and capes (19 dots: 12 interior municipality seats + 7 coastal capes).
   `georef_sheet.py` fits the mapKurator transform family (affine / poly2 / TPS)
   and picks by leave-one-out on the control points; for this schematic map the
   affine fit on the 12 interior dots wins (LOO median ≈ 1972 m).
4. **NGIB match** (`ngib_match.py`, run by `bake.py`) as enrichment, followed by
   hand curation.

Division of labour: the spotter finds **where** each word is; Claude reads **what**
it says.

## References

- mapKurator system: https://arxiv.org/abs/2306.17059 ·
  https://github.com/knowledge-computing/mapkurator-system
- Spotter: https://github.com/knowledge-computing/mapkurator-spotter
- Apple-Silicon port used here: https://github.com/acpicornell/mapkurator-mps
- ICDAR 2024 MapText competition: https://rrc.cvc.uab.es/?ch=28&com=tasks
- LIGHT (multi-modal text linking): https://arxiv.org/pdf/2506.22589
