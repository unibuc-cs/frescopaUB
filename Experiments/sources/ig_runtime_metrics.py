"""
Runtime Information Gain Metrics for Query-Answer Traces (QAT)

Implement section 2.3 metrics:
 r = <t, q, s, D>
  m_pres, m_prom, m_cite, m_align

And aggregate them .

If no claims-json arg provided, AlignmentMean will be blank.

"""


import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Sequence
from urllib.parse import urlparse

import pandas as pd

EPS = 1e-9

@dataclass(frozen=True)
class BrandConfig:
    """ Brand identifier used by the runtime metrics
    domain_identifiers are compared against normalized domains from D
    text_identifiers are searched in the answer text a
    """

    brand: str
        domain_identifiers: Tuple[str, ...]
    text_identifiers: Tuple[str, ...]

@dataclass(frozen=True)
class ClaimRule:
    """A simple canonical-claim matcher for V1.

    A claim matches if at least one item in `any` is found in the answer.
    Items are interpreted as case-insensitive regex patterns.
    For a stricter rule, use patterns with word boundaries, e.g. r"\\bmodular\\b".

    In V2 - we can use an LLM to determine if a claim is supported by the answer, and use these rules as a backup for cases where the LLM is uncertain.
    """

    name: str
    any: Tuple[str, ...]

def normalize_domain(url_or_domain: str) -> str:
    """Normalize a URL/domain for stable comparison.

    For production, replace this with tldextract if you need robust eTLD+1 handling for domains such as
    co.uk, com.au, etc.
    """

    if not url_or_domain:
        return ""

    x = url_or_domain.strip().lower()
    if not x:
        return ""

    # urlparse needs the netloc
    parsed = urlparse(x if "://" in x else f"http://{x}")
    host = parsed.netloc or parsed.path
    host = host.split("@")[-1] # drop user info if any
    host = host.split(":")[0] # drop port if any
    host = host.strip("./")

    if host.startswith("www."):
        host = host[4:]


    return host

def normalize_domains(D: Sequence[str]) -> List[str]:
    """Normalize and deduplicate a list of domains while preserving order."""
    seen = set()
    out: List[str] = []

    for item in D or []:
        dom = normalize_domain(item)
        if dom and dom not in seen:
            seen.add(dom)
            out.append(dom)

    return  out

def domain_matches_brand(domain: str, brand_domains: Sequence[str]) -> bool:
    """Return True when a cited domain belongs to the brand.

    Allows exact matches and subdomain matches. Example:
    support.lovesac.com matches lovesac.com.
    """

    d = normalize_domain(domain)
    if not d:
        return False

    for b in brand_domains:
        bd = normalize_domain(b)
        if not bd:
            continue

        if d == bd or d.endswith("." + bd):
            return True

    return False

def first_identifier_position(text: str, identifiers: Sequence[str]) -> Optional[int]:
    """Return the first character offset of any brand identifier in text"""
    if not text:
        return None

    best: Optional[int] = None

    for ident in identifiers:
        if not ident:
            continue

        # Use word-ish boundaries to avoid mathing inside longer words.
        pattern = r"(?<![A-Za-z0-9])" + re.escape(ident) + r"(?![A-Za-z0-9])"
        m = re.search(pattern, text, re.IGNORECASE)

        if m:
            best = m.start() if best is None else min(best, m.start())

    return best

def text_has_identifier(text: str, identifiers: Sequence[str]) -> bool:
    """Return True if any brand identifier appears in the text."""
    return first_identifier_position(text, identifiers) is not None


def first_brand_citation_rank(
        D: Sequence[str],
        brand_domains: Sequence[str]
) -> Optional[int]:
    """Given D, the cited domains,
    return Rank of first brand-owned citation in D, 1-indexed."""
    domains = normalize_domains(D)

    for i, dom in enumerate(domains, start=1):
        if domain_matches_brand(dom, brand_domains):
            return i

    return None

def prominence_rank(record: Dict[str, Any], brand_config: BrandConfig) -> Optional[int]:
    """Compute rank_B(r).

    Priority:
      1. sentence rank of first textual brand mention in answer a;
      2. citation rank of first brand domain in D, if no textual mention exists.

    Sentence rank is interpretable and stable across providers, while citation rank covers answers
    where the brand is cited but not explicitly named in the generated text.
    """
    answer = record.get("a") or ""

    sent_rank = sentence_rank_of_first_identfier(answer, brand_config.text_identifiers)
    if sent_rank is not None:
        return sent_rank

    return first_brand_citation_rank(
        record.get("D") or [],
        brand_config.domain_identifiers,
    )

def load_claims(path: Optional[Path]) -> Dict[str, List[ClaimRule]]:
    """Load canonical claim rules grouped by topic/cluster.

    Expected JSON format:
    {
      "Product": [
        {"name": "mentions modularity", "any": ["\\bmodular\\b", "configurable"]},
        {"name": "mentions washable covers", "any": ["washable cover", "removable cover"]}
      ],
      "bean bag": [...]
    }
    """
    if not path:
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))

    claims: Dict[str, List[ClaimRule]] = {}

    for topic, rules in raw.items():
        claims[topic] = [
            ClaimRule(
                name=str(r.get("name", "claim")),
                any=tuple(map(str, r.get("any", []))),
            )
            for r in rules
        ]

    return claims

def match_claim(rule: ClaimRule, answer: str) -> float:
    """Return 1.0 if the canonical claim rule is matched, else 0.0."""
    if not answer:
        return 0.0

    for pattern in rule.any:
        if re.search(pattern, answer, flags=re.IGNORECASE):
            return 1.0

    return 0.0


def alignment_score(
    record: Dict[str, Any],
    claims_by_topic: Dict[str, List[ClaimRule]],
) -> Optional[float]:
    """Compute m_align(r), or None if Gamma_C is unavailable."""
    topic = record.get("topic") or record.get("cluster") or ""
    claims = claims_by_topic.get(topic, [])

    if not claims:
        return None

    answer = record.get("a") or ""

    return sum(match_claim(c, answer) for c in claims) / len(claims)


def trace_metrics(
        record: Dict[str, Any],
        brand : BrandConfig,
        claims_by_topic: Dict[str, List[ClaimRule]],
) -> Dict[str, Any]:
    """Compute all Section 2.3 trace-level metrics for one JSON record."""
    answer = record.get("a") or ""
    raw_D = record.get("D") or []
    D = normalize_domains(raw_D)
    topic = record.get("topic") or record.get("cluster")

    # Select the brand domains that have been cited in D (answer)
    brand_cited_domains = [
        d for d in D
        if domain_matches_brand(d, brand.domain_identifiers)
    ]

    brand_cited = len(brand_cited_domains) > 0
    brand_mentioned = text_has_identifier(answer, brand.text_identifiers)

    # Presence metric
    m_pres = 1.0 if (brand_mentioned or brand_cited) else 0.0

    # Rank metric, proeminence
    rank = prominence_rank(record, brand)
    m_prom = (1.0 / rank) if rank else 0.0

    # We use de-duplicated normalized domains..
    m_cite = len(brand_cited_domains) / (len(D) + EPS)

    m_align = alignment_score(record, claims_by_topic)

    return {
        "t": record.get("t"),
        "q": record.get("q"),
        "system": record.get("s"),
        "answer": answer,
        "topic": topic,
        "brand": record.get("brand"),
        "country": record.get("country"),
        "success": bool(record.get("success", False)),
        "response_time_ms": record.get("response_time_ms"),
        "d_count": len(D),
        "d_domains": "|".join(D),
        "brand_cited": brand_cited,
        "brand_cited_domains": "|".join(brand_cited_domains),
        "brand_mentioned": brand_mentioned,
        "rank_B": rank,
        "m_pres": m_pres,
        "m_prom": m_prom,
        "m_cite": m_cite,
        "m_align": m_align,
    }

def load_records(path: Path) -> List[Dict[str, Any]]:
    """Load QAT records from either a raw list or an API response object."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "records" in raw:
        return raw["records"]

    if isinstance(raw, list):
        return raw

    raise ValueError("Invalid JSON must be either a list of records or an object n object with a 'records' list.")

def aggregate_metrics(df: pd.DataFrame, freq: str = "7D") -> pd.DataFrame:
    """Aggregate Section 2.3 indicators per topic, system, and time window."""
    out = df.copy()

    out["t"] = pd.to_datetime(out["t"], errors="coerce", utc=True)
    out = out[out["success"] == True].copy()

    if out.empty:
        return pd.DataFrame()

    # Treat missing topic/system as explicit labels for stable groupby behavior.
    out["topic"] = out["topic"].fillna("__missing_topic__")
    out["system"] = out["system"].fillna("__missing_system__")

    if str(freq).lower() == "all":
        grouped = (
            out.groupby(["topic", "system"])
            .agg(
                n_traces=("q", "count"),
                PresenceRate=("m_pres", "mean"),
                ProminenceMean=("m_prom", "mean"),
                CitationShareMean=("m_cite", "mean"),
                AlignmentMean=("m_align", "mean"),
                MeanResponseTimeMs=("response_time_ms", "mean"),
                MedianResponseTimeMs=("response_time_ms", "median"),
                MeanCitationCount=("d_count", "mean"),
                time_start=("t", "min"),
                time_end=("t", "max"),
            )
            .reset_index()
        )
        return grouped

    grouped = (
        out.set_index("t")
        .groupby(["topic", "system", pd.Grouper(freq=freq)])
        .agg(
            n_traces=("q", "count"),
            PresenceRate=("m_pres", "mean"),
            ProminenceMean=("m_prom", "mean"),
            CitationShareMean=("m_cite", "mean"),
            AlignmentMean=("m_align", "mean"),
            MeanResponseTimeMs=("response_time_ms", "mean"),
            MedianResponseTimeMs=("response_time_ms", "median"),
            MeanCitationCount=("d_count", "mean"),
        )
        .reset_index()
        .rename(columns={"t": "window_start"})
    )

    return grouped

def sentence_rank_of_first_identfier(
        text:str,
        identifiers: Sequence[str]) -> Optional[int]:
    """Rank the first sentence containing a brand identifier, 1-indexed.

    This is an implementable interpretation of rank_B(r). It is easy to audit:
    if the brand appears in the first sentence, prominence = 1; if it first
    appears in the second sentence, prominence = 1/2; etc.
    """

    if not text:
        return None

    # Conservative sentence split; good enough for metric extraction.
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]

    # Take each sentences and verify if it contains the identifiers; stop at furst
    for i, sent in enumerate(sentences, start=1):
        if text_has_identifier(sent, identifiers):
            return i

    return None

def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("json_path", type=Path)
    parser.add_argument("--brand", default="lovesac")
    parser.add_argument("--brand-domain", nargs="+", default=[])
    parser.add_argument("--brand-name", nargs="+", default=[])
    parser.add_argument(
        "--claims-json",
        type=Path,
        default=None,
        help="JSON file containing canonical claim rules grouped by topic.",
    )
    parser.add_argument(
        "--freq",
        default="all",
        help="Pandas time frequency - grouping on time window if you want, e.g. all, 1D, 7D, 30D.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("metrics_by_trace.csv"),
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=Path("metrics_summary.csv"),
    )

    args = parser.parse_args()

    # Set up the brand config: domains (urls), names (in textual repr)
    brand_domains = tuple(args.brand_domain or [f"{args.brand}.com"])
    brand_names = tuple(args.brand_name or [args.brand])
    brand = BrandConfig(
        brand = args.brand,
        domain_identifiers=brand_domains,
        text_identifiers=brand_names,
    )

    # Load claims setup and records files
    claims_by_topic = load_claims(args.claims_json)
    records = load_records(args.json_path)

    # Create a list of rows for each trace record with all the Section 2.3 metrics computed
    rows = [
        trace_metrics(r, brand, claims_by_topic)
        for r in records
    ]

    # Put this list in a dataframe and aggregate from start time "t" to the freq
    df = pd.DataFrame(rows)
    summary = aggregate_metrics(df, freq=args.freq)

    df.to_csv(args.out, index=False)
    summary.to_csv(args.summary_out, index=False)

    print(f"Wrote trace metrics: {args.out} ({len(df)} rows)")
    print(f"Wrote summary metrics: {args.summary_out} ({len(summary)} rows)")

    if not claims_by_topic:
        print("Note: no claims JSON provided; m_align / AlignmentMean are NaN.")

if __name__ == "__main__":
    main()

