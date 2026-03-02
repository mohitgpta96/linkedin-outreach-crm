"""
Source 3: Recently Funded Startups via Crunchbase (RapidAPI)
Finds Series A/B companies in the last 60–90 days.
Fresh funding = hiring urgency. These are warm signals even without a job post.
"""

import logging
import time
from datetime import datetime, timedelta

import requests

from config import (
    RAPIDAPI_KEY,
    LOCATIONS,
    TARGET_INDUSTRIES,
    EXCLUDE_INDUSTRIES,
    MAX_DISCOVERY_RESULTS,
)

logger = logging.getLogger(__name__)

CRUNCHBASE_API_HOST = "crunchbase-crunchbase-v1.p.rapidapi.com"
CRUNCHBASE_BASE_URL = f"https://{CRUNCHBASE_API_HOST}"


def _days_ago(n: int) -> str:
    return (datetime.utcnow() - timedelta(days=n)).strftime("%Y-%m-%d")


def _location_matches(location: str) -> bool:
    if not location:
        return True
    loc_lower = location.lower()
    return any(l.lower() in loc_lower for l in LOCATIONS)


def _industry_ok(categories: list) -> bool:
    cats_lower = " ".join(c.lower() for c in (categories or []))
    if any(e.lower() in cats_lower for e in EXCLUDE_INDUSTRIES):
        return False
    return True


def _search_funded_companies(days_back: int = 90) -> list[dict]:
    """Query RapidAPI Crunchbase for recently funded companies."""
    if not RAPIDAPI_KEY:
        logger.warning("RAPIDAPI_KEY not set — skipping Crunchbase scrape.")
        return []

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": CRUNCHBASE_API_HOST,
        "Content-Type": "application/json",
    }

    # Crunchbase v4 search endpoint
    url = f"{CRUNCHBASE_BASE_URL}/searches/funding_rounds"
    payload = {
        "field_ids": [
            "funded_organization_identifier",
            "funded_organization_location",
            "funded_organization_categories",
            "funded_organization_num_employees_enum",
            "investment_type",
            "announced_on",
            "money_raised",
        ],
        "query": [
            {
                "type": "predicate",
                "field_id": "investment_type",
                "operator_id": "includes",
                "values": ["series_a", "series_b"],
            },
            {
                "type": "predicate",
                "field_id": "announced_on",
                "operator_id": "gte",
                "values": [_days_ago(days_back)],
            },
        ],
        "sort": [{"field_id": "announced_on", "sort_value": "desc"}],
        "limit": 100,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("entities", [])
    except requests.RequestException as exc:
        logger.error(f"[Crunchbase] API call failed: {exc}")
        return []


def _get_company_details(org_id: str, headers: dict) -> dict:
    """Fetch org details to get founder/CEO LinkedIn URL."""
    url = f"{CRUNCHBASE_BASE_URL}/entities/organizations/{org_id}"
    params = {
        "field_ids": (
            "short_description,homepage_url,employee_count,founded_on,"
            "founder_identifiers,contact_email,linkedin,primary_job_title"
        )
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json().get("properties", {})
    except requests.RequestException as exc:
        logger.error(f"[Crunchbase] Org details failed for {org_id}: {exc}")
        return {}


def scrape_crunchbase() -> list[dict]:
    """
    Pull recently funded Series A/B startups, filter by location + industry,
    and return lead records with founder info and funding details.
    """
    if not RAPIDAPI_KEY:
        logger.warning("RAPIDAPI_KEY not set — skipping Crunchbase.")
        return []

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": CRUNCHBASE_API_HOST,
    }

    raw_entities = _search_funded_companies(days_back=90)
    logger.info(f"[Crunchbase] Raw results: {len(raw_entities)}")

    leads: list[dict] = []
    seen_orgs: set[str] = set()

    for entity in raw_entities:
        if len(leads) >= MAX_DISCOVERY_RESULTS:
            break

        props = entity.get("properties", {})
        org = props.get("funded_organization_identifier", {})
        org_id = org.get("permalink") or org.get("uuid", "")
        org_name = org.get("value", "")

        if not org_id or org_id in seen_orgs:
            continue

        location_raw = ""
        for loc in (props.get("funded_organization_location") or []):
            location_raw = loc.get("value", "")
            break

        if not _location_matches(location_raw):
            continue

        categories = [
            c.get("value", "")
            for c in (props.get("funded_organization_categories") or [])
        ]
        if not _industry_ok(categories):
            continue

        funding_type = props.get("investment_type", "")
        funding_date = props.get("announced_on", {}).get("value", "")
        funding_amount_raw = props.get("money_raised", {})
        funding_amount = ""
        if funding_amount_raw:
            val = funding_amount_raw.get("value_usd") or funding_amount_raw.get("value", 0)
            funding_amount = f"${val:,.0f}" if val else ""

        # Fetch more details
        details = _get_company_details(org_id, headers)
        time.sleep(0.5)  # rate limit courtesy

        website = details.get("homepage_url", "")
        company_size = details.get("employee_count", "")
        description = details.get("short_description", "")

        seen_orgs.add(org_id)
        leads.append({
            "name": "",           # will be filled by enrichment
            "first_name": "",
            "title": "Founder/CEO",
            "company": org_name,
            "location": location_raw,
            "profile_url": "",    # will be resolved in enrichment
            "signal_type": "funding",
            "signal_text": (
                f"Raised {funding_amount} ({funding_type.replace('_', ' ').title()}) "
                f"on {funding_date}. {description}"
            )[:500],
            "signal_date": funding_date,
            "source": "crunchbase",
            "company_website": website,
            "funding_stage": funding_type.replace("_", " ").title(),
            "funding_date": funding_date,
            "funding_amount": funding_amount,
            "industry": ", ".join(categories[:3]),
            "company_size_raw": str(company_size),
        })

    logger.info(f"[Crunchbase] Total leads collected: {len(leads)}")
    return leads
