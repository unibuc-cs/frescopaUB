# Running Frescopa Locally

This guide gets the Frescopa site running on your machine for local testing of
scripts, blocks, and styles.

The site is built on Adobe Edge Delivery Services. The AEM CLI runs a local
dev server that:

1. Serves your **local working copy** of all code (`blocks/`, `scripts/`,
   `styles/`, etc. — including uncommitted edits).
2. **Reverse-proxies page content** from the project's live AEM preview
   backend at `https://main--frescopa--andreibbarbu.aem.page`.

So localhost = your code + live content. That's the supported workflow.

## Prerequisites

- **Node.js** 18 or newer (`node -v` to check). https://nodejs.org/ if missing.
- **npm** (ships with Node).
- **Git** to clone the repo.
- **Network access** to `*.aem.page` / `*.aem.live` so the CLI can fetch page
  content. No AEM login is required for previewed/published content.

## One-Time Setup

```bash
git clone <this-repo-url> frescopa
cd frescopa
npm install
```

`npm install` runs a `postinstall` step that builds the dropin commerce
assets — this can take a minute the first time.

## Starting the Local Server

```bash
npx -y @adobe/aem-cli up --url https://main--frescopa--andreibbarbu.aem.page --no-open
```

Then open http://localhost:3000 in your browser.

You should see banner output ending with:

```
info: Local AEM dev server up and running: http://localhost:3000/
info: Enabled reverse proxy to https://main--frescopa--andreibbarbu.aem.page
```

The explicit `--url` is required in this repo because the local Git `origin`
remote is `AChiriac/information_gain`, while the page content still lives on
the Frescopa preview backend. Without `--url`, the CLI infers
`https://main--information_gain--AChiriac.hlx.page`, which returns 403/404.

The dev server has live reload: edit any file under `blocks/`, `styles/`, or
`scripts/`, save, and the browser refreshes automatically.

### Optional: install the CLI globally

```bash
npm install -g @adobe/aem-cli
aem up --no-open
```

## What you can change locally

These take effect immediately on the next page reload:

- **Block logic** — `blocks/<name>/<name>.js`
- **Block styles** — `blocks/<name>/<name>.css`
- **Global scripts** — `scripts/scripts.js` (entry point), `scripts/delayed.js`
- **Global styles** — `styles/styles.css`, `styles/lazy-styles.css`, `styles/fonts.css`
- **Head** — `head.html`

Do **not** edit `scripts/aem.js` — it's the AEM core library.

## Changing page content

Page content (the actual HTML body of each URL) comes from the AEM backend,
not from your local checkout. There are two ways to change it:

### Option A — author it in AEM (canonical)

Use the AEM Sidekick / Universal Editor on the live preview environment. Once
previewed, content shows up at `https://main--frescopa--andreibbarbu.aem.page`
and on your local server. This is what authors do.

### Offline product data (mock commerce)

The dropins (`/coffee`, `/tea`, `/machines`, `/products/<sku>`) normally
fetch product info from Adobe Commerce GraphQL endpoints that you may not
have access to. This repo ships a HAR-based mock so those pages render
without that backend:

- `localhost.har` (in project root) — recorded browsing session
- `scripts/mock-commerce.js` — runtime fetch interceptor (auto-loaded)
- `tools/mock-commerce/build-mocks.mjs` — rebuilds the mocks from a fresh HAR

To extend coverage to new pages, recapture with Chrome DevTools' "Disable
cache" enabled, save as `localhost.har`, and run
`node tools/mock-commerce/build-mocks.mjs`. Full instructions in
[`tools/mock-commerce/README.md`](tools/mock-commerce/README.md).

Currently working offline: `/coffee`, `/tea` (full product data + images).
Currently not yet covered: `/machines`, individual product detail pages
— see the mock-commerce README for how to extend.

### Option B — fully static, EDS-decoupled (`static/` folder)

The repo includes a `static/` folder with hand-written HTML pages that skip
Edge Delivery Services entirely — no AEM CLI, no proxy, no backend.

```bash
npx -y http-server -p 8080 -c-1 .
# then open http://localhost:8080/static/
```

See `static/README.md` for details, trade-offs, and how to add pages.
Block **CSS** works; block **JS does not run** in this mode — use Option A
if you need to test block JavaScript or commerce features.

### Option C — local draft pages (legacy)

The repo has a `drafts/` folder with two starter pages (`index.html`,
`about.html`). These are **not served by the AEM CLI directly** — older
versions of the CLI accepted `--html-folder`, but the current version does
not. To use them you'd need to spin up a separate static server:

```bash
npx -y http-server drafts -p 8080
```

Then visit `http://localhost:8080/` — but note the EDS decoration pipeline
(scripts.js, blocks, etc.) will not run unless the page imports them with
correct paths. This is a partial fallback only useful for raw HTML/markup
experimentation; if you actually need the EDS pipeline, use Option A.

For most testing — script changes, block changes, CSS — Option A + the live
preview content is what you want. You only need Option B if you have no
network access at all.

## Inspecting what the server returns

```bash
curl http://localhost:3000/                     # rendered page
curl http://localhost:3000/index.plain.html     # body markup AEM hands the decorator
curl http://localhost:3000/index.md             # source markdown
```

Useful when debugging a block — shows you the exact DOM your block code is
about to decorate.

## Linting

Before committing run:

```bash
npm run lint           # check JS + CSS
npm run lint:fix       # auto-fix what's fixable
```

## Troubleshooting

- **Port 3000 already in use** — kill whatever is on it (`lsof -i :3000`) or
  use another port: `aem up --port 3001 --no-open`.
- **`npm install` fails on `postinstall`** — make sure your Node version is
  18+; older Node breaks the dropin build step.
- **Page renders blank / unstyled** — open browser devtools console; the
  block decoration code logs there. Most often a block's expected markup
  doesn't match what the backend returned.
- **404 on a path you expect to exist** — that path isn't published on the
  AEM preview backend yet. Either author it in AEM or use a path that does
  exist (`curl http://localhost:3000/` confirms the homepage works).
- **Network blocked** — the CLI needs to reach `*.aem.page`. On a restricted
  network you'll see proxy errors and pages won't load.

## Project layout (quick reference)

```
blocks/      Reusable content blocks (one folder each)
scripts/     Global JS — scripts.js is the entry point, aem.js is core (don't edit)
styles/      Global CSS
head.html    Injected into <head> of every page
drafts/      Sample static HTML (Option B fallback only — see above)
```

Full project conventions are in `AGENTS.md`.
