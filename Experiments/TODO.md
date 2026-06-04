# Content Experiment Runner And IG Implementation Plan

Primary working plan for the Frescopa Information Gain and content experiment
work.

## Current Assumptions

- Project target: Frescopa.
- V1 uses one topic cluster only: `unknown`.
- `unknown` represents all current Frescopa pages and prompts until narrower
  clusters are introduced.
- The page is the concrete capture, indexing-approximation, editing, and
  page-score unit.
- The cluster is the internal aggregation key for topic-level scoring, QAT
  grouping, reporting, and recommendation bundles.
- Recommendations are cluster-specific and include affected pages.
- Frescopa claims live in `Experiments/data/example_claims_config.json`.
- The old Lovesac claim config is obsolete.
- V1 scoring is deterministic and heuristic first. Human or LLM judging is a
  later calibration layer, not required for the first scorer.
- Next queued milestone: implement the Section 2.1 page-level Information
  Gain scorer and cluster aggregation layer for the active `unknown` cluster.

## Goal

Test whether controlled content edits improve page-level Information Gain,
cluster-level aggregation scores, and AI-mediated discovery outcomes.

V1 loop:

1. Render target Frescopa pages locally with AEM CLI.
2. Capture each baseline page as a structured `PageSnapshot`.
3. Generate or provide a controlled edit plan.
4. Apply the variant through product mock JSON or a runtime DOM overlay.
5. Re-render and evaluate baseline vs variant at page level and cluster level.
6. Save artifacts and a short comparison report.

## Next Implementation Milestone

Build the Section 2.1 static scorer before adding more experiment automation.
The scorer runs without live LLM calls.

Scope:

- read one or more rendered `PageSnapshot` objects;
- assign a `PageScore` to each snapshot;
- group page scores by `cluster`;
- emit a `ClusterScore` for each cluster;
- compare baseline vs variant scores when both are available;
- write machine-readable JSON artifacts and a short `report.md`.

Out of scope for this milestone:

- splitting `unknown` into real topic clusters;
- live AI answer collection;
- LLM rubric judging;
- automatic CMS writes;
- rebuilding HAR mocks with `npm run build:mocks`;
- optimizing weights from historical QAT data.

Preferred implementation location:

```text
Experiments/sources/content_runner/
```

Preferred config location:

```text
Experiments/config/ig_scoring_config.json
```

The config defines active clusters, dimension weights, thresholds, canonical
claims, required topic coverage, and recommendation mappings. V1 configures
only `unknown`.

## Quick Commands

Install dependencies once:

```bash
npm install
```

Run the local AEM dev server:

```bash
npx -y @adobe/aem-cli up --url https://main--frescopa--andreibbarbu.aem.page --no-open --forward-browser-logs
```

Inspect rendered/local output:

```bash
curl http://localhost:3000/
curl http://localhost:3000/index.plain.html
curl http://localhost:3000/index.md
```

Find the ProductSearch mock file for a SKU on PowerShell:

```powershell
Select-String -Path tools\mock-commerce\responses\*.json -Pattern '"sku": "HBDR212"' |
  Select-Object -ExpandProperty Path -Unique
```

Regenerate PDP mocks after editing ProductSearch data:

```bash
node tools/mock-commerce/synthesize-pdp.mjs
```

## Local Rendering Model

```text
AEM preview content
  -> served through local AEM CLI
  -> decorated by Edge Delivery Services code in this repo
  -> enriched with mocked commerce data from tools/mock-commerce
```

Relevant files:

- `LOCAL_DEV.md`: local server and AEM preview proxy.
- `MODIFY_CONTENT.md`: product/catalog mock editing guide.
- `head.html`: loads `scripts/mock-commerce.js` before commerce/dropin code.
- `tools/mock-commerce/responses/*.json`: product/catalog mutation surface.
- `tools/mock-commerce/synthesize-pdp.mjs`: regenerates PDP mock responses.
- `scripts/aem.js`: core EDS helper library. Do not modify for experiments.
- `blocks/product-list-page-custom/`: PLP product query and rendering.
- `blocks/product-details/` and `scripts/initializers/pdp.js`: PDP rendering.

## Mutation Surfaces

### Product Mock JSON

Use product mock edits for product names, descriptions, prices, images, and
PLP/PDP product data.

Edit the `ProductSearch` file, not the generated `GET_PRODUCT_DATA` file. The
PDP mocks are regenerated from ProductSearch data.

Concrete example for SKU `HBDR212`:

```text
Source file: tools/mock-commerce/responses/4c7efb5dc3172d4a.json
Product path: /products/hbdr212/hbdr212
Fields: productView.name, productView.shortDescription, productView.price
```

Example edit target:

```text
productView.shortDescription =
"Dark roast coffee with chocolate notes, toasted nuts, and a smooth smoky finish."
```

After editing ProductSearch data, run
`node tools/mock-commerce/synthesize-pdp.mjs` and reload the PLP/PDP in a fresh
browser context.

### Runtime DOM Overlays

Use DOM overlays for AEM-authored headings, banners, marketing copy, CTAs,
lists, and FAQ-like content.

DOM overlays are evaluation-only and do not write back to AEM. Edits are keyed
by generated node ID, not invented selectors.

Example edit output:

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

DOM application contract:

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

## PageSnapshot Contract

Use Playwright to open the fully rendered local page. Do not use raw `curl` HTML
as the main evaluator input, because raw HTML is captured before EDS
decoration, block JS, and commerce dropins finish rendering product content.

`PageSnapshot` is the capture format for a concrete URL and the input for
page-level scoring. The scorer emits a `PageScore` for each snapshot, then
groups scored pages by `cluster` and emits `ClusterScore` outputs.

Render contract:

```python
async def render_page(browser, path):
    page = await browser.new_page()
    await page.goto(f"http://localhost:3000{path}", wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle")
    await page.locator("main").wait_for()
    return page
```

Expected `PageSnapshot` shape:

```json
{
  "url": "/coffee",
  "title": "Coffee",
  "cluster": "unknown",
  "meta": {
    "description": "..."
  },
  "visible_text": "...",
  "headings": [],
  "sections": [],
  "ctas": [],
  "links": [],
  "editable_nodes": [
    {
      "id": "n001",
      "selector": "[data-exp-id='n001']",
      "tag": "h1",
      "text": "Coffee",
      "source": "aem-dom"
    }
  ],
  "products": [
    {
      "sku": "HBDR212",
      "name": "House Blend - Dark Roast",
      "description": "Dark roast coffee with chocolate notes...",
      "price": "$14.99",
      "href": "http://localhost:3000/products/hbdr212/hbdr212"
    }
  ]
}
```

Extraction notes:

- generate stable `data-exp-id` attributes for editable visible text nodes;
- include only visible and meaningful text;
- skip `script`, `style`, `noscript`, and SVG internals;
- keep product extraction tied to rendered DOM first;
- add direct mock-commerce JSON references later if needed.

## IG Scoring Config Contract

Create the V1 scorer config at:

```text
Experiments/config/ig_scoring_config.json
```

Initial shape:

```json
{
  "version": "v1",
  "default_cluster": "unknown",
  "dimensions": [
    "intent_coverage",
    "specificity",
    "structure",
    "trust",
    "originality",
    "search_readiness",
    "media_readiness",
    "risk_control"
  ],
  "clusters": {
    "unknown": {
      "label": "All current Frescopa content",
      "page_weights": {
        "intent_coverage": 0.125,
        "specificity": 0.125,
        "structure": 0.125,
        "trust": 0.125,
        "originality": 0.125,
        "search_readiness": 0.125,
        "media_readiness": 0.125,
        "risk_control": 0.125
      },
      "cluster_weights": {
        "intent_coverage": 0.125,
        "specificity": 0.125,
        "structure": 0.125,
        "trust": 0.125,
        "originality": 0.125,
        "search_readiness": 0.125,
        "media_readiness": 0.125,
        "risk_control": 0.125
      },
      "thresholds": {
        "page_score": 0.6,
        "cluster_score": 0.6,
        "page_search_readiness": 0.6,
        "cluster_search_readiness": 0.6
      },
      "required_topics": [],
      "canonical_claims_file": "Experiments/data/example_claims_config.json",
      "recommendation_mappings": {}
    }
  }
}
```

Config rules:

- keep weights normalized to sum to `1.0`;
- keep thresholds in config, not hard-coded in the scorer;
- if a dimension cannot be estimated yet, emit a low-confidence default and a
  visible issue rather than dropping the dimension;

## Evaluation Model

### Section 2.1: Page-Level IG Scoring And Cluster Aggregation

The scorer accepts one or more `PageSnapshot` objects, emits one `PageScore`
per page, groups pages by `cluster`, and emits one `ClusterScore` per cluster.

Implement the V1 dimensions heuristically first:

- intent coverage;
- specificity and boundedness;
- structured answerability;
- evidence and trust support;
- originality / information gain relative to alternatives;
- search and discovery readiness;
- media and product readiness;
- content risk control.

V1 heuristic signals:

- `intent_coverage`: required topics or canonical claims represented in visible
  text, headings, product cards, or PDP content.
- `specificity`: prices, quantities, delivery timing, named SKUs, roast levels,
  flavor notes, compatibility constraints, exclusions, policy limits, or other
  bounded claims.
- `structure`: useful headings, lists, tables, FAQ-like sections, product
  cards, comparison units, and concise sectioning.
- `trust`: internally consistent claims, concrete product facts, policy details,
  internal links, contact or organization cues, and supported freshness or
  quality statements.
- `originality`: useful claims or combinations of claims that are not generic;
  when no reference set is available, mark the estimate as low confidence.
- `search_readiness`: rendered visible content, title, meta description,
  canonical URL or stable URL, internal links, non-empty main content, and no
  duplicate-page purpose.
- `media_readiness`: product names, descriptions, prices, image URLs or alt
  context, and consistency between PLP/PDP product facts.
- `risk_control`: low duplication, no keyword stuffing, no thin generated copy,
  no contradictory claims, and no pages created only for tiny query variations.

Scoring rules:

- page dimension scores are normalized floats in `[0, 1]`;
- `PageScore.score` is the weighted average of the page dimensions using
  `page_weights`;
- cluster dimension scores are computed by aggregating page dimension scores
  and cross-page signals for all pages in the cluster;
- `ClusterScore.score` is the weighted average of cluster dimensions using
  `cluster_weights`;
- `passed` is `true` only when the score and all active configured threshold
  checks pass;
- every low dimension emits at least one issue or recommendation signal.

`PageScore` contract:

```json
{
  "url": "/coffee",
  "cluster": "unknown",
  "score": 0.58,
  "passed": false,
  "dimensions": {
    "intent_coverage": 0.55,
    "specificity": 0.7,
    "structure": 0.5,
    "trust": 0.6,
    "originality": 0.45,
    "search_readiness": 0.75,
    "media_readiness": 0.65,
    "risk_control": 0.8
  },
  "signals": {},
  "issues": [],
  "editable_nodes": [],
  "products": []
}
```

`ClusterScore` contract:

```json
{
  "cluster": "unknown",
  "score": 0.62,
  "passed": true,
  "page_count": 3,
  "pages": [
    "/",
    "/coffee",
    "/products/hbdr212/hbdr212"
  ],
  "dimensions": {},
  "signals": {
    "coverage": [],
    "consistency": []
  },
  "issues": [],
  "recommendations": []
}
```

`scores.json` comparison contract:

```json
{
  "baseline": {
    "page_scores_file": "baseline/page-scores.json",
    "cluster_scores_file": "baseline/cluster-scores.json"
  },
  "variant": {
    "page_scores_file": "variant/page-scores.json",
    "cluster_scores_file": "variant/cluster-scores.json"
  },
  "deltas": {
    "pages": {},
    "clusters": {}
  },
  "summary": {
    "improved": true,
    "failure_types": []
  }
}
```

Cluster-specific recommendation rules live in the cluster config. Generic
fallback recommendations are allowed when the output still includes `cluster`
and `affected_pages`.

Recommendation object contract:

```json
{
  "cluster": "unknown",
  "affected_pages": [
    "/coffee"
  ],
  "source": {
    "level": "page",
    "dimension": "specificity",
    "threshold": 0.6,
    "observed": 0.42
  },
  "priority": "P1",
  "action": "Add concrete flavor notes, package size, roast level, and brewing guidance to the affected product card or PDP.",
  "rationale": "The affected page is the editable surface that caused the low cluster-specific specificity signal."
}
```

Recommendation rules:

- page failures produce edit-targeted recommendations for the failing URL;
- cluster failures produce cluster-specific recommendations with all affected
  URLs attached;
- runtime QAT failures later produce cluster-specific recommendations, because
  QAT metrics are grouped by cluster and measurement window;
- a recommendation without `affected_pages` is incomplete unless the issue is a
  cluster-config issue.

Production intervention surfaces:

| Surface | Change type | Primary role |
| --- | --- | --- |
| AEM-authored content update | Canonical page copy, headings, blocks, FAQs, links, metadata. | Durable content revision. |
| CMS workflow | Review, approval, publishing, ownership, audit trail. | Governance of content changes. |
| Edge/CDN variant | Alternate response or transformation served by routing rules. | Variant testing or targeted exposure before canonical revision. |

Recommendation-to-intervention mapping:

| Failed signal | Recommendation action | Intervention surface |
| --- | --- | --- |
| Low specificity | Add prices, timing, quantities, constraints, product facts, or eligibility conditions. | AEM copy or product data. |
| Low structure | Add headings, lists, comparison tables, steps, or FAQ-like sections. | AEM-authored page blocks. |
| Low media readiness | Improve product name, description, price, image context, or PLP/PDP consistency. | Product or commerce data. |
| Low search readiness | Clarify title, metadata, canonical role, internal links, or duplicate page purpose. | AEM metadata, page structure, or routing configuration. |
| IG-F2 narrative misalignment | Rewrite affected pages around canonical claims. | AEM copy, PDP content, or reviewed CMS update. |

Example:

| Diagnosis | Recommendation | Intervention | Evaluation |
| --- | --- | --- | --- |
| Low specificity on `/coffee`. | Add roast level, package size, flavor notes, and brewing guidance. | Update product data or authored copy. | Compare page and cluster score deltas. |

### Section 2.3: QAT Runtime Metrics

Current code already computes:

- presence;
- prominence;
- citation share;
- alignment.

V1 aggregates QAT metrics under `unknown`.

### Failure Types

When a variant fails, record the likely failure type:

- IG-F1: visibility gap;
- IG-F2: narrative misalignment;
- IG-F3: hollow IG;
- IG-F4: drift after revision;
- IG-F5: cross-channel inconsistency;
- IG-F6: discovery readiness failure.

### Search-System Reference URLs

Keep these as engineering references for crawlability, indexing, helpful
content, AI search readiness, and generated-content guardrails:

- https://developers.google.com/search/docs/fundamentals/seo-starter-guide
- https://developers.google.com/search/docs/fundamentals/how-search-works
- https://developers.google.com/search/docs/fundamentals/creating-helpful-content
- https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- https://developers.google.com/search/docs/fundamentals/using-gen-ai-content

## Runner Output

Store each run under:

```text
Experiments/outputs/content-runs/<run_id>/
```

Minimum artifacts:

- `run.json`: run ID, config path, input paths, clusters, variant IDs,
  timestamps;
- `config.json`: resolved scorer config copied for reproducibility;
- `baseline/pages.json`: extracted baseline page snapshots;
- `baseline/page-scores.json`: baseline page-level IG scores;
- `baseline/cluster-scores.json`: baseline cluster-level IG/QAT scores available for the run;
- `variant/manifest.json`: applied edits or product patches;
- `variant/pages.json`: extracted variant page snapshots;
- `variant/page-scores.json`: variant page-level IG scores;
- `variant/cluster-scores.json`: variant cluster-level IG/QAT scores available for the run;
- `scores.json`: comparison and deltas;
- `report.md`: concise human-readable summary.

`report.md` contains:

- pages evaluated;
- cluster evaluated;
- baseline score vs variant score;
- dimension deltas;
- recommendations generated;
- likely failure type if the variant did not improve;
- commands or files used for product mock mutation when applicable.

Add rendered HTML snapshots and screenshots once the basic loop is stable:

```python
async def save_rendered_snapshot(page, out_file):
    html = await page.evaluate("document.documentElement.outerHTML")
    write_text(out_file, html)
```

If product mock JSON changes, old rendered snapshots are stale. Regenerate
snapshots before evaluating that variant.

## Guardrails

- Use fresh browser contexts per experiment to avoid local/session storage leaks.
- Store every experiment artifact.
- Do not let the agent edit scripts, styles, hidden config, or arbitrary HTML.
- Keep DOM edits mapped by generated IDs.
- Prefer visible text and metadata for the first evaluator.
- Add screenshots, accessibility tree, or structured data only after the MVP.
- Avoid `npm run build:mocks` during experiments unless the intent is to rebuild
  from HAR files and overwrite edited ProductSearch mocks.

## Implementation Checklist

1. [ ] Scaffold the runner and config: add `Experiments/sources/content_runner/`
   and `Experiments/config/ig_scoring_config.json` with the `unknown` cluster,
   weights, thresholds, and empty recommendation mappings.
2. [ ] Define the implementation contracts in code: `PageSnapshot`,
   `PageScore`, `ClusterScore`, recommendation objects, and baseline-vs-variant
   comparison JSON.
3. [ ] Implement page rendering and snapshot extraction: use Playwright on
   `/coffee` plus one PDP such as `/products/hbdr212/hbdr212`, capture fully
   rendered content, and generate stable `data-exp-id` values for editable
   visible text nodes.
4. [ ] Implement the Section 2.1 static scorer: compute all eight deterministic
   page dimensions, aggregate scored pages into the `unknown` cluster, apply
   configured thresholds, and emit page/cluster pass-fail status.
5. [ ] Implement recommendation generation: map low page or cluster dimensions
   to rule-based recommendations with `cluster`, `affected_pages`, `source`,
   `priority`, `action`, and `rationale`.
6. [ ] Persist and compare runs: write artifacts under
   `Experiments/outputs/content-runs/`, generate `scores.json`, and produce a
   compact `report.md` with score deltas, recommendations, and failure mode.
7. [ ] Add mutation support for experiments: apply DOM edits by `data-exp-id`,
   mutate one SKU in ProductSearch mock JSON, and regenerate PDP mocks.
8. [ ] Integrate existing runtime metrics: wire the current Section 2.3 QAT
   metrics into the reporting layer while aggregating under `unknown`.
9. [ ] Add focused validation: tests for scoring math, thresholds,
   recommendations, cluster aggregation, and optional rendered HTML/screenshot
   artifacts after the basic loop is stable.
10. [ ] Split `unknown` into Frescopa topic clusters only after the single
    cluster workflow works end to end.
