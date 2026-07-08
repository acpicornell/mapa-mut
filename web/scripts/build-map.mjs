#!/usr/bin/env node
// Builds the Deep Zoom (DZI) tiles of the Mut 1683 master for OpenSeadragon
// (the "El gravat" viewer and the toponym-detail viewer). ONE image, ONE DZI —
// no quadrants. Output is gitignored and regenerable; it is slow, so it is NOT
// part of prebuild — run it when the master changes:
//
//   cd web && npm run map

import { mkdir, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';
import sharp from 'sharp';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..');
const MASTER = join(ROOT, 'data/raw/Insula_Maioricae_Vicentius_Mut_1683.jpg');
const OUT = resolve(HERE, '..', 'public', 'map');

await mkdir(OUT, { recursive: true });
await rm(join(OUT, 'mapa.dzi'), { force: true });
await rm(join(OUT, 'mapa_files'), { recursive: true, force: true });

console.log('Generant tessel·les DZI del gravat de Mut (1683)…');
await sharp(MASTER, { limitInputPixels: false })
  .tile({ size: 256, overlap: 1, layout: 'dz' })
  .toFile(join(OUT, 'mapa'));
console.log('✓ web/public/map/mapa.dzi + mapa_files/');
