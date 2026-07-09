# Vendored third-party assets

These libraries and fonts are self-hosted (not loaded from any CDN at runtime) so
the site has no external code dependency and can enforce a strict
Content-Security-Policy. All are redistributed here under their own permissive
licenses, whose full texts are included alongside each asset.

| Asset | Version | License | License file |
|-------|---------|---------|--------------|
| OpenSeadragon | 4.1.0 | BSD 3-Clause | `openseadragon/LICENSE.txt` |
| Leaflet | 1.9.4 | BSD 2-Clause | `leaflet/LICENSE.txt` |
| Cinzel (font) | Google Fonts | SIL OFL 1.1 | `fonts/cinzel-OFL.txt` |
| EB Garamond (font) | Google Fonts | SIL OFL 1.1 | `fonts/ebgaramond-OFL.txt` |

The minified JS bundles keep their upstream copyright/license headers. Map raster
tiles (OpenStreetMap, Esri) are **not** vendored — they are fetched from their
providers at runtime with attribution, as they are data, not code.

## Regenerating

- **OpenSeadragon:** `openseadragon.min.js` + `images/*` from
  `https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/`.
- **Leaflet:** `leaflet.js`, `leaflet.css` + `images/*` from
  `https://unpkg.com/leaflet@1.9.4/dist/`.
- **Fonts:** the `latin` + `latin-ext` `woff2` subsets of the Google Fonts CSS
  (`Cinzel:wght@500;600` and `EB+Garamond:ital,wght@0,400;0,500;1,400`), with
  `fonts.css` rewritten to point at the local files.
