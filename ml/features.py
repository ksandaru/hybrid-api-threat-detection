"""Canonical feature contract for the hybrid detection pipeline.

This module is the single source of truth for the feature vector used by
both the offline training pipeline (ml/preprocess.py, ml/train.py) and the
live Express detection middleware (api/middleware/featureExtractor.js).
The two MUST stay in sync: same feature names, same order, same
definitions. If you change anything here, mirror the change in
featureExtractor.js in the same commit.

Feature families:
  - Payload-level (12): computed from a single request's text (URL query
    string, path, or body) — the signal for SQL injection detection.
  - Flow-level (5): computed from a sliding window of recent requests per
    source IP — the signal for brute-force / credential-stuffing detection.
    At inference time these are computed live by the Express middleware
    from real request history. In the training corpus, only CICIDS2017
    carries genuine flow statistics; Kaggle/CSIC/ATRDF are single-request
    payload sources and get zero-filled flow features (see preprocess.py
    and docs/phase-1-datasets/MEMORY.md for why, and for the CICIDS2017
    proxy limitations).
"""

import math
import re
from collections import Counter

PAYLOAD_FEATURES = [
    "payload_length",
    "sql_keyword_count",
    "single_quote_count",
    "double_dash_count",
    "semicolon_count",
    "paren_count",
    "equals_count",
    "special_char_ratio",
    "shannon_entropy",
    "has_union_select",
    "has_or_equals",
    "has_comment",
]

FLOW_FEATURES = [
    "requests_per_min_ip",
    "login_failure_ratio",
    "inter_arrival_time_variance",
    "distinct_usernames_tried",
    "unique_ip_count_window",
]

# Canonical order — api/middleware/featureExtractor.js must produce a
# feature vector in exactly this order.
CANONICAL_FEATURE_ORDER = PAYLOAD_FEATURES + FLOW_FEATURES

SQL_KEYWORDS = [
    "select", "union", "insert", "update", "delete", "drop", "create",
    "alter", "exec", "execute", "declare", "cast", "convert", "waitfor",
    "sleep", "benchmark", "information_schema", "sysobjects", "syscolumns",
    "xp_", "sp_", "or", "and", "having", "group by", "order by",
]

SPECIAL_CHARS = set("'\";()=--#*%<>{}[]|&+")


def shannon_entropy(text: str) -> float:
    """Shannon entropy (bits/char) of a string. 0.0 for empty input."""
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )


def extract_payload_features(text) -> dict:
    """Compute the 12 payload-level features for a single request string.

    `text` should be the decoded query string / path / body being
    inspected (e.g. the value of `?q=` on /api/search, or a raw HTTP
    request line + body for CSIC-style sources). None/NaN is treated as
    an empty string.
    """
    if text is None or (isinstance(text, float) and math.isnan(text)):
        text = ""
    text = str(text)
    lower = text.lower()
    length = len(text)

    special_char_count = sum(1 for ch in text if ch in SPECIAL_CHARS)

    return {
        "payload_length": length,
        "sql_keyword_count": sum(
            len(re.findall(r"\b" + re.escape(kw) + r"\b", lower))
            for kw in SQL_KEYWORDS
        ),
        "single_quote_count": text.count("'"),
        "double_dash_count": text.count("--"),
        "semicolon_count": text.count(";"),
        "paren_count": text.count("(") + text.count(")"),
        "equals_count": text.count("="),
        "special_char_ratio": (special_char_count / length) if length else 0.0,
        "shannon_entropy": shannon_entropy(text),
        "has_union_select": int(bool(re.search(r"union\s+select", lower))),
        "has_or_equals": int(bool(re.search(r"\bor\b.{0,15}=", lower))),
        "has_comment": int(("--" in text) or ("#" in text) or ("/*" in text)),
    }


def default_flow_features() -> dict:
    """Zero-filled flow features for payload-only training sources.

    Real values are only meaningful when computed over a live sliding
    window of requests from the same source IP (see
    api/middleware/featureExtractor.js, built in Phase 3).
    """
    return {name: 0.0 for name in FLOW_FEATURES}


def default_payload_features() -> dict:
    """Zero-filled payload features for flow-only training sources
    (CICIDS2017 network flows carry no request payload text)."""
    return {name: 0.0 for name in PAYLOAD_FEATURES}


def empty_feature_row() -> dict:
    """A full canonical-order feature dict, all zeros — useful as a base
    to update() from partial extractors."""
    return {name: 0.0 for name in CANONICAL_FEATURE_ORDER}
