from pathlib import Path
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sources"))

from ig_runtime_metrics import (  # noqa: E402
    BrandConfig,
    ClaimRule,
    aggregate_metrics,
    domain_matches_brand,
    normalize_domain,
    trace_metrics,
)


def test_domain_normalization_and_matching():
    assert normalize_domain("https://www.shop.unibuc.ro/path?q=1") == "shop.unibuc.ro"
    assert domain_matches_brand("https://support.unibuc.ro/help", ["unibuc.ro"])
    assert not domain_matches_brand("https://fakeunibuc.ro/help", ["unibuc.ro"])


def test_trace_metrics_with_brand_citation_and_claims():
    brand = BrandConfig(
        brand="frescopa-unibuc",
        domain_identifiers=("unibuc.ro",),
        text_identifiers=("Frescopa", "Unibuc-Frescopa"),
    )
    claims = {
        "unknown": [
            ClaimRule("mentions brand", (r"\bFrescopa\b",)),
            ClaimRule("mentions delivery", (r"\blivrare\b",)),
        ]
    }
    record = {
        "t": "2026-04-27T14:51:14+00:00",
        "q": "Cum comand?",
        "s": "aimode",
        "a": "Frescopa permite comenzi online.",
        "D": ["https://unibuc.ro/page", "https://example.com/ref"],
        "success": True,
        "topic": "unknown",
    }

    metrics = trace_metrics(record, brand, claims)

    assert metrics["m_pres"] == 1.0
    assert metrics["rank_B"] == 1
    assert metrics["m_prom"] == 1.0
    assert metrics["m_cite"] == pytest.approx(0.5)
    assert metrics["m_align"] == 0.5


def test_trace_metrics_with_text_presence_without_citation():
    brand = BrandConfig(
        brand="frescopa-unibuc",
        domain_identifiers=("unibuc.ro",),
        text_identifiers=("Frescopa",),
    )
    record = {
        "t": "2026-04-27T14:51:14+00:00",
        "q": "Ce este?",
        "s": "gemini",
        "a": "Serviciul este disponibil. Frescopa apare in al doilea enunt.",
        "D": [],
        "success": True,
        "topic": "unknown",
    }

    metrics = trace_metrics(record, brand, {})

    assert metrics["m_pres"] == 1.0
    assert metrics["rank_B"] == 2
    assert metrics["m_prom"] == 0.5
    assert metrics["m_cite"] == 0.0
    assert metrics["m_align"] is None


def test_trace_metrics_uses_citation_rank_when_brand_is_not_named():
    brand = BrandConfig(
        brand="frescopa-unibuc",
        domain_identifiers=("unibuc.ro",),
        text_identifiers=("Frescopa",),
    )
    record = {
        "t": "2026-04-27T14:51:14+00:00",
        "q": "Unde gasesc informatii?",
        "s": "copilot",
        "a": "Consulta sursele oficiale pentru detalii.",
        "D": ["https://example.com/ref", "https://unibuc.ro/page"],
        "success": True,
        "topic": "unknown",
    }

    metrics = trace_metrics(record, brand, {})

    assert metrics["m_pres"] == 1.0
    assert metrics["rank_B"] == 2
    assert metrics["m_prom"] == 0.5
    assert metrics["m_cite"] == pytest.approx(0.5)


def test_aggregate_metrics_all_frequency():
    df = pd.DataFrame(
        [
            {
                "t": "2026-04-27T14:51:14+00:00",
                "q": "q1",
                "topic": "unknown",
                "system": "aimode",
                "success": True,
                "m_pres": 1.0,
                "m_prom": 1.0,
                "m_cite": 0.5,
                "m_align": 0.5,
                "response_time_ms": 100.0,
                "d_count": 2,
            },
            {
                "t": "2026-04-27T14:52:14+00:00",
                "q": "q2",
                "topic": "unknown",
                "system": "aimode",
                "success": True,
                "m_pres": 0.0,
                "m_prom": 0.0,
                "m_cite": 0.0,
                "m_align": 1.0,
                "response_time_ms": 300.0,
                "d_count": 0,
            },
        ]
    )

    summary = aggregate_metrics(df, freq="all")

    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["n_traces"] == 2
    assert row["PresenceRate"] == 0.5
    assert row["ProminenceMean"] == 0.5
    assert row["CitationShareMean"] == 0.25
    assert row["AlignmentMean"] == 0.75
    assert row["MeanResponseTimeMs"] == 200.0
