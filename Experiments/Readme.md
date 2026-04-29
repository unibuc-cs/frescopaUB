# Information Gain for AI-Mediated Discovery

This repository is the implementation workspace for the full Information Gain architecture described in `Docs/main_abs1.tex`: page-level IG scoring, Information Gain Cards, Query-Answer Trace collection, runtime evaluation, failure diagnosis, recommendation generation, and before/after measurement for GEO optimization.

The current code implements only an initial slice of the paper: the Section 2.3 Query-Answer Trace runtime metrics. It normalizes retrieved sources, measures brand presence, prominence, citation share, and claim alignment, then exports trace-level and aggregate CSV summaries.

Project notes and paper material are available in [Overleaf](https://www.overleaf.com/project/693dbca494ef60186839f6ef).

## Long-Term Scope

The long-term goal is to implement the complete workflow from the paper:

- score brand pages for specificity, structured answerability, evidence quality, differentiation, and novelty;
- maintain Information Gain Cards per topic cluster, including static requirements, runtime thresholds, temporal review rules, canonical claims, and recommendation mappings;
- collect and evaluate Query-Answer Traces across AI systems;
- detect visibility, citation, alignment, and persistence failures through the IG failure taxonomy;
- generate concrete content recommendations from static page weaknesses and runtime failures;
- support human and LLM-assisted judging for scalable annotation;
- evaluate interventions through controlled before/after measurements and, eventually, variant-aware routing and dashboards.

The short-term implementation plan at the end of this README covers the current QAT runtime-metrics piece only.

## Folder Organization

- `data/`: input JSON files downloaded from the information gain monitoring API, plus example claim configuration.
- `sources/`: implementation scripts for downloading data and computing runtime metrics.
- `tests/`: pytest coverage for metric extraction, domain matching, trace scoring, and aggregation behavior.
- `outputs/`: generated CSV results from local metric runs.
- `Docs/`: project documentation, paper drafts, and reference metric examples.
- `config/`: claim and configuration files used by local experiments.

## Script Roles

- `sources/test_retrieve.py`: downloads information gain metric records from the monitoring API into `data/`. It reads `IG_API_KEY` from `.env` or the environment and supports optional `date`, `platform`, and `cluster` filters.
- `sources/ig_runtime_metrics.py`: core metric implementation and CLI. It loads QAT JSON, computes `m_pres`, `m_prom`, `m_cite`, and `m_align`, then writes trace-level and aggregate CSV files.
- `sources/run_ig_runtime_metrics.py`: convenience runner with the current Frescopa/UNIBUC inputs, brand identifiers, claim config, and output paths.
- `tests/test_ig_runtime_metrics.py`: pytest suite validating domain normalization, brand matching, trace metrics, and aggregate summaries.

## Short-Term Implementation Plan

```text
Raw QAT JSON
   -> normalize D
   -> compute trace-level m_pres, m_prom, m_cite, m_align
   -> aggregate by topic/system/time window
   -> compare against IGC thresholds Phi_C
   -> trigger failure categories IG-F1 ... IG-F5
   -> generate content recommendations
```
