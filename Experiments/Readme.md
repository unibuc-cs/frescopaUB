
```text
Raw QAT JSON
   -> normalize D
   -> compute trace-level m_pres, m_prom, m_cite, m_align
   -> aggregate by topic/system/time window
   -> compare against IGC thresholds Phi_C
   -> trigger failure categories IG-F1 ... IG-F5
   -> generate content recommendations
```


### Structure to follow
```text 
data/
  information_gain_metrics_all.json

config/
  brands.json
  claims_config.json
  thresholds.json

src/
  ig_runtime_metrics.py
  api_fetch.py
  aggregate_metrics.py
  failure_taxonomy.py

outputs/
  metrics_by_trace.csv
  metrics_summary.csv
  failures.csv
```

