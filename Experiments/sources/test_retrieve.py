import argparse
import json
import os
import re
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for environments not yet synced
    load_dotenv = None


API_KEY_ENV = "IG_API_KEY"
BASE_URL = "https://jeftla4bp5.execute-api.us-east-1.amazonaws.com/dev"
ROOT = Path(__file__).resolve().parents[1]
ENV_PATHS = (ROOT.parent / ".env", ROOT / ".env")


def load_local_env() -> None:
    env_path = next((path for path in ENV_PATHS if path.exists()), ENV_PATHS[0])

    if load_dotenv is not None:
        load_dotenv(env_path)
        return

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _sanitize_filename_component(value: str) -> str:
    value = re.sub(r"\s+", "_", value.strip())
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def build_output_filename(date: str | None, platform: str | None, cluster: str | None) -> str:
    date_part = _sanitize_filename_component(date) if date else "ALLDATES"
    platform_part = _sanitize_filename_component(platform) if platform else "ALLPLATFORMS"
    cluster_part = _sanitize_filename_component(cluster) if cluster else "ALLCLUSTERS"
    return f"information_gain_metrics_{date_part}_{platform_part}_{cluster_part}.json"


def download_information_gain_metrics(
    date: str | None = None,
    platform: str | None = None,
    cluster: str | None = None,
    out_folder: str | None = None,
) -> tuple[str | None, int]:
    load_local_env()
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"Missing {API_KEY_ENV} environment variable.")

    params = {"format": "download"}
    if date:
        params["date"] = date
    if platform:
        params["platform"] = platform
    if cluster:
        params["cluster"] = cluster

    response = requests.get(
        f"{BASE_URL}/monitoring/information-gain-metrics",
        headers={"x-api-key": api_key},
        params=params,
        timeout=60,
    )
    response.raise_for_status()

    data = response.json()

    # download with results returns a raw list; no results returns {records: [], total: 0, message: ...}
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("records", [])
    else:
        raise ValueError(f"Unexpected API response type: {type(data)!r}")

    if not records:
        message = data.get("message", "n/a") if isinstance(data, dict) else "n/a"
        print(f"No metrics found. Message: {message}")
        return None, 0

    filename = build_output_filename(date, platform, cluster)
    assert out_folder is not None, "out_folder must be provided"
    os.makedirs(out_folder, exist_ok=True)

    out_file_path = Path(out_folder) / filename
    with open(out_file_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    return filename, len(records)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download information gain metrics and save as JSON."
    )
    parser.add_argument("--date", help="Date in YYYY-MM-DD format")
    parser.add_argument("--platform", help="Platform identifier")
    parser.add_argument("--cluster", help="Cluster name")
    parser.add_argument("--out_folder", help="Output folder", default="./data")
    args = parser.parse_args()

    filename, count = download_information_gain_metrics(
        date=args.date,
        platform=args.platform,
        cluster=args.cluster,
        out_folder=args.out_folder
    )
    if filename:
        print(f"Downloaded {count} records -> {filename}")


if __name__ == "__main__":
    main()
