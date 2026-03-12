"""
Lead Enrichment — Stage 3 of the outreach pipeline.

Reads:  leads/qualified/clean_leads.csv  (ICP-filtered, deduped)
Cache:  cache/enriched_leads.json        (keyed by linkedin_url)
Output: leads/enriched/enriched_leads.json

Enrichment sources (all free, no paid API required):
  1. Company website scraping  — description, domain, size hints
  2. Careers page scraping     — hiring_engineers signal
  3. Crunchbase via RapidAPI   — funding_stage (50 req/month, optional)

Only enriches leads with icp_score >= 75.
Caches every result immediately — safe to stop and resume.

Usage:
    python3 scripts/enrich_leads.py
    python3 scripts/enrich_leads.py --min-score 80
    python3 scripts/enrich_leads.py --limit 20
    python3 scripts/enrich_leads.py --dry-run
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
INPUT_PATH   = ROOT / "leads" / "qualified" / "clean_leads.csv"
CACHE_PATH   = ROOT / "cache" / "enriched_leads.json"
OUTPUT_PATH  = ROOT / "leads" / "enriched" / "enriched_leads.json"
LOG_PATH     = ROOT / "logs" / "enrichment_errors.log"

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_MIN_SCORE = 75
REQUEST_TIMEOUT   = 10  # seconds per HTTP request
DELAY_BETWEEN     = 1.2 # seconds between leads (polite crawling)

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY", "")
CRUNCHBASE_HOST = "crunchbase-company-info.p.rapidapi.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Keywords that signal the company is actively hiring engineers
ENGINEER_HIRING_KEYWORDS = [
    "software engineer", "frontend engineer", "backend engineer",
    "full stack", "fullstack", "mobile engineer", "ios engineer",
    "android engineer", "devops", "site reliability", "sre",
    "data engineer", "ml engineer", "machine learning engineer",
    "platform engineer", "infrastructure engineer",
]

# Funding stage keywords → normalised stage label
FUNDING_KEYWORDS = {
    "series d": "series_d", "series c": "series_c",
    "series b": "series_b", "series a": "series_a",
    "seed": "seed", "pre-seed": "pre_seed",
    "bootstrapped": "bootstrapped", "self-funded": "bootstrapped",
    "raised": "raised",
}


# ── Cache helpers ─────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, default=str)


def cache_key(linkedin_url: str) -> str:
    """Normalise URL to use as cache key."""
    return linkedin_url.rstrip("/").lower()


# ── Utility ───────────────────────────────────────────────────────────────────

def extract_domain(url: str) -> str:
    """https://metorial.com/about → metorial.com"""
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc or parsed.path
        return domain.replace("www.", "").strip("/")
    except Exception:
        return ""


def safe_get(url: str, timeout: int = REQUEST_TIMEOUT):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return r
    except Exception as e:
        logger.debug(f"    HTTP GET failed for {url}: {e}")
        return None


def extract_text_snippet(html: str, max_chars: int = 400) -> str:
    """Pull plain text from HTML — strips tags, collapses whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


# ── Enrichment Sources ────────────────────────────────────────────────────────

def enrich_from_website(company_url: str) -> dict:
    """
    Scrape the company homepage for:
      - company_description (meta description or first paragraph)
      - company_size hint (from footer / about text)
      - company_domain
    """
    result = {}
    if not company_url:
        return result

    domain = extract_domain(company_url)
    result["company_domain"] = domain
    result["company_website"] = company_url

    resp = safe_get(company_url)
    if not resp:
        return result

    html = resp.text

    # Meta description — best source for a clean company blurb
    meta_match = re.search(
        r'<meta\s+(?:name|property)=["\'](?:description|og:description)["\']\s+content=["\'](.*?)["\']',
        html, re.IGNORECASE
    )
    if meta_match:
        result["company_description"] = meta_match.group(1).strip()[:400]
    else:
        # Fallback: first <p> or <h1> text
        p_match = re.search(r"<(?:p|h1)[^>]*>(.*?)</(?:p|h1)>", html, re.IGNORECASE | re.DOTALL)
        if p_match:
            result["company_description"] = extract_text_snippet(p_match.group(1), 300)

    # Size hint — look for "X employees", "team of X", etc.
    size_match = re.search(
        r"(\d[\d,]*)\s*(?:\+\s*)?(?:employees?|people|team members?|strong team)",
        html, re.IGNORECASE
    )
    if size_match:
        raw_size = size_match.group(1).replace(",", "")
        try:
            result["company_size_scraped"] = int(raw_size)
        except ValueError:
            pass

    # LinkedIn company page URL
    li_match = re.search(
        r'href=["\']?(https?://(?:www\.)?linkedin\.com/company/[a-zA-Z0-9\-_/]+)',
        html, re.IGNORECASE
    )
    if li_match:
        result["company_linkedin_url"] = li_match.group(1).rstrip("/")

    return result


def enrich_from_careers(company_url: str) -> dict:
    """
    Scrape careers page for hiring_engineers signal.
    Tries common career page paths.
    """
    if not company_url:
        return {"hiring_engineers": False, "careers_url": ""}

    domain = extract_domain(company_url)
    base   = f"https://{domain}"
    career_paths = ["/careers", "/jobs", "/work-with-us", "/join", "/hiring", "/open-roles"]

    for path in career_paths:
        resp = safe_get(base + path, timeout=8)
        if not resp:
            continue

        html_lower = resp.text.lower()
        hiring = any(kw in html_lower for kw in ENGINEER_HIRING_KEYWORDS)
        return {
            "hiring_engineers": hiring,
            "careers_url": base + path,
        }

    return {"hiring_engineers": False, "careers_url": ""}


def enrich_from_crunchbase(company_name: str) -> dict:
    """
    Use Crunchbase RapidAPI to get funding stage.
    Only called if RAPIDAPI_KEY is set. Uses 1 credit.
    """
    if not RAPIDAPI_KEY:
        return {}

    try:
        # Step 1: search by company name
        search_resp = requests.get(
            "https://crunchbase-company-info.p.rapidapi.com/company/search",
            headers={
                "x-rapidapi-key":  RAPIDAPI_KEY,
                "x-rapidapi-host": CRUNCHBASE_HOST,
            },
            params={"query": company_name},
            timeout=10,
        )
        if not search_resp.ok:
            return {}

        data = search_resp.json()
        results = data.get("data") or data.get("results") or []
        if not results:
            return {}

        top = results[0]
        funding_raw = str(top.get("funding_stage") or top.get("last_funding_type") or "").lower()

        # Normalise funding stage
        stage = ""
        for kw, label in FUNDING_KEYWORDS.items():
            if kw in funding_raw:
                stage = label
                break

        return {
            "funding_stage":  stage or funding_raw,
            "funding_amount": str(top.get("total_funding_usd") or ""),
            "company_industry": str(top.get("category_list") or top.get("industry") or ""),
        }

    except Exception as e:
        logger.debug(f"    Crunchbase failed for '{company_name}': {e}")
        return {}


# ── Core enrichment ───────────────────────────────────────────────────────────

def enrich_lead(lead: dict) -> dict:
    """
    Run all enrichment sources for one lead.
    Returns a merged enrichment dict.
    """
    enriched = {
        "linkedin_url":        lead.get("profile_url") or lead.get("linkedin_url", ""),
        "name":                lead.get("name", ""),
        "company":             lead.get("company", ""),
        "title":               lead.get("title", ""),
        "icp_score":           lead.get("icp_score", ""),
        "persona":             lead.get("persona", ""),
        "buying_signal":       lead.get("buying_signal", ""),

        # Fields to populate
        "company_domain":      "",
        "company_website":     "",
        "company_description": "",
        "company_size":        lead.get("company_size", ""),
        "company_linkedin_url":"",
        "company_industry":    lead.get("industry", ""),
        "funding_stage":       lead.get("funding_stage", ""),
        "hiring_engineers":    False,
        "careers_url":         "",

        "enriched_at":         datetime.now(timezone.utc).isoformat(),
        "enrichment_sources":  [],
    }

    company_url = str(lead.get("company_website") or lead.get("company_url") or "").strip()

    # Source 1: Company website
    if company_url:
        website_data = enrich_from_website(company_url)
        if website_data:
            enriched.update(website_data)
            enriched["enrichment_sources"].append("website")
            logger.debug(f"    website ✓ domain={website_data.get('company_domain','')}")
        time.sleep(0.5)
    else:
        # Try to construct URL from company name as fallback
        slug = re.sub(r"[^a-z0-9]", "", lead.get("company", "").lower())
        if slug:
            guessed = f"https://{slug}.com"
            website_data = enrich_from_website(guessed)
            if website_data.get("company_description"):
                enriched.update(website_data)
                enriched["enrichment_sources"].append("website_guessed")

    # Source 2: Careers page
    url_for_careers = enriched.get("company_website") or company_url
    if url_for_careers:
        careers_data = enrich_from_careers(url_for_careers)
        enriched.update(careers_data)
        enriched["enrichment_sources"].append("careers")
        logger.debug(f"    careers ✓ hiring_engineers={careers_data.get('hiring_engineers')}")
        time.sleep(0.5)

    # Source 3: Crunchbase (only if no funding_stage yet and API key is set)
    if RAPIDAPI_KEY and not enriched.get("funding_stage"):
        cb_data = enrich_from_crunchbase(lead.get("company", ""))
        if cb_data:
            enriched.update(cb_data)
            enriched["enrichment_sources"].append("crunchbase")
            logger.debug(f"    crunchbase ✓ stage={cb_data.get('funding_stage','')}")

    # Normalise size: use scraped value if original is missing
    if not enriched["company_size"] and enriched.get("company_size_scraped"):
        enriched["company_size"] = str(enriched["company_size_scraped"])

    enriched.pop("company_size_scraped", None)
    return enriched


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enrich high-quality leads")
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE,
                        help=f"Minimum ICP score to enrich (default: {DEFAULT_MIN_SCORE})")
    parser.add_argument("--limit",     type=int, default=0,
                        help="Max leads to enrich this run (0 = all eligible)")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Show what would be enriched without calling APIs")
    args = parser.parse_args()

    # ── Load input ────────────────────────────────────────────────────────────
    if not INPUT_PATH.exists():
        logger.error(f"Input not found: {INPUT_PATH}")
        logger.info("Run scripts/dedupe.py first to generate clean_leads.csv")
        sys.exit(1)

    df = pd.read_csv(INPUT_PATH, low_memory=False, dtype=str).fillna("")
    logger.info(f"Loaded {len(df)} leads from {INPUT_PATH}")

    # ── Filter by ICP score ───────────────────────────────────────────────────
    score_col = df["icp_score"] if "icp_score" in df.columns else pd.Series(0, index=df.index)
    df["_score_num"] = pd.to_numeric(score_col, errors="coerce").fillna(0)
    eligible = df[df["_score_num"] >= args.min_score].copy()
    logger.info(f"Eligible (score >= {args.min_score}): {len(eligible)} leads")

    if eligible.empty:
        logger.info("No eligible leads. Lower --min-score or run icp_filter.py first.")
        return

    # ── Load cache ────────────────────────────────────────────────────────────
    cache = load_cache()
    logger.info(f"Cache: {len(cache)} leads already enriched")

    # Skip leads already in cache
    def get_url(row):
        return str(row.get("profile_url") or row.get("linkedin_url") or "").strip()

    already_cached = sum(
        1 for _, row in eligible.iterrows()
        if cache_key(get_url(row.to_dict())) in cache
    )
    if already_cached:
        logger.info(f"Skipping {already_cached} leads already in cache")

    to_enrich = [
        row.to_dict() for _, row in eligible.iterrows()
        if cache_key(get_url(row.to_dict())) not in cache
    ]

    if args.limit:
        to_enrich = to_enrich[:args.limit]

    logger.info(f"To enrich this run: {len(to_enrich)}")

    if args.dry_run:
        print(f"\nDRY RUN — would enrich {len(to_enrich)} leads:")
        for lead in to_enrich[:10]:
            print(f"  {lead.get('name','?'):25s} | score:{lead.get('icp_score','?'):>5} | {lead.get('company','?')}")
        if len(to_enrich) > 10:
            print(f"  ... and {len(to_enrich) - 10} more")
        return

    if not to_enrich:
        logger.info("Nothing new to enrich — all eligible leads are cached.")
        _write_output(cache)
        return

    # ── Enrich loop ───────────────────────────────────────────────────────────
    success = 0
    failed  = 0

    for i, lead in enumerate(to_enrich, 1):
        name    = lead.get("name") or lead.get("company") or f"lead_{i}"
        url_key = cache_key(get_url(lead))

        logger.info(f"[{i}/{len(to_enrich)}] {name} — {lead.get('company','')}")

        try:
            enriched = enrich_lead(lead)
            cache[url_key] = enriched
            save_cache(cache)  # save immediately after each lead
            success += 1

            sources = ", ".join(enriched.get("enrichment_sources", []))
            logger.info(
                f"  ✅ sources:[{sources}]  "
                f"domain:{enriched.get('company_domain','—')}  "
                f"hiring_engineers:{enriched.get('hiring_engineers','—')}  "
                f"funding:{enriched.get('funding_stage','—') or '—'}"
            )

        except Exception as e:
            failed += 1
            logger.warning(f"  ❌ Failed: {e}")
            # Log to error file
            with open(LOG_PATH, "a") as f:
                f.write(f"{datetime.now().isoformat()} | {name} | {url_key} | {e}\n")

        # Progress checkpoint every 10 leads
        if i % 10 == 0:
            _write_output(cache)
            logger.info(f"  💾 Progress saved ({i}/{len(to_enrich)})")

        time.sleep(DELAY_BETWEEN)

    # ── Final save ────────────────────────────────────────────────────────────
    _write_output(cache)

    print("\n" + "=" * 50)
    print("ENRICHMENT COMPLETE")
    print("=" * 50)
    print(f"  Processed : {len(to_enrich)}")
    print(f"  Succeeded : {success}")
    print(f"  Failed    : {failed}")
    print(f"  Total cached : {len(cache)}")
    print(f"  Output → {OUTPUT_PATH}")
    print()


def _write_output(cache: dict) -> None:
    """Write the full enriched dataset (all cached leads) to the output file."""
    leads_list = list(cache.values())
    with open(OUTPUT_PATH, "w") as f:
        json.dump(leads_list, f, indent=2, default=str)


if __name__ == "__main__":
    main()
