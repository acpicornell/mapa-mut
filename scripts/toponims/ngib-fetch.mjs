// Downloads the Mallorca subset (ILLA=1) of the Nomenclàtor Geogràfic de les
// Illes Balears (NGIB, layer "Lloc_anomenat") into data/toponims/ngib/llocs.json.
//
// The NGIB is the authoritative, UIB-normalised gazetteer of Balearic place
// names (field GRAFIA). We use it to validate/correct the AI-read toponyms of
// the Despuig map and to clear the "dubte" flags.
//
//   node scripts/toponims/ngib-fetch.mjs
//
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, '..', '..', 'data/toponims/ngib');

const BASE = 'https://ideib.caib.es/geoserveis/rest/services/public/NGIB/MapServer/0/query';
const FIELDS = ['OBJECTID', 'GRAFIA', 'TIPUS_LOCAL', 'TIPUS_SUPERLOCAL', 'MUNICIPI', 'NUCLI'];
const PAGE = 1000;

function url(offset) {
  const p = new URLSearchParams({
    where: 'ILLA=1',
    outFields: FIELDS.join(','),
    returnGeometry: 'true',
    outSR: '4326',
    resultOffset: String(offset),
    resultRecordCount: String(PAGE),
    f: 'json',
  });
  return `${BASE}?${p}`;
}

const all = [];
for (let offset = 0; ; offset += PAGE) {
  const res = await fetch(url(offset));
  if (!res.ok) throw new Error(`HTTP ${res.status} at offset ${offset}`);
  const data = await res.json();
  const feats = data.features ?? [];
  for (const f of feats) {
    const a = f.attributes, g = f.geometry;
    if (!g || g.x == null) continue;
    all.push({
      grafia: a.GRAFIA,
      tipus: a.TIPUS_LOCAL,
      municipi: a.MUNICIPI || null,
      nucli: a.NUCLI || null,
      lng: Math.round(g.x * 1e6) / 1e6,
      lat: Math.round(g.y * 1e6) / 1e6,
    });
  }
  process.stdout.write(`\r  baixats ${all.length} topònims…`);
  if (!data.exceededTransferLimit && feats.length < PAGE) break;
}
process.stdout.write('\n');

await mkdir(OUT_DIR, { recursive: true });
await writeFile(join(OUT_DIR, 'llocs.json'), JSON.stringify(all));
console.log(`✓ ${all.length} NGIB toponyms (Mallorca) → data/toponims/ngib/llocs.json`);
