import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)

cmd = [
    sys.executable,
    str(ROOT / "sources" / "ig_runtime_metrics.py"),
    str(DATA / "information_gain_metrics_ALLDATES_ALLPLATFORMS_ALLCLUSTERS.json"),

    "--brand", "frescopa-unibuc",

    # one flag, multiple values
    "--brand-name", "Unibuc-Frescopa", "Frescopa",

    "--brand-domain", "unibuc.ro", "shop.unibuc.ro",

    "--claims-json", str(DATA / "example_claims_config.json"),
    "--freq", "all",
    "--out", str(OUTPUTS / "metrics_by_trace.csv"),
    "--summary-out", str(OUTPUTS / "metrics_summary.csv"),
]

subprocess.run(cmd, check=True)
