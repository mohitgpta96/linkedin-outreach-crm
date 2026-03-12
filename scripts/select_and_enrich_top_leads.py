"""
select_and_enrich_top_leads.py

Selects top 50 ICP leads from the CRM dataset and performs deep FREE enrichment.

Steps:
  1. Load all leads from output/leads.csv
  2. Score & rank by final_score formula
  3. Select top 50
  4. Deep-enrich each using free sources (website scraping, careers page, LinkedIn company)
  5. Detect PM gap signal
  6. Save results to leads/high_priority/
  7. Cache all scraping in cache/deep_enrichment_cache.json

Run:
  python3 scripts/select_and_enrich_top_leads.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

# ── Paths ────────────────────────────────────────────────────────────────────
BASE        = Path(__file__).parent.parent
LEADS_CSV   = BASE / "output" / "leads.csv"
OUT_DIR     = BASE / "leads" / "high_priority"
CACHE_FILE  = BASE / "cache" / "deep_enrichment_cache.json"
TOP50_RAW   = OUT_DIR / "top_50_leads.json"
TOP50_ENR   = OUT_DIR / "top_50_enriched.json"
PROGRESS    = OUT_DIR / "enrichment_progress.json"

OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

# ── HTTP session ──────────────────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})

TIMEOUT = 8  # seconds per request

# ── Cache helpers ─────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


# ── STEP 1 — Score & rank ─────────────────────────────────────────────────────

def _persona_weight(title: str) -> int:
    t = str(title).lower()
    if any(k in t for k in ["founder", "ceo", "co-founder", "cofounder"]):
        return 20
    if any(k in t for k in ["cto", "head of engineering", "vp engineering", "chief technology", "chief technical"]):
        return 18
    if any(k in t for k in ["engineering manager", "head of product", "vp product"]):
        return 12
    return 5


def _hiring_signal(lead: dict) -> int:
    fields = ["pm_hiring_evidence", "signal_text", "growth_signals", "careers_page_roles"]
    text   = " ".join(str(lead.get(f) or "") for f in fields).lower()
    pm_kw  = ["project manager", "product manager", "scrum master", " pm ", "program manager"]
    return 15 if any(kw in text for kw in pm_kw) else 0


def _funding_signal(lead: dict) -> int:
    f = str(lead.get("funding_stage") or "").lower()
    if any(k in f for k in ["seed", "series a", "pre-seed", "preseed"]):
        return 10
    if f.strip():
        return 3
    return 0


def _company_size_fit(lead: dict) -> int:
    raw = str(lead.get("company_size") or "")
    nums = re.findall(r"\d+", raw)
    if not nums:
        return 1
    mid = int(nums[0])
    if 10 <= mid <= 50:
        return 5
    if 51 <= mid <= 100:
        return 3
    return 1


def compute_final_score(lead: dict) -> float:
    icp     = min(float(lead.get("quality_score") or lead.get("icp_score") or 0), 100)
    persona = _persona_weight(str(lead.get("title") or lead.get("headline") or ""))
    hiring  = _hiring_signal(lead)
    funding = _funding_signal(lead)
    size    = _company_size_fit(lead)
    return icp * 0.5 + persona * 1.0 + hiring + funding + size


# ── STEP 2 — Select top 50 ────────────────────────────────────────────────────

def select_top_50(df: pd.DataFrame) -> list[dict]:
    qualified = df[pd.to_numeric(df.get("quality_score", 0), errors="coerce").fillna(0) >= 70].copy()
    print(f"  Leads with ICP >= 70: {len(qualified)}")

    leads = qualified.fillna("").to_dict("records")
    for lead in leads:
        lead["final_score"] = round(compute_final_score(lead), 1)

    leads.sort(key=lambda x: x["final_score"], reverse=True)
    top50 = leads[:50]
    print(f"  Top 50 selected. Score range: {top50[-1]['final_score']} – {top50[0]['final_score']}")
    return top50


# ── STEP 3 — Free enrichment helpers ─────────────────────────────────────────

def _get(url: str, timeout: int = TIMEOUT) -> str | None:
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None


def _find_domain(lead: dict) -> str:
    website = str(lead.get("company_website") or "").strip()
    if website and website.startswith("http"):
        parsed = urlparse(website)
        return parsed.netloc.replace("www.", "")
    company = str(lead.get("company") or "").strip().lower()
    company = re.sub(r"[^a-z0-9]", "", company)
    return f"{company}.com" if company else ""


def scrape_company_website(domain: str, cache: dict) -> dict:
    if not domain:
        return {}
    cache_key = f"website:{domain}"
    if cache_key in cache:
        return cache[cache_key]

    result: dict = {}
    url = f"https://{domain}"
    html = _get(url)
    if not html:
        url = f"https://www.{domain}"
        html = _get(url)
    if not html:
        cache[cache_key] = result
        return result

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()[:3000]

    # Product category from keywords
    cat_map = {
        "AI / ML": ["artificial intelligence", "machine learning", "llm", "gpt", "ai-powered", "deep learning"],
        "SaaS / B2B": ["saas", "b2b", "software as a service", "enterprise software", "cloud platform"],
        "Dev Tools": ["developer tools", "devtools", "api", "sdk", "developer platform"],
        "Fintech": ["fintech", "payments", "banking", "financial", "invoice", "payroll"],
        "HR Tech": ["hr tech", "hrtech", "hiring", "recruitment", "talent", "workforce"],
        "Construction Tech": ["construction", "project management", "contractor", "building"],
        "E-commerce": ["ecommerce", "e-commerce", "shopify", "marketplace", "retail"],
        "Healthcare": ["healthcare", "health tech", "medical", "clinical", "patient"],
    }
    text_lower = text.lower()
    category = "Other"
    for cat, keywords in cat_map.items():
        if any(kw in text_lower for kw in keywords):
            category = cat
            break

    b2b = any(k in text_lower for k in ["b2b", "enterprise", "business", "teams", "saas", "platform"])
    ai  = any(k in text_lower for k in ["ai", "artificial intelligence", "machine learning", "llm"])

    # Extract description (first 200 chars of meaningful text)
    desc_match = re.search(r"[A-Z][^.!?]{40,200}[.!?]", text)
    description = desc_match.group(0) if desc_match else text[:200]

    result = {
        "company_domain":      domain,
        "company_website":     url,
        "company_description": description.strip(),
        "product_category":    category,
        "is_b2b":              b2b,
        "has_ai":              ai,
    }
    cache[cache_key] = result
    return result


def scrape_careers_page(domain: str, cache: dict) -> dict:
    if not domain:
        return {}
    cache_key = f"careers:{domain}"
    if cache_key in cache:
        return cache[cache_key]

    result = {"hiring_engineers": False, "hiring_pm": False, "engineering_team_growth": False}

    for path in ["/careers", "/jobs", "/work-with-us", "/join-us", "/open-roles"]:
        html = _get(f"https://{domain}{path}")
        if not html:
            html = _get(f"https://www.{domain}{path}")
        if html and len(html) > 500:
            text = re.sub(r"<[^>]+>", " ", html).lower()
            text = re.sub(r"\s+", " ", text)

            eng_kw = ["engineer", "software developer", "backend", "frontend", "full stack",
                      "sre", "devops", "data engineer", "ml engineer"]
            pm_kw  = ["project manager", "product manager", "scrum master", "program manager",
                      "delivery manager", " pm ", "pmo"]

            result["hiring_engineers"] = any(k in text for k in eng_kw)
            result["hiring_pm"]        = any(k in text for k in pm_kw)

            if result["hiring_engineers"]:
                # Count engineer mentions as proxy for team growth
                count = sum(text.count(k) for k in eng_kw)
                result["engineering_team_growth"] = count >= 3
            break

    cache[cache_key] = result
    return result


def scrape_linkedin_company(company_name: str, cache: dict) -> dict:
    """
    LinkedIn blocks scraping. We use the public Google-cached snippet or
    just infer from existing lead data. Returns empty dict if unavailable.
    """
    if not company_name:
        return {}
    cache_key = f"linkedin_co:{company_name.lower()}"
    if cache_key in cache:
        return cache[cache_key]

    # LinkedIn blocks direct scraping — return empty, use existing CSV data
    result: dict = {}
    cache[cache_key] = result
    return result


def detect_pm_gap(lead: dict, careers: dict) -> bool:
    """
    PM gap = company is hiring engineers but NOT hiring a PM, and is small (<50 employees).
    """
    hiring_eng = careers.get("hiring_engineers", False)
    hiring_pm  = careers.get("hiring_pm", False)

    size_raw = str(lead.get("company_size") or "")
    size_nums = re.findall(r"\d+", size_raw)
    size = int(size_nums[0]) if size_nums else 999

    return bool(hiring_eng and not hiring_pm and size < 50)


# ── STEP 4 — Enrich one lead ──────────────────────────────────────────────────

def enrich_lead(lead: dict, cache: dict) -> dict:
    domain  = _find_domain(lead)
    company = str(lead.get("company") or "")

    website_data = scrape_company_website(domain, cache)
    careers_data = scrape_careers_page(domain, cache)
    linkedin_co  = scrape_linkedin_company(company, cache)

    pm_gap = detect_pm_gap(lead, careers_data)

    enriched = {**lead}
    enriched.update({
        "company_domain":           domain,
        "company_website":          website_data.get("company_website", lead.get("company_website", "")),
        "company_description":      website_data.get("company_description", lead.get("what_they_do", "")),
        "product_category":         website_data.get("product_category", ""),
        "is_b2b":                   website_data.get("is_b2b", False),
        "has_ai":                   website_data.get("has_ai", False),
        "hiring_engineers":         careers_data.get("hiring_engineers", False),
        "hiring_pm":                careers_data.get("hiring_pm", False),
        "engineering_team_growth":  careers_data.get("engineering_team_growth", False),
        "pm_gap_signal":            pm_gap,
        "company_size_range":       linkedin_co.get("company_size_range", lead.get("company_size", "")),
        "company_industry":         linkedin_co.get("industry", lead.get("industry", "")),
        "company_location":         linkedin_co.get("headquarters", lead.get("location", "")),
        "deep_enriched_at":         pd.Timestamp.now().isoformat(),
    })
    return enriched


# ── STEP 5 — Progress helpers ─────────────────────────────────────────────────

def _load_progress() -> dict:
    if PROGRESS.exists():
        try:
            return json.loads(PROGRESS.read_text())
        except Exception:
            pass
    return {"done": []}


def _save_progress(done: list[str]) -> None:
    PROGRESS.write_text(json.dumps({"done": done}, indent=2))


# ── STEP 6 — Dashboard section (adds to lead_table.py) ───────────────────────

def _print_dashboard_note() -> None:
    print("\n" + "─" * 60)
    print("DASHBOARD: Top 50 ICP Leads section")
    print("─" * 60)
    print("The enriched results are saved to:")
    print(f"  {TOP50_ENR}")
    print("\nTo view in dashboard: go to 'All Leads' → filter by")
    print("  priority_score desc — top 50 are the high-priority leads.")
    print("─" * 60)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("select_and_enrich_top_leads.py")
    print("=" * 60)

    # Load leads
    print(f"\n[1/5] Loading leads from {LEADS_CSV.relative_to(BASE)} ...")
    df = pd.read_csv(LEADS_CSV, low_memory=False)
    df = df.fillna("")
    print(f"  Total leads in CRM: {len(df)}")

    # Score & select top 50
    print("\n[2/5] Scoring and selecting top 50 leads ...")
    top50 = select_top_50(df)
    TOP50_RAW.write_text(json.dumps(top50, indent=2, ensure_ascii=False))
    print(f"  Saved raw top 50 → {TOP50_RAW.relative_to(BASE)}")

    # Load cache and progress
    print("\n[3/5] Loading cache and checking previous progress ...")
    cache    = _load_cache()
    progress = _load_progress()
    done_set = set(progress["done"])
    print(f"  Cache entries: {len(cache)}  |  Already enriched: {len(done_set)}")

    # Enrich
    print(f"\n[4/5] Deep-enriching top 50 leads (free sources only) ...")
    enriched_all: list[dict] = []

    # Load partial results if they exist
    if TOP50_ENR.exists():
        try:
            enriched_all = json.loads(TOP50_ENR.read_text())
        except Exception:
            enriched_all = []

    for i, lead in enumerate(top50, 1):
        name = str(lead.get("name") or lead.get("founder_name") or f"Lead#{i}")
        key  = str(lead.get("profile_url") or name)

        if key in done_set:
            print(f"  [{i:02d}/50] {name:35s} ← skipped (already done)")
            continue

        print(f"  [{i:02d}/50] {name:35s} enriching ...", end="", flush=True)
        t0 = time.time()

        enriched = enrich_lead(lead, cache)
        enriched_all.append(enriched)
        done_set.add(key)

        elapsed = time.time() - t0
        pm_flag = "✓ PM gap" if enriched.get("pm_gap_signal") else ""
        print(f" done ({elapsed:.1f}s) {pm_flag}")

        # Save every 5 leads
        if i % 5 == 0:
            TOP50_ENR.write_text(json.dumps(enriched_all, indent=2, ensure_ascii=False))
            _save_progress(list(done_set))
            _save_cache(cache)
            print(f"  → Progress saved ({i}/50)")

        # Polite delay
        time.sleep(0.5)

    # Final save
    TOP50_ENR.write_text(json.dumps(enriched_all, indent=2, ensure_ascii=False))
    _save_progress(list(done_set))
    _save_cache(cache)

    # Summary
    print(f"\n[5/5] Summary")
    pm_gaps = sum(1 for l in enriched_all if l.get("pm_gap_signal"))
    hiring_eng = sum(1 for l in enriched_all if l.get("hiring_engineers"))
    hiring_pm  = sum(1 for l in enriched_all if l.get("hiring_pm"))

    print(f"  Enriched leads  : {len(enriched_all)}")
    print(f"  PM gap signal   : {pm_gaps}")
    print(f"  Hiring engineers: {hiring_eng}")
    print(f"  Hiring PM       : {hiring_pm}")
    print(f"\n  Output → {TOP50_ENR.relative_to(BASE)}")
    print(f"  Cache  → {CACHE_FILE.relative_to(BASE)}")

    _print_dashboard_note()

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
