# Content Experiment Runner

This note describes a practical first version of the agent loop we want:
programmatically change content, render the real local site, evaluate the
result, and compare it with a baseline.

The recommended first implementation is:

1. mutate catalog/product content through the existing mock-commerce JSON files;
2. render real local Frescopa pages with Playwright;
3. extract a structured page model from the rendered DOM;
4. let an agent propose controlled text edits;
5. apply those edits back to the DOM;
6. run the LLM/search-style evaluation against baseline and variant.

## How Frescopa Renders Locally

Start the site with the documented local AEM command:

```bash
npx -y @adobe/aem-cli up --url https://main--frescopa--andreibbarbu.aem.page --no-open
```

The browser then opens pages from:

```text
http://localhost:3000
```

The local page is a mix of three layers:

```text
AEM preview content
  -> served through the local AEM CLI
  -> decorated by Edge Delivery Services code in this repo
  -> enriched with mocked commerce data from tools/mock-commerce
```

Useful files to inspect:

- `LOCAL_DEV.md`
  Describes the local server. The important bit is that localhost serves local
  code but reverse-proxies page content from the Frescopa AEM preview backend.

- `head.html`
  Loads the import map, global CSS, `scripts/mock-commerce.js`, `scripts/aem.js`,
  `scripts/scripts.js`, `scripts/configs.js`, and `scripts/commerce.js`.
  The order matters: the mock fetch layer is installed before commerce/dropin
  code starts fetching data.

- `scripts/mock-commerce.js`
  Overrides `window.fetch` for known commerce GraphQL hosts. It computes a
  request signature, looks it up in `tools/mock-commerce/manifest.json`, and
  returns a recorded response from `tools/mock-commerce/responses/`.

- `tools/mock-commerce/responses/*.json`
  The product/catalog mutation surface. `ProductSearch` response files are the
  source of truth for product listing cards and for synthesized PDP responses.

- `tools/mock-commerce/synthesize-pdp.mjs`
  Regenerates `GET_PRODUCT_DATA` PDP mocks from the `ProductSearch` files.
  Run this after editing product names, short descriptions, prices, or images.

- `config.json`
  Defines Commerce endpoints and headers. In local experiments, requests to
  these endpoints are intercepted by `scripts/mock-commerce.js`.

- `scripts/configs.js`
  Loads `config.json` and exposes values such as `commerce-endpoint`.

- `scripts/scripts.js`
  Main page loader. `loadPage()` initializes config, initializes dropins,
  decorates sections/blocks, detects category/PDP pages, and loads lazy content.

- `scripts/aem.js`
  Core EDS helper library. It decorates sections and blocks and loads block JS.
  Do not modify this file for the experiment runner.

- `blocks/product-list-page-custom/product-list-page-custom.js`
  Category/product-listing block. It reads the authored block config, builds a
  `ProductSearch` query, calls `performCatalogServiceQuery()`, and renders the
  product listing UI.

- `blocks/product-list-page-custom/ProductList.js`
  Renders product cards: image, product name, short description, price, and PDP
  link.

- `scripts/initializers/pdp.js`
  PDP initializer. Reads the SKU from metadata or URL and fetches product data
  through the PDP dropin API.

- `blocks/product-details/product-details.js`
  PDP block. Renders the PDP dropin containers: gallery, header, price, short
  description, options, quantity, description, and attributes.

## MVP Flow

### 1. Baseline Render

Use Playwright to open the real local page. Do not rely on raw `curl` HTML for
the evaluator, because raw HTML does not include everything produced by EDS
decoration, block JS, and commerce dropins.

Pseudocode:

```python
async def render_page(browser, path):
    page = await browser.new_page()
    await page.goto(f"http://localhost:3000{path}", wait_until="domcontentloaded")

    # Wait for page decoration and late product rendering.
    await page.wait_for_load_state("networkidle")
    await page.locator("main").wait_for()

    return page
```

### 2. Extract A Page Model

The evaluator should receive a stable JSON object, not arbitrary HTML. The page
model should include visible text, metadata, editable nodes, and product data.

Example model:

```json
{
  "url": "/coffee",
  "title": "Coffee",
  "meta": {
    "description": "..."
  },
  "visible_text": "...",
  "editable_nodes": [
    {
      "id": "n001",
      "selector": "[data-exp-id='n001']",
      "tag": "h1",
      "text": "Coffee",
      "source": "aem-dom"
    },
    {
      "id": "n002",
      "selector": "[data-exp-id='n002']",
      "tag": "p",
      "text": "Freshly roasted blends for every routine.",
      "source": "aem-dom"
    }
  ],
  "products": [
    {
      "sku": "HBDR212",
      "name": "House Blend - Dark Roast",
      "description": "A bold blend of Arabica and Robusta beans...",
      "price": 14.99
    }
  ]
}
```

Extraction pseudocode:

```python
async def extract_page_model(page, path):
    return await page.evaluate("""
    (path) => {
      const editableTags = new Set(["H1", "H2", "H3", "P", "LI", "A", "BUTTON"]);
      const skip = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "SVG"]);
      let counter = 0;

      const editableNodes = [...document.querySelectorAll("main h1, main h2, main h3, main p, main li, main a, main button")]
        .filter((el) => editableTags.has(el.tagName))
        .filter((el) => !skip.has(el.tagName))
        .filter((el) => el.innerText && el.innerText.trim().length > 2)
        .map((el) => {
          const id = `n${String(++counter).padStart(3, "0")}`;
          el.setAttribute("data-exp-id", id);
          return {
            id,
            selector: `[data-exp-id='${id}']`,
            tag: el.tagName.toLowerCase(),
            text: el.innerText.trim(),
            source: "aem-dom"
          };
        });

      const products = [...document.querySelectorAll(".product-list-page-custom .list li")]
        .map((el) => ({
          name: el.querySelector(".name")?.innerText?.trim() || "",
          description: el.querySelector(".description")?.innerText?.trim() || "",
          price: el.querySelector(".price")?.innerText?.trim() || "",
          href: el.querySelector("a[href*='/products/']")?.href || ""
        }))
        .filter((product) => product.name);

      return {
        url: path,
        title: document.title,
        meta: {
          description: document.querySelector("meta[name='description']")?.content || ""
        },
        visible_text: document.body.innerText,
        editable_nodes: editableNodes,
        products
      };
    }
    """, path)
```

### 3. Ask The Agent For Controlled Edits

The agent should return edits by node ID. Avoid letting the agent return
selectors it invented on its own.

Input to the agent:

```json
{
  "task": "Improve search relevance for a query like 'dark roast coffee with chocolate notes'.",
  "page": {
    "url": "/coffee",
    "editable_nodes": [
      {
        "id": "n002",
        "tag": "p",
        "text": "Freshly roasted blends for every routine."
      }
    ],
    "products": [
      {
        "sku": "HBDR212",
        "name": "House Blend - Dark Roast",
        "description": "A bold blend of Arabica and Robusta beans..."
      }
    ]
  }
}
```

Expected agent output:

```json
{
  "edits": [
    {
      "id": "n002",
      "replacement": "Explore dark roast coffee with deep chocolate notes, toasted nuts, and a smooth finish."
    }
  ]
}
```

### 4. Apply DOM Edits

Apply the agent edits to the same rendered page. The browser updates layout
immediately. For isolation, each experiment should still start from a fresh page
load and browser context.

Pseudocode:

```python
async def apply_dom_edits(page, edits):
    await page.evaluate("""
    (edits) => {
      for (const edit of edits) {
        const el = document.querySelector(`[data-exp-id='${edit.id}']`);
        if (!el) continue;
        el.textContent = edit.replacement;
        el.setAttribute("data-exp-edited", "true");
      }
    }
    """, edits)
```

### 5. Mutate Product/Catalog Data

Use this path for product names, product short descriptions, prices, and images.

Human-readable workflow:

```text
1. Find the `ProductSearch` JSON file that contains the SKU.
2. Edit `productView.name`, `productView.shortDescription`, price, or image URL.
3. Run `node tools/mock-commerce/synthesize-pdp.mjs`.
4. Open a fresh browser context and render the target page again.
```

Automation pseudocode:

```python
def mutate_product(search_response_file, sku, patch):
    data = read_json(search_response_file)

    for item in data["data"]["productSearch"]["items"]:
        product = item["productView"]
        if product["sku"] != sku:
            continue

        if "name" in patch:
            product["name"] = patch["name"]
        if "shortDescription" in patch:
            product["shortDescription"] = patch["shortDescription"]
        if "price" in patch:
            product["price"]["regular"]["amount"]["value"] = patch["price"]
            product["price"]["final"]["amount"]["value"] = patch["price"]

    write_json(search_response_file, data)
    run("node tools/mock-commerce/synthesize-pdp.mjs")
```

Example target:

```text
SKU: HBDR212
Source file: tools/mock-commerce/responses/4c7efb5dc3172d4a.json
Fields: productView.name, productView.shortDescription, productView.price
```

### 6. Evaluate Baseline vs Variant

Keep the evaluator input small and consistent. It should receive the same schema
for baseline and variant.

Pseudocode:

```python
async def run_experiment(path, agent, evaluator):
    baseline_page = await render_page(browser, path)
    baseline_model = await extract_page_model(baseline_page, path)
    baseline_score = await evaluator.score(baseline_model)
    await baseline_page.close()

    variant_page = await render_page(browser, path)
    variant_model_before = await extract_page_model(variant_page, path)
    edits = await agent.propose_edits(variant_model_before)
    await apply_dom_edits(variant_page, edits["edits"])
    variant_model_after = await extract_page_model(variant_page, path)
    variant_score = await evaluator.score(variant_model_after)
    await variant_page.close()

    return {
      "path": path,
      "baseline": baseline_score,
      "variant": variant_score,
      "delta": variant_score["score"] - baseline_score["score"],
      "edits": edits["edits"]
    }
```

## Snapshot Layer

Add snapshots after the MVP works. Use them to make LLM evaluations repeatable.

Recommended snapshot type:

```text
rendered snapshot = Playwright opens page, waits for render, saves final DOM
```

Rendered snapshot pseudocode:

```python
async def save_rendered_snapshot(page, out_file):
    html = await page.evaluate("document.documentElement.outerHTML")
    write_text(out_file, html)
```

Raw snapshots are possible:

```python
html = httpx.get("http://localhost:3000/coffee").text
```

But raw snapshots are less useful for this project because they happen before
EDS decoration and before commerce dropins finish rendering product content.

Important rule: if product mock JSON changes, old rendered snapshots are stale.
Regenerate the snapshot before evaluating that variant.

## Guardrails

- Use fresh browser contexts per experiment to avoid local/session storage leaks.
- Store every experiment artifact: baseline model, variant model, edits, scores,
  and optional rendered HTML snapshot.
- Do not let the agent edit scripts, styles, hidden config, or arbitrary HTML.
- Keep DOM edits mapped by generated IDs, not by agent-invented selectors.
- Prefer visible text and metadata for the first evaluator. Add screenshots,
  accessibility tree, or structured data later if the metric needs them.
- Re-run `node tools/mock-commerce/synthesize-pdp.mjs` after product JSON edits.
- Avoid `npm run build:mocks` during experiments unless you intentionally want
  to rebuild from HAR files and overwrite edited ProductSearch mocks.

## First Implementation Checklist

- [ ] Add a small runner under `tools/content-experiments/`.
- [ ] Start from two paths: `/coffee` and one PDP, for example `/products/hbdr212/hbdr212`.
- [ ] Implement Playwright rendering and page-model extraction.
- [ ] Implement DOM edit application by generated `data-exp-id`.
- [ ] Implement product JSON mutation for one SKU.
- [ ] Implement baseline vs variant evaluation with a stub scoring function.
- [ ] Persist experiment artifacts under an ignored output folder.
- [ ] Replace the stub scorer with the LLM/search-style evaluator.
- [ ] Add rendered snapshots once the basic loop is stable.
