# Information Gain Metrics

This repository computes runtime information gain metrics for Query-Answer Traces (QAT). It normalizes retrieved sources, measures brand presence, prominence, citation share, and claim alignment, then exports trace-level and aggregate CSV summaries.

Project notes and paper material are available in [Overleaf](https://www.overleaf.com/project/693dbca494ef60186839f6ef).

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

## Implementation Plan

```text
Raw QAT JSON
   -> normalize D
   -> compute trace-level m_pres, m_prom, m_cite, m_align
   -> aggregate by topic/system/time window
   -> compare against IGC thresholds Phi_C
   -> trigger failure categories IG-F1 ... IG-F5
   -> generate content recommendations
```
