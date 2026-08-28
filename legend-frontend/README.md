# Legend — marketing site

Standalone landing page for **Legend**. Extracted from the Orchestraty
website so it can live in the Legend repository on its own.

It has **no dependency on Orchestraty** — its own theme tokens, navbar, footer
and entry point. Just drop this folder into the Legend repo.

## Run

```bash
npm install
npm run dev        # http://localhost:5300
```

## Build

```bash
npm run build      # -> dist/
npm run preview
```

## Structure

```
index.html
vite.config.ts
tsconfig.json
src/
  main.tsx           entry — renders the page
  theme.css          design tokens (dark + green), base styles, .container/.section
  links.ts           DOCS_URL / GITHUB_URL — edit these
  Navbar.tsx/.css    site nav (Legend branded)
  Footer.tsx/.css    site footer
  Legend.tsx   the page: scanning-laptop hero, how it works,
  Legend.css   what-you-get deck, install CTA
```

## Edit first

`src/links.ts` — set `DOCS_URL` and `GITHUB_URL` to the real destinations.
The install command shown on the page is `pip install legend` (in `Legend.tsx`).
