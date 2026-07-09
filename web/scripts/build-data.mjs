#!/usr/bin/env node
// Data layer for the Mut 1683 site. Joins the two source files by toponym id and
// emits a single versioned file that the Astro pages import:
//
//   web/src/data/toponims.json — the 137 toponyms of the single-sheet engraving,
//     each carrying its 1683 reading, modern name, type, confidence, NGIB match
//     and both pixel (x, y) and geographic (lon, lat) positions.
//
// Sources (single sheet, NO quadrants, NO census, NO vignettes):
//   data/toponims/matches.json  — [{id, nom, graf, tipus, decision, review, ngib,
//                                   municipi, sim, km}]  (match + confidence, no position)
//   data/toponims/toponims.json — {toponims:[{id, graf, nom, tipus, x, y, dubte,
//                                   lon, lat}], georef:{model, control_points,
//                                   loo_median_m, sheet}}  (positions + georef meta)
//
//   cd web && npm run data

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..');
const OUT = resolve(HERE, '..', 'src', 'data');

const rd = (rel) => JSON.parse(readFileSync(join(ROOT, rel), 'utf8'));

// ─── Load sources ──────────────────────────────────────────────────────────
const matches = rd('data/toponims/matches.json');
const src = rd('data/toponims/toponims.json');
const posById = new Map(src.toponims.map((t) => [t.id, t]));

// ─── Join matches ↔ positions by id ──────────────────────────────────────────
const perDecision = {};
const perTipus = {};
const toponims = [];
let sensePos = 0;

for (const m of matches) {
  const p = posById.get(m.id) || null;
  if (!p) sensePos++;
  const decision = m.decision || 'sense';
  // tipus comes as a single string; the pages treat it as a multi-value array.
  const tipus = m.tipus ? [m.tipus] : (p && p.tipus ? [p.tipus] : []);
  toponims.push({
    id: m.id,
    graf: m.graf ?? p?.graf ?? '',           // 1683 reading (diplomatic)
    nom: m.nom ?? p?.nom ?? '',              // modern name
    tipus,
    decision,
    review: m.review ?? null,
    ngib: m.ngib ?? null,                     // matched NGIB canonical form
    municipi: m.municipi ?? null,
    sim: m.sim ?? null,
    km: m.km ?? null,
    dubte: !!(p?.dubte ?? m.dubte),
    lon: p?.lon ?? null,
    lat: p?.lat ?? null,
    x: p?.x ?? null,
    y: p?.y ?? null,
  });
  perDecision[decision] = (perDecision[decision] || 0) + 1;
  for (const t of tipus) perTipus[t] = (perTipus[t] || 0) + 1;
}

const georef = src.georef || {};

mkdirSync(OUT, { recursive: true });
writeFileSync(
  join(OUT, 'toponims.json'),
  JSON.stringify(
    {
      // Data license travels with the data: if this file is copied, the terms
      // and the required attribution go with it. See data/toponims/LICENSE.md.
      license: {
        name: 'CC BY-NC 4.0',
        url: 'https://creativecommons.org/licenses/by-nc/4.0/',
        attribution:
          'Topònims del mapa de Mallorca de Vicenç Mut (Insula Maioricae, 1683) — © Antonio Picornell',
        note: 'Reuse allowed for non-commercial purposes with attribution.',
      },
      font:
        "Topònims del mapa de Mallorca de Vicenç Mut (Insula Maioricae, 1683). " +
        "Pipeline d'un sol full: spotter mapKurator (Apple MPS) + lectura Claude vision + " +
        "georeferenciació afí global + match amb el Nomenclàtor Geogràfic de les Illes Balears (NGIB).",
      georef: {
        model: georef.model ?? null,
        control_points: georef.control_points ?? null,
        loo_median_m: georef.loo_median_m ?? null,
        sheet: georef.sheet ?? null,
      },
      comptador: {
        total: toponims.length,
        ambPosicio: toponims.filter((t) => t.lon != null && t.lat != null).length,
        ambNgib: toponims.filter((t) => t.ngib).length,
        perDecision,
        perTipus,
      },
      toponims,
    },
    null,
    1,
  ),
);

// ─── Summary ─────────────────────────────────────────────────────────────────
console.log(`✓ web/src/data/toponims.json — ${toponims.length} topònims (full únic Mut 1683)`);
console.log(`  decisions: ${JSON.stringify(perDecision)}`);
console.log(
  `  georef: ${georef.model ?? '—'}, ${georef.control_points ?? '—'} punts de control, ` +
    `LOO ≈ ${georef.loo_median_m ?? '—'} m`,
);
if (sensePos) console.log(`  ⚠ ${sensePos} topònims sense posició (no eren a toponims.json)`);
