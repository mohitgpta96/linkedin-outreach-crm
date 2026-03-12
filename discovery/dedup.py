"""
dedup.py — Deduplication and signal scoring for discovered leads.
- Normalizes LinkedIn URLs
- Removes leads already in data_store
- Assigns Signal type A (direct PM signal) or B (inferred)
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

PM_SIGNAL_KEYWORDS = [
    "product manager", "project manager", "program manager",
    "hiring pm", "pm role", "head of product", "vp product",
    "actively hiring pm",
]


def _normalize_url(url: str) -> str:
    """Lowercase, strip trailing slash, remove query string."""
    if not url:
        return ""
    url = url.strip().lower()
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    # Rebuild without query/fragment
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    return clean


def _has_pm_signal(lead: dict) -> bool:
    text_fields = [
        lead.get("signal_text", ""),
        lead.get("growth_signals", ""),
        lead.get("careers_page_roles", ""),
        lead.get("pm_job_title", ""),
        lead.get("pm_hiring_evidence", ""),
    ]
    combined = " ".join(str(f) for f in text_fields if f).lower()
    return any(kw in combined for kw in PM_SIGNAL_KEYWORDS)


def deduplicate_and_score(
    new_leads: list[dict],
    existing_urls: set[str] | None = None,
) -> list[dict]:
    """
    1. Normalize URLs
    2. Remove duplicates within new_leads
    3. Remove leads already in existing_urls
    4. Assign icp_signal_type: A (direct PM posting) or B (inferred startup signal)
    """
    if existing_urls is None:
        existing_urls = set()

    seen_urls: set[str] = set()
    deduped: list[dict] = []

    for lead in new_leads:
        url = _normalize_url(lead.get("profile_url") or lead.get("linkedin_url") or "")

        # Skip if already in DB
        if url and url in existing_urls:
            continue

        # Skip intra-batch duplicate
        if url and url in seen_urls:
            continue

        if url:
            seen_urls.add(url)
            lead["profile_url"] = url

        # Assign signal type
        lead["icp_signal_type"] = "A" if _has_pm_signal(lead) else "B"

        deduped.append(lead)

    logger.info(f"[dedup] {len(new_leads)} raw → {len(deduped)} unique (removed {len(new_leads)-len(deduped)})")
    return deduped
