from __future__ import annotations

"""PII regex patterns — compiled once at module import time, never per-call."""

import re

_PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b',
        re.IGNORECASE,
    ),
    "phone": re.compile(
        r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
        re.IGNORECASE,
    ),
    "ssn": re.compile(
        r'\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0{4})\d{4}\b',
        re.IGNORECASE,
    ),
    "credit_card": re.compile(
        r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b',
        re.IGNORECASE,
    ),
    "api_key": re.compile(
        r'\b(?:sk-[A-Za-z0-9]{20,}|[A-Za-z0-9]{32,}(?:key|token|secret)[A-Za-z0-9]{0,})\b',
        re.IGNORECASE,
    ),
    "ip_address": re.compile(
        r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
        re.IGNORECASE,
    ),
}
