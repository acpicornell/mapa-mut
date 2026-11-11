# The public website (`web/`)

The published site at <https://mut.corpusbalear.org>, built with Astro as a static
site. Moved here from the top-level README.

## `web/` — the public website (Astro, static)

The published site: a filterable/sortable table of the **137** curated toponyms,
an interactive **Mapa** (geographic layer), a page on the engraving itself with a
deep-zoom viewer (**El gravat**), the method, and statistics. Catalan UI;
readings kept in their original 1683 spelling. It is **self-contained**: it only
reads the JSON under `web/src/data/`, generated from the versioned
`data/toponims/` by `npm run data` (which CI runs before every build).

```bash
cd web
npm install
npm run data        # build src/data/*.json from the pipeline output
npm run hero        # homepage hero crop
npm run map         # DZI tiles for the engraving deep-zoom on /gravat and /toponims (slow; only when the master changes)
npm run dev         # http://localhost:4330
npm run build       # → web/dist  (prebuild runs data + hero)
```

## Deploy

Deploy = **Cloudflare Workers (Static Assets)**, automatic on push to the default branch
(see [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)); manually with `npm run deploy` (= build +
`wrangler deploy`, config in `web/wrangler.toml`). The generated deploy assets
(`web/public/{map,hero}`) are versioned, so a clean checkout reproduces the whole site.
Third-party libraries and fonts are self-hosted under `web/public/vendor/`, so the site
loads no runtime CDN and can enforce the strict CSP in `web/public/_headers`.
