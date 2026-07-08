// Approach-B vision extraction for ONE quadrant sheet (page-by-page pipeline).
// Reference script — set BASE to the sheet's window dir and N to the window count
// (printed by b_windows.py), then run via the Workflow tool. One agent per window
// groups the spotter boxes into toponyms and reads them DIPLOMATICALLY (Sô/Câ kept).
// Save the returned {windows:[...]} to <BASE>/extract.json for b_assemble.py.
//
// NW clean rebuild 2026-06-19: interior BASE=.../nw/b N=15 → 480; coast
// BASE=.../nw/b-coast N=4 → 109. EDIT the BASE/N constants below per track and
// re-invoke (the Workflow `args` global did NOT propagate when launched via
// scriptPath, so don't rely on it — the constants are the source of truth).
export const meta = {
  name: 'b-extract-sheet',
  description: 'Approach B extraction for one quadrant sheet: N agents read map windows, group spotter boxes into toponyms and read them diplomatically',
  phases: [{ title: 'Extract', detail: 'one agent per sheet window' }],
}

const BASE = (args && args.base) || '/home/acpicornell/projects/despuig/data/toponims/mapkurator/ne/b-coast'
const N = (args && args.n) || 5
const SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    toponims: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          boxes: { type: 'array', items: { type: 'number' } },
          reading: { type: 'string' },
        },
        required: ['boxes', 'reading'],
      },
    },
  },
  required: ['toponims'],
}

function prompt(nn) {
  return `You are transcribing place-names from an 18th-century engraved map of Mallorca (Despuig, 1785), in Mallorqui/Catalan period spelling. Your transcription must be STRICTLY LITERAL: read the engraved letters and nothing else. Inventing, "correcting", completing, or guessing a name is a SERIOUS ERROR — it destroys the toponymic record. A partial honest reading is always better than a confident wrong one.

Read the window image: ${BASE}/w${nn}.png
The companion file ${BASE}/w${nn}.json lists the detected word boxes; n is the number printed at each red box's top-left corner. That file ALSO has a "text" field — it is RAW MACHINE OCR, FREQUENTLY WRONG (it confuses the Son mark with "St", drops and swaps letters). DO NOT copy it, DO NOT trust it, DO NOT let it influence you. Read the engraving pixels ONLY; use n solely to know which box you are transcribing.

Your job: GROUP boxes into complete toponyms and transcribe each EXACTLY as engraved.
- A toponym may span several boxes ("Sô"+"Toni"+"Coll" = "Sô Toni Coll"); group their numbers. Adjacent boxes may be different names — keep them apart.
- DIPLOMATIC transcription: keep every abbreviation mark exactly as engraved; do NOT modernize or expand them (the modern form is derived later).
- THE SON ABBREVIATION (critical, very common): a capital S followed by a vowel carrying a circumflex/stroke — Sô, Sâ, Sõ — is the possessive "Son/Sa". Transcribe it LITERALLY as "Sô"/"Sâ". It is NOT "Sant" and NOT "St"/"S.t". Only write "St."/"S.t" when a genuine raised/superscript t is actually engraved (real saints, e.g. "St Jordi"). If you see a rounded mark over the vowel, it is Son — never Sant.
- Other marks as engraved: Câ/Ca = Can, Pta. = Punta, Rfl. = Rafal, circumflex vowels ô â ê, ll/y, b/v.
- Coastal/feature names count too (Cala, Punta, Cap, Illa, Torrent, Puig...). Town names in CAPITALS are nuclei — include them.
- INVENT NOTHING. If some letters are illegible, transcribe only the part you can clearly read. If a whole box is illegible noise, skip it. Never fill a gap with a plausible name. Sparse windows are fine.

Return {"toponims": [{"boxes": [n,...], "reading": "..."}]} for every name you can actually read in the window.`
}

phase('Extract')
const results = await parallel(
  Array.from({ length: N }, (_, i) => {
    const nn = String(i + 1).padStart(2, '0')
    return () => agent(prompt(nn), { label: `w${nn}`, phase: 'Extract', schema: SCHEMA })
  })
)
const out = results.map((r, i) => ({ w: i + 1, toponims: (r && r.toponims) || [] }))
const total = out.reduce((s, w) => s + w.toponims.length, 0)
log(`extracted ${total} toponyms across ${results.filter(Boolean).length}/${N} windows`)
return { total, windows: out }
