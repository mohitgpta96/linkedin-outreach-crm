#!/usr/bin/env python3
"""
icp_prefilter.py — ICP filter for newly discovered leads
Removes leads that don't meet ICP criteria.
Gate: if <5 candidates remain → abort

Criteria:
- employee_count > 100 → discard
- Not tech/SaaS industry → discard
- Already in 'Enriched' or 'Ready' stage → skip
- No LinkedIn URL → discard (can't enrich)

Usage:
    python3 scripts/icp_prefilter.py          # dry run
    python3 scripts/icp_prefilter.py --apply  # actually remove/downgrade
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from data_store import get_leads, upsert_lead

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MIN_CANDIDATES = 5

NON_TECH_INDUSTRIES = {
    "restaurants", "food & beverage", "retail", "real estate", "construction",
    "agriculture", "mining", "oil & gas", "transportation", "utilities",
    "government", "public sector", "staffing", "recruitment", "legal services",
    "accounting", "consulting", "media & entertainment", "publishing",
    "travel & tourism", "hospitality",
}

TECH_SIGNALS = [
    "saas", "software", "tech", "api", "platform", "app", "ai", "ml",
    "fintech", "edtech", "healthtech", "cloud", "data", "analytics",
    "b2b", "developer", "devtools", "automation", "product", "engineering",
    "cybersecurity", "marketplace", "mobile", "web", "startup",
]


def _is_non_tech(lead: dict) -> bool:
    industry = str(lead.get("industry") or "").lower()
    if not industry:
        return False  # unknown = give benefit of doubt
    for nont in NON_TECH_INDUSTRIES:
        if nont in industry:
            return True
    # Check for any tech signal
    for ts in TECH_SIGNALS:
        if ts in industry:
            return False
    return False


def _over_100_employees(lead: dict) -> bool:
    emp = lead.get("employee_count")
    if emp is None:
        # Try parsing company_size string
        size_str = str(lead.get("company_size") or "").strip()
        if not size_str or size_str in ("nan", ""):
            return False  # unknown = keep
        try:
            # "51-200 employees" → take max
            nums = [int(x) for x in size_str.replace("+", "").replace("employees", "").split("-") if x.strip().isdigit()]
            emp = max(nums) if nums else None
        except Exception:
            return False
    try:
        return int(emp) > 100
    except Exception:
        return False


def _has_linkedin_url(lead: dict) -> bool:
    url = lead.get("profile_url") or lead.get("linkedin_url") or ""
    return "linkedin.com/in/" in str(url)


def filter_leads(leads: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns (keep, discard)."""
    keep    = []
    discard = []

    for lead in leads:
        stage = lead.get("pipeline_stage", "")
        if stage in ("Enriched", "Ready", "Request Sent", "Connected", "Replied", "Interested", "Closed"):
            keep.append(lead)
            continue

        reasons = []
        if _over_100_employees(lead):
            reasons.append(">100 employees")
        if _is_non_tech(lead):
            reasons.append("non-tech industry")
        if not _has_linkedin_url(lead):
            reasons.append("no LinkedIn URL")

        if reasons:
            lead["_discard_reason"] = ", ".join(reasons)
            discard.append(lead)
        else:
            keep.append(lead)

    return keep, discard


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually mark discarded leads as Rejected")
    args = parser.parse_args()

    leads      = get_leads(filters={"pipeline_stage": "ICP Candidate"})
    icp_leads  = [l for l in leads if l.get("pipeline_stage") == "ICP Candidate"]

    print(f"\n{'='*55}")
    print("ICP Pre-filter")
    print(f"{'='*55}")
    print(f"Leads in 'ICP Candidate' stage: {len(icp_leads)}")

    if not icp_leads:
        print("  No leads to filter.")
        return

    keep, discard = filter_leads(icp_leads)

    print(f"\nKeep    : {len(keep)}")
    print(f"Discard : {len(discard)}")

    if discard:
        print("\nDiscard reasons:")
        for lead in discard[:10]:
            print(f"  - {lead.get('founder_name') or lead.get('name','-')} @ "
                  f"{lead.get('company_name') or lead.get('company','-')}: "
                  f"{lead.get('_discard_reason','')}")

    # Gate check
    if len(keep) < MIN_CANDIDATES:
        print(f"\n⛔ GATE FAIL: Only {len(keep)} ICP candidates remain (minimum {MIN_CANDIDATES}).")
        print("   Aborting — broaden discovery or check data quality.")
        sys.exit(2)

    if not args.apply:
        print(f"\n[DRY RUN] Would keep {len(keep)}, discard {len(discard)}.")
        print("Run with --apply to update DB.")
        return

    # Mark discarded as Rejected
    rejected = 0
    for lead in discard:
        try:
            lead["pipeline_stage"]     = "Rejected"
            lead["enrichment_status"]  = "rejected"
            lead["notes"]              = f"ICP filter: {lead.get('_discard_reason','')}"
            upsert_lead(lead)
            rejected += 1
        except Exception as e:
            logger.warning(f"  Failed to reject lead: {e}")

    print(f"\n✅ Marked {rejected} leads as Rejected")
    print(f"✅ {len(keep)} leads remain in ICP Candidate stage → ready for enrichment")


if __name__ == "__main__":
    main()
