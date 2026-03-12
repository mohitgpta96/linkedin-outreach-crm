"""
Enrich YC leads with founder LinkedIn URLs by scraping YC company pages.
Uses:
  1. YC OSS API (free, no auth) — get company slug from company name
  2. Scrape https://www.ycombinator.com/companies/{slug} — extract founder LinkedIn URLs

Updates leads.csv in place. Saves backup first.
"""

import re
import time
import random
import requests
import pandas as pd
from pathlib import Path
from difflib import SequenceMatcher

LEADS_CSV   = Path(__file__).parent / "output" / "leads.csv"
YC_OSS_URL  = "https://yc-oss.github.io/api/companies/all.json"
HEADERS     = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def slug_to_name(slug: str) -> str:
    """Convert YC slug to display name (for matching)."""
    slug = re.sub(r"-[0-9a-f]{7,}$", "", slug)
    parts = slug.replace("-", " ").replace("_", " ").split()
    return " ".join(p.capitalize() for p in parts[:3])


def load_yc_companies() -> list:
    """Load all YC companies from OSS API."""
    print("Fetching YC OSS company list...")
    try:
        r = requests.get(YC_OSS_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        companies = r.json()
        print(f"  Loaded {len(companies)} YC companies")
        return companies
    except Exception as e:
        print(f"  Failed: {e}")
        return []


def find_slug(company_name: str, yc_companies: list, batch: str = "") -> str:
    """Find YC slug for a company name."""
    name_lower = company_name.lower().strip()

    # Exact match first
    for co in yc_companies:
        if co.get("name", "").lower().strip() == name_lower:
            return co.get("slug", "")

    # Fuzzy match — require similarity > 0.85
    best_slug  = ""
    best_score = 0.0
    for co in yc_companies:
        score = name_similarity(company_name, co.get("name", ""))
        if score > best_score:
            best_score = score
            best_slug  = co.get("slug", "")

    if best_score >= 0.85:
        return best_slug

    # Try slug-based match (slug → name conversion)
    for co in yc_companies:
        slug = co.get("slug", "")
        if name_lower in slug.lower() or slug.lower() in name_lower.replace(" ", "-"):
            return slug

    return ""


def scrape_yc_page(slug: str) -> dict:
    """Scrape YC company page for founder LinkedIn URLs and names."""
    result = {"linkedin_url": "", "founder_name": ""}
    url = f"https://www.ycombinator.com/companies/{slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return result

        # Decode HTML entities for easier parsing
        html = r.text.replace("&quot;", '"').replace("&amp;", "&").replace("&#x27;", "'")

        # Find founders array in the page JSON
        # Pattern: "full_name":"Aly Murray" ... "linkedin_url":"https://www.linkedin.com/in/..."
        founders_match = re.search(r'"founders"\s*:\s*\[(.*?)\]', html, re.DOTALL)
        if founders_match:
            founders_block = founders_match.group(1)
            # Extract first founder's name and LinkedIn
            name_m = re.search(r'"full_name"\s*:\s*"([^"]{3,80})"', founders_block)
            li_m   = re.search(r'"linkedin_url"\s*:\s*"https://www\.linkedin\.com/in/([^/"]+)', founders_block)
            if li_m:
                result["linkedin_url"] = f"https://www.linkedin.com/in/{li_m.group(1)}"
            if name_m:
                result["founder_name"] = name_m.group(1).strip()
            return result

        # Fallback: extract LinkedIn slugs directly
        li_slugs = re.findall(r'linkedin\.com/in/([a-zA-Z0-9\-]+)', html)
        if li_slugs:
            result["linkedin_url"] = f"https://www.linkedin.com/in/{li_slugs[0]}"

    except Exception:
        pass
    return result


def run():
    df = pd.read_csv(LEADS_CSV)

    # Backup
    backup = LEADS_CSV.parent / "leads_backup_pre_yc_linkedin.csv"
    if not backup.exists():
        df.to_csv(backup, index=False)
        print(f"Backup saved: {backup.name}")

    # Leads needing LinkedIn URL
    needs_url = df[
        df["profile_url"].isna() |
        ~df["profile_url"].str.startswith("https://www.linkedin.com/in/", na=False)
    ].copy()
    print(f"\nLeads needing LinkedIn URL: {len(needs_url)}")

    if needs_url.empty:
        print("All leads already have LinkedIn URLs.")
        return

    # Load YC companies
    yc_companies = load_yc_companies()
    if not yc_companies:
        return

    found_count = 0
    for i, (idx, lead) in enumerate(needs_url.iterrows(), 1):
        company = str(lead.get("company", "")).strip()
        source  = str(lead.get("source", ""))
        if not company:
            continue

        print(f"\n[{i}/{len(needs_url)}] {company} ({source})")

        slug = find_slug(company, yc_companies)
        if not slug:
            print(f"  No YC slug found for '{company}'")
            continue

        print(f"  Slug: {slug}")
        info = scrape_yc_page(slug)

        if info["linkedin_url"]:
            print(f"  LinkedIn: {info['linkedin_url']}")
            df.loc[idx, "profile_url"] = info["linkedin_url"]
            if info["founder_name"] and str(df.loc[idx, "name"]) in ("nan", "NaN", ""):
                # Clean name
                name = info["founder_name"]
                df.loc[idx, "name"]       = name
                df.loc[idx, "first_name"] = name.split()[0] if name else "Founder"
            found_count += 1
        else:
            print(f"  No LinkedIn found on YC page")

        # Save every 10 rows
        if i % 10 == 0:
            df.to_csv(LEADS_CSV, index=False)
            print(f"  Saved progress ({found_count} found so far)")

        time.sleep(random.uniform(0.8, 1.5))

    df.to_csv(LEADS_CSV, index=False)
    print(f"\nDone! Found LinkedIn URLs for {found_count}/{len(needs_url)} leads.")
    print(f"Saved: {LEADS_CSV}")


if __name__ == "__main__":
    run()
