# Frescopa Static Build

A fully static, EDS-decoupled version of Frescopa. No AEM CLI, no reverse
proxy, no backend. Just HTML, CSS, and any plain HTTP server.

## What's in here

- `index.html`, `about.html` — hand-written pages.
- `static.css` — page chrome (header/nav/footer) for the static build.
- The pages link directly to the project's existing CSS in `/styles/` and
  `/blocks/<name>/<name>.css`. **No block JavaScript runs.**

## Run it

From the **project root** (one directory up from `static/`):

```bash
npx -y http-server -p 8080 -c-1 .
```

Or with Python:

```bash
python3 -m http.server 8080
```

Then open http://localhost:8080/static/

The `-c-1` on `http-server` disables caching so edits show up on refresh.

> Serve from the **project root**, not from `static/` itself — the pages
> reference `/styles/...` and `/blocks/...` with absolute paths, so the
> server's root must be the project root.

## Editing

Open any `.html` file, change content, save, refresh browser. That's it.

To add a page:

1. Copy `index.html` to `static/<newpage>.html`.
2. Edit the body.
3. Add a link to it in the `<nav>` of all pages that should reach it.

## Trade-offs vs. the EDS dev server

| | Static build (this folder) | AEM CLI (`aem up`) |
|---|---|---|
| Setup | `http-server` | `npm install`, `aem-cli` |
| Network needed | No | Yes (proxies live preview) |
| Block CSS | Works | Works |
| Block JS | **Does not run** | Runs |
| Auto-blocking, sections, three-phase loader | Not present | Present |
| Content editing | Edit HTML files | Edit in AEM author |
| Use for | Quick visual demos, offline | Real script/feature work |

If you need block JS (commerce, forms, quiz, dynamic UI) → use the AEM CLI.
If you just want a fast no-tooling preview → this folder is fine.

## Why this exists

Adobe Edge Delivery Services renders pages by:
1. Fetching markdown/HTML content from a backend.
2. Running `scripts/aem.js` and `scripts/scripts.js` to wrap sections,
   discover blocks, load each block's CSS+JS, and call its `decorate()`.

The static pages here **skip step 1 and step 2** by hand-writing the
post-decoration DOM directly. Each `<div class="section ...-container">` →
`<div class="...-wrapper">` → `<div class="block-name">` mirrors what the
EDS pipeline would produce, so the existing block CSS targets it correctly.

## Limitations to know about

- Blocks that need JS (forms, commerce, modal, quiz, search, etc.) will be
  visually present but non-functional — their JS is not loaded.
- The CSS variables used by the project (`--frescopa-color-*`,
  `--type-*`, `--spacing-*`) live in `/styles/styles.css`. If you delete
  that link, the pages will lose colors and typography.
- Image URLs in the demo pages point to Unsplash; replace with your own
  assets as needed.
