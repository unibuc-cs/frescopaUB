# Modifying Content on the Local (Offline) Frescopa Site

This guide explains how to change product text, prices, and images that
appear on the **local** copy of the Frescopa site without touching the
real Adobe Commerce / AEM backends. It assumes the project is already
running locally per `LOCAL_DEV.md`.

The content shown on `/coffee`, `/tea`, `/machines`, `/accessories`,
and every `/products/<urlKey>/<sku>` page is served from a small set of
captured GraphQL response files in
`tools/mock-commerce/responses/`. Editing those files changes what the
site shows, immediately, with no server restart.

## How the offline data is laid out

- `tools/mock-commerce/responses/*.json` — recorded `ProductSearch`
  responses (one per category) and synthesized `GET_PRODUCT_DATA`
  responses (one per SKU). The `ProductSearch` files are the **source of
  truth** for product cards on listing pages and for the synthesizer.
- `tools/mock-commerce/manifest.json` — index that maps a request
  signature → response file. You don't normally edit this by hand.
- `mock-assets/` — every product image, served at `/mock-assets/<file>`.

Currently covered (17 products): coffee bags, coffee pods, tea, coffee
machines, accessories.

## Steps to change product text or price

### 1. Identify the SKU you want to change

Open the product on `http://localhost:3000` (e.g. `/coffee`,
`/machines`, etc.) and either click into it or hover the link to see the
URL. The URL pattern is `/products/<urlKey>/<sku>`. The SKU is the part
after the last slash, **uppercased** in the JSON (e.g. URL
`/products/hbdr212/hbdr212` → SKU `HBDR212`).

### 2. Find the file that holds that SKU

```bash
grep -l "HBDR212" tools/mock-commerce/responses/*.json
```

You will usually see two or three matches:

- One `ProductSearch` file (lots of products in one JSON, one per
  category — the **source of truth**).
- One or two `GET_PRODUCT_DATA` files (synthesized — auto-generated
  copies, one per SKU casing).

Always edit the **`ProductSearch` file** (it's the longer one with
multiple products inside). The synthesizer will regenerate the
`GET_PRODUCT_DATA` files from it.

### 3. Edit the field you want to change

Open the file in your editor and locate the product block by SKU:

```json
{
  "name": "House Blend - Dark Roast",
  "sku": "HBDR212",
  "shortDescription": "A bold blend of Arabica and Robusta beans...",
  "urlKey": "hbdr212",
  "images": [{"url": "__MOCK_ORIGIN__/mock-assets/urn_aaid_aem_5f861728-...avif"}],
  "price": {
    "regular": {"amount": {"currency": "USD", "value": 14.99}},
    "final":   {"amount": {"currency": "USD", "value": 14.99}}
  }
}
```

You can change:

- `name` — the product title shown everywhere
- `shortDescription` — the description shown on listings and the PDP
- `price.regular.amount.value` and `price.final.amount.value` — the
  displayed price (set both to the same number for a normal price; set
  `final` lower than `regular` for a sale)
- `images[0].url` — point at any local image (see step 5)

> Keep the JSON valid: don't drop quotes, commas, or braces. The page
> silently breaks if the JSON is malformed.

### 4. Regenerate the per-product detail pages

The PDP uses a separate file the synthesizer creates from the
`ProductSearch` data. Run:

```bash
node tools/mock-commerce/synthesize-pdp.mjs
```

This rewrites the `GET_PRODUCT_DATA` mocks for every SKU in a few
milliseconds. (No server restart needed — the dev server reads the file
on every request.)

### 5. Reload the browser

Hard-refresh (`Cmd+Shift+R` / `Ctrl+Shift+R`) the page. New text and
prices appear immediately.

## Changing or adding an image

1. Drop the new image into `mock-assets/` (any common format works:
   `.jpg`, `.png`, `.webp`, `.avif`).
2. In the `ProductSearch` JSON, set the product's
   `images[0].url` to `__MOCK_ORIGIN__/mock-assets/<your-file>`.
   The `__MOCK_ORIGIN__` placeholder is replaced at runtime with
   `http://localhost:3000` so it works on every machine.
3. Re-run `node tools/mock-commerce/synthesize-pdp.mjs` and reload.

## Adding a brand-new product

1. Open the right `ProductSearch` file (e.g. the bagged-coffee one for a
   new coffee bag). Identify the matching category by inspecting
   `manifest.json` — entries have `variables.filter.categoryPath` such
   as `bagged-coffee`, `coffee-pods`, `tea`, `coffee-machines`,
   `accessories`.
2. Copy an existing product block in `data.productSearch.items` and
   change the `sku`, `name`, `urlKey`, `shortDescription`, image URL,
   and price. Increment `data.productSearch.total_count` and
   `data.productSearch.page_info.page_size` to match the new item count.
3. Run `node tools/mock-commerce/synthesize-pdp.mjs`. The synthesizer
   will create a PDP mock for the new SKU automatically (covering both
   upper- and lowercase casings).
4. Reload `/<category-page>`. The product card appears, and clicking
   it opens a working detail page.

## What you cannot change locally

- **Page chrome** (page headings, marketing banners, footer text,
  breadcrumb labels, navigation labels) is authored in AEM and
  reverse-proxied from `https://main--frescopa--andreibbarbu.aem.page`.
  Edits there must be made by an AEM author. Local file changes won't
  affect them.
- **Cart / checkout / login flows** are not mocked. They rely on live
  Commerce mutations.

## Caveat: rebuilding from HARs overwrites your edits

The `npm run build:mocks` script rebuilds the `ProductSearch` files
from the recorded `.har` files in the project root. If you only ran
`synthesize-pdp.mjs` after editing, your changes are safe; but a full
`npm run build:mocks` would replace the `ProductSearch` JSON with the
freshly-extracted version and your edits would be lost.

If you plan to keep edits across rebuilds, work on a separate branch or
copy the edited file aside before rebuilding.

## Quick recap (cheat sheet)

```bash
# 1. Find the file
grep -l "<SKU>" tools/mock-commerce/responses/*.json

# 2. Edit the ProductSearch JSON (name / shortDescription / price / image)

# 3. Regenerate PDP mocks
node tools/mock-commerce/synthesize-pdp.mjs

# 4. Hard-refresh the browser
```

That's the whole loop — edit JSON → run synthesizer → refresh.
