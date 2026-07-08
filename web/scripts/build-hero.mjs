#!/usr/bin/env node
// Builds the home-page hero image: a wide crop of the Mut 1683 engraving from the
// high-resolution master. Single sheet, no quadrants. Output is gitignored and
// regenerable.
//
//   cd web && npm run hero

import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';
import sharp from 'sharp';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..');
const SRC = join(ROOT, 'data/raw/Insula_Maioricae_Vicentius_Mut_1683.jpg');
const OUT_DIR = resolve(HERE, '..', 'public', 'hero');
const OUT = join(OUT_DIR, 'mapa-hero.jpg');

// Crop as fractions of the master (a wide central band of the engraving).
const REGION = { left: 0.05, top: 0.14, width: 0.90, height: 0.46 };
const WIDTH = 2400;
const QUALITY = 82;

mkdirSync(OUT_DIR, { recursive: true });

const img = sharp(SRC, { limitInputPixels: false });
const { width: W, height: H } = await img.metadata();
await sharp(SRC, { limitInputPixels: false })
  .extract({
    left: Math.round(W * REGION.left),
    top: Math.round(H * REGION.top),
    width: Math.round(W * REGION.width),
    height: Math.round(H * REGION.height),
  })
  .resize({ width: WIDTH, withoutEnlargement: true })
  .jpeg({ quality: QUALITY, mozjpeg: true })
  .toFile(OUT);

console.log(`✓ hero → web/public/hero/mapa-hero.jpg (amplada ${WIDTH}px, q${QUALITY})`);
