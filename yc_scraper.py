"""
YC Company Scraper — generates 200+ enriched leads from YC-OSS API
Appends to output/leads.csv, deduplicates by profile_url
"""

import csv
import json
import os
import re
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import requests

# ── Constants ─────────────────────────────────────────────────────────────────
TODAY = "2026-03-03"
OUTPUT_DIR = "/Users/mohit/Desktop/LinkedIn Outreach/output"
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "leads.csv")
YC_API_URL = "https://yc-oss.github.io/api/companies/all.json"
YC_COMPANY_URL = "https://www.ycombinator.com/companies/{slug}"
MAX_WORKERS = 20
REQUEST_TIMEOUT = 12

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CSV_COLUMNS = [
    "name", "first_name", "title", "company", "location", "profile_url",
    "company_website", "signal_type", "signal_text", "signal_date", "source",
    "lead_temperature", "quality_score", "pipeline_stage", "verified",
    "warm_up_status", "outreach_status", "headline", "about_snippet",
    "background_summary", "skills", "post_themes", "post_tone",
    "recent_notable_post", "what_they_do", "company_size", "industry",
    "target_customer", "growth_signals", "careers_page_roles", "funding_stage",
    "funding_date", "funding_amount", "trigger_event", "trigger_date",
    "inferred_pain_points", "pm_value_prop", "suggested_opener",
    "msg_connection_note", "msg_first_dm", "msg_followup_day4",
    "msg_followup_day10", "msg_followup_day17", "msg_followup_day25",
    "msg_word_count_note", "msg_word_count_dm", "notes", "scraped_at",
]

TECH_SAAS_TAGS = {
    "saas", "b2b", "ai", "machine learning", "developer tools", "fintech",
    "healthcare", "edtech", "devops", "api", "cloud", "data", "analytics",
    "cybersecurity", "automation", "infrastructure", "marketplace", "web3",
    "crypto", "robotics", "biotech", "climate tech", "software", "platform",
}

INDIA_UK_UAE_KEYWORDS = {
    "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
    "chennai", "pune", "united kingdom", "london", "uk", "england",
    "uae", "dubai", "abu dhabi", "emirates",
}

print_lock = threading.Lock()

def log(msg):
    with print_lock:
        print(msg)


# ── Load existing leads (for dedup) ──────────────────────────────────────────
def load_existing_profile_urls():
    seen = set()
    if not os.path.exists(OUTPUT_CSV):
        return seen
    try:
        with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("profile_url", "").strip()
                if url:
                    seen.add(url.lower())
    except Exception:
        pass
    return seen


# ── Fetch YC API ──────────────────────────────────────────────────────────────
def fetch_yc_companies():
    log("[API] Fetching YC companies list...")
    resp = requests.get(YC_API_URL, timeout=30)
    resp.raise_for_status()
    all_companies = resp.json()
    log(f"[API] Total YC companies: {len(all_companies)}")

    filtered = [
        c for c in all_companies
        if c.get("status") == "Active"
        and c.get("isHiring") is True
        and isinstance(c.get("team_size"), int)
        and 5 <= c["team_size"] <= 200
    ]
    log(f"[API] Filtered (Active + Hiring + size 5-200): {len(filtered)}")
    return filtered


# ── Scrape YC company page for LinkedIn slugs + founder names ─────────────────
def scrape_yc_page(slug):
    """
    Returns list of (founder_name, linkedin_slug) tuples.
    Uses 3 extraction methods in order of reliability:
    1. JSON blob: "full_name":"NAME"..."linkedin_url":"...linkedin.com/in/SLUG"
    2. HTML card: div.text-xl.font-bold > NAME < ...linkedin.com/in/SLUG
    3. Fallback: slug-derived name
    """
    from html import unescape
    url = YC_COMPANY_URL.format(slug=slug)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        html = unescape(resp.text)

        result = []
        seen_slugs = []

        def add_pair(name, li_slug):
            name = name.strip()
            if not name or len(name) < 2:
                return
            has_emoji = bool(re.search(r'[^\x00-\x7F]', name))
            if has_emoji or len(name.split()) > 5:
                return
            if li_slug not in seen_slugs:
                seen_slugs.append(li_slug)
                result.append((name, li_slug))

        # Method 1: JSON blob — most reliable, covers cases where HTML order is reversed
        # Pattern: "full_name":"Anin Sayana",...,"linkedin_url":"https://.../in/anin-sayana-xx/"
        json_pairs = re.findall(
            r'"full_name":"([^"]{2,60})"[^}]{0,500}?"linkedin_url":"[^"]*linkedin\.com/in/([a-zA-Z0-9\-]+)',
            html,
            re.DOTALL
        )
        for name, li_slug in json_pairs:
            add_pair(name, li_slug)

        if result:
            return result

        # Method 2: HTML founder card — div.text-xl.font-bold > name then linkedin url
        html_pairs = re.findall(
            r'text-xl font-bold\">([^<]{2,60})<.*?linkedin\.com/in/([a-zA-Z0-9\-]+)',
            html,
            re.DOTALL
        )
        for name, li_slug in html_pairs:
            add_pair(name, li_slug)

        if result:
            return result

        # Method 3: Fallback — just slugs, derive name from slug
        slugs_found = re.findall(r'linkedin\.com/in/([a-zA-Z0-9\-]+)', html)
        seen_fb = []
        for s in slugs_found:
            if s not in seen_fb:
                seen_fb.append(s)
        return [(clean_name_from_slug(s), s) for s in seen_fb]

    except Exception:
        return []


# ── Scrape company website for description ────────────────────────────────────
def scrape_company_website(website_url):
    if not website_url:
        return ""
    try:
        resp = requests.get(
            website_url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )
        if resp.status_code != 200:
            return ""
        html = resp.text
        # Extract text from meta description
        meta_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{10,300})',
            html, re.IGNORECASE
        )
        if meta_match:
            return meta_match.group(1).strip()
        # Fallback: og:description
        og_match = re.search(
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']{10,300})',
            html, re.IGNORECASE
        )
        if og_match:
            return og_match.group(1).strip()
        return ""
    except Exception:
        return ""


# ── Clean founder name from LinkedIn slug ─────────────────────────────────────
def clean_name_from_slug(slug):
    # Remove hex suffix like -a1b2c3d (7+ hex chars)
    cleaned = re.sub(r'-[0-9a-f]{7,}$', '', slug, flags=re.IGNORECASE)
    parts = cleaned.split('-')
    # Take first 2 parts and capitalize
    name_parts = [p.capitalize() for p in parts[:2] if p]
    return " ".join(name_parts) if name_parts else slug.capitalize()


# ── Lead temperature from batch ───────────────────────────────────────────────
def get_lead_temperature(batch):
    b = batch.upper() if batch else ""
    if any(x in b for x in ["2025", "F25", "S25", "W25"]):
        return "Hot"
    if any(x in b for x in ["2024", "S24", "W24", "F24"]):
        return "Warm"
    return "Cold"


# ── Quality score ─────────────────────────────────────────────────────────────
def compute_quality_score(title, team_size, batch, tags, location):
    score = 0
    title_lower = (title or "").lower()
    if any(t in title_lower for t in ["founder", "ceo", "cto", "co-founder"]):
        score += 30
    if team_size and team_size <= 50:
        score += 20
    elif team_size and team_size <= 200:
        score += 10
    batch_upper = (batch or "").upper()
    if any(x in batch_upper for x in ["2025", "2024", "F25", "S25", "W25", "S24", "W24", "F24"]):
        score += 20
    tags_lower = {t.lower() for t in (tags or [])}
    if tags_lower & TECH_SAAS_TAGS:
        score += 10
    loc_lower = (location or "").lower()
    if any(k in loc_lower for k in INDIA_UK_UAE_KEYWORDS):
        score += 15
    return min(score, 100)


# ── Infer pain points ─────────────────────────────────────────────────────────
def infer_pain_points(one_liner, long_desc, team_size, industry, tags):
    desc = (one_liner or long_desc or "").lower()
    tags_lower = {t.lower() for t in (tags or [])}
    pains = []

    if team_size and team_size <= 20:
        pains.append("No dedicated PM to own the roadmap — founder is decision bottleneck")
        pains.append("Engineers pulled into product decisions instead of shipping code")
        pains.append("Sprint process ad-hoc or absent — features slip and priorities shift weekly")
    elif team_size and team_size <= 50:
        pains.append("Product process breaking down as team scales past 20 people")
        pains.append("Customer feedback not systematically fed into roadmap — building on gut")
        pains.append("Competing roadmap priorities with no single owner to resolve them")
    else:
        pains.append("Cross-functional coordination bottleneck — eng, sales, support all want different things")
        pains.append("Roadmap alignment across teams requires constant founder involvement")
        pains.append("Lack of structured sprint ceremonies slowing down delivery predictability")

    if "ai" in tags_lower or "machine learning" in tags_lower or "ai" in desc:
        pains.append("AI product iteration cycles fast — need PM to triage what actually moves the needle")
    if "b2b" in tags_lower or "enterprise" in desc:
        pains.append("Enterprise customer requests piling up without structured prioritization")

    return " | ".join(pains[:3])


# ── PM value prop ─────────────────────────────────────────────────────────────
def build_pm_value_prop(first_name, one_liner, team_size):
    desc_short = (one_liner or "the product").strip().rstrip(".")
    if team_size and team_size <= 20:
        return (
            f"Own the product roadmap so {first_name} can focus on growth and fundraising | "
            f"Set up lightweight sprint processes so engineers ship what matters most | "
            f"Turn customer conversations into structured feature priorities — close the feedback loop"
        )
    elif team_size and team_size <= 50:
        return (
            f"Own roadmap prioritization so {first_name} stops being the bottleneck | "
            f"Bridge engineering and customers — structured feedback → sprint backlog | "
            f"Drive delivery velocity with clear sprint goals and retrospectives"
        )
    else:
        return (
            f"Coordinate cross-functional roadmap so {first_name} focuses on strategy | "
            f"Own the sprint process and reduce context-switching for engineers | "
            f"Build the feedback loop: customers → features → shipped, systematically"
        )


# ── Message generation ────────────────────────────────────────────────────────
def generate_messages(first_name, company_name, one_liner, batch, website, title):
    one_liner_clean = (one_liner or f"what you're building at {company_name}").strip().rstrip(".")
    batch_str = batch or "YC"
    website_domain = re.sub(r'^https?://(www\.)?', '', website or "").rstrip("/") or company_name.lower().replace(" ", "") + ".com"
    title_lower = (title or "founder").lower()

    # connection note < 40 words — starts with first name + observation, ends with curiosity question
    msg_note = (
        f"{first_name}, \"{one_liner_clean}\" — love what you're solving at {company_name}. "
        f"Who's currently owning the roadmap and sprint process as you scale?"
    )

    # first DM < 60 words
    msg_dm = (
        f"{first_name}, spent time understanding {company_name} — {one_liner_clean}. "
        f"With a small team and a lot of product surface, it's easy to end up building the loudest request instead of the highest-leverage one. "
        f"What does your current prioritization process look like?"
    )

    # followup day 4 < 60 words — operational angle
    msg_f4 = (
        f"{first_name}, no pressure — just thinking about {company_name} and the PM question. "
        f"What's your biggest operational headache right now: shipping speed, customer alignment, or internal coordination?"
    )

    # followup day 10 < 60 words — reference website, soft call ask
    msg_f10 = (
        f"{first_name}, one more thought: most {website_domain}-stage teams hit a wall at 15–20 people without someone owning product coordination. "
        f"Is a dedicated PM on your roadmap? Would love 15 minutes to share how others have handled this."
    )

    # followup day 17 < 60 words — referral ask
    msg_f17 = (
        f"{first_name}, if the PM conversation isn't the right fit right now, would you know anyone in your network building a similar-stage product team? "
        f"Either way — rooting for {company_name}."
    )

    # followup day 25 < 40 words — breakup
    msg_f25 = (
        f"{first_name}, last message from me. I'll leave the door open. "
        f"Keep shipping — what you're building at {company_name} is genuinely interesting."
    )

    wc_note = len(msg_note.split())
    wc_dm = len(msg_dm.split())

    return msg_note, msg_dm, msg_f4, msg_f10, msg_f17, msg_f25, wc_note, wc_dm


# ── Suggested opener ──────────────────────────────────────────────────────────
def build_suggested_opener(first_name, company_name, one_liner, batch):
    one_liner_clean = (one_liner or f"building {company_name}").strip().rstrip(".")
    return (
        f"{first_name}, building {company_name} in a space where product chaos kills momentum fast. "
        f"Who's currently owning your roadmap and sprint process?"
    )


# ── Process one company → one lead row ───────────────────────────────────────
def process_company(company, existing_urls):
    slug = company.get("slug", "")
    name = company.get("name", "")
    one_liner = company.get("one_liner", "")
    long_desc = company.get("long_description", "")
    website = company.get("website", "")
    team_size = company.get("team_size")
    industry = company.get("industry", "")
    subindustry = company.get("subindustry", "")
    tags = company.get("tags", [])
    batch = company.get("batch", "")
    location = company.get("all_locations", "")
    regions = company.get("regions", [])

    # Scrape YC page for (name, linkedin_slug) pairs
    founders = scrape_yc_page(slug)
    if not founders:
        return None  # skip — no founder LinkedIn found

    # Use the first founder as primary lead
    founder_name, primary_slug = founders[0]
    profile_url = f"https://www.linkedin.com/in/{primary_slug}"

    # Dedup check
    if profile_url.lower() in existing_urls:
        log(f"  [SKIP] Duplicate: {profile_url}")
        return None

    # Use extracted name (already clean from HTML), fallback to slug derivation
    if not founder_name or len(founder_name) < 2:
        founder_name = clean_name_from_slug(primary_slug)
    first_name = founder_name.split()[0] if founder_name else "Founder"

    # Title — assume Founder/CEO for YC companies (we can't get exact title from page easily)
    title = "Co-Founder & CEO"

    # Scrape company website (optional — don't fail if slow)
    website_desc = ""
    if website:
        website_desc = scrape_company_website(website)

    # Description to use
    description = website_desc or long_desc or one_liner or ""

    # Lead temperature
    temperature = get_lead_temperature(batch)

    # Quality score
    qscore = compute_quality_score(title, team_size, batch, tags, location)

    # Signal text
    signal_text = (
        f"{batch} startup | {team_size} employees | {one_liner}"
    )

    # Growth signals
    growth_signals = f"{batch} backed, product-led growth"

    # Funding
    funding_stage = "Seed / YC"
    funding_date = TODAY
    funding_amount = "$500K–$2M (YC)"

    # Industry combined
    industry_full = ", ".join(filter(None, [industry, subindustry.split(" -> ")[-1] if " -> " in subindustry else subindustry]))

    # Pain points
    pain_points = infer_pain_points(one_liner, long_desc, team_size, industry, tags)

    # PM value prop
    pm_value = build_pm_value_prop(first_name, one_liner, team_size)

    # Suggested opener
    opener = build_suggested_opener(first_name, name, one_liner, batch)

    # Messages
    msg_note, msg_dm, msg_f4, msg_f10, msg_f17, msg_f25, wc_note, wc_dm = generate_messages(
        first_name, name, one_liner, batch, website, title
    )

    # Tags as skills
    skills = ", ".join(tags) if tags else ""

    # Target customer inference
    tags_lower = {t.lower() for t in tags}
    if "b2b" in tags_lower or "enterprise" in tags_lower:
        target_customer = "B2B / Enterprise"
    elif "b2c" in tags_lower or "consumer" in tags_lower:
        target_customer = "B2C / Consumer"
    else:
        target_customer = "B2B"

    # Company size string
    company_size_str = f"{team_size} employees" if team_size else ""

    # Headline
    headline = f"Co-Founder at {name} | {batch}"

    # About snippet
    about_snippet = (description[:300] + "...") if len(description) > 300 else description

    row = {
        "name": founder_name,
        "first_name": first_name,
        "title": title,
        "company": name,
        "location": location,
        "profile_url": profile_url,
        "company_website": website,
        "signal_type": "yc_hiring",
        "signal_text": signal_text,
        "signal_date": TODAY,
        "source": "YC",
        "lead_temperature": temperature,
        "quality_score": qscore,
        "pipeline_stage": "Found",
        "verified": "",
        "warm_up_status": "Not started",
        "outreach_status": "Not contacted",
        "headline": headline,
        "about_snippet": about_snippet,
        "background_summary": f"{batch} founder building {name}.",
        "skills": skills,
        "post_themes": "product building, startup growth, team scaling",
        "post_tone": "builder-focused, technical, direct",
        "recent_notable_post": "",
        "what_they_do": one_liner or description[:200],
        "company_size": company_size_str,
        "industry": industry_full,
        "target_customer": target_customer,
        "growth_signals": growth_signals,
        "careers_page_roles": "",
        "funding_stage": funding_stage,
        "funding_date": funding_date,
        "funding_amount": funding_amount,
        "trigger_event": f"{batch} company growing without a dedicated PM",
        "trigger_date": TODAY,
        "inferred_pain_points": pain_points,
        "pm_value_prop": pm_value,
        "suggested_opener": opener,
        "msg_connection_note": msg_note,
        "msg_first_dm": msg_dm,
        "msg_followup_day4": msg_f4,
        "msg_followup_day10": msg_f10,
        "msg_followup_day17": msg_f17,
        "msg_followup_day25": msg_f25,
        "msg_word_count_note": wc_note,
        "msg_word_count_dm": wc_dm,
        "notes": "",
        "scraped_at": TODAY,
    }

    log(f"  [OK] {founder_name} @ {name} ({batch}, {team_size} ppl) — {temperature} — score:{qscore}")
    return row


# ── Main orchestrator ─────────────────────────────────────────────────────────
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load existing to deduplicate
    existing_urls = load_existing_profile_urls()
    log(f"[INIT] Existing leads in CSV: {len(existing_urls)}")

    # Fetch and filter companies
    companies = fetch_yc_companies()

    # Shuffle to get diverse batches (don't always scrape same companies first)
    random.seed(42)
    random.shuffle(companies)

    # Run threaded scraping
    log(f"[SCRAPE] Starting {MAX_WORKERS}-thread scraping of {len(companies)} companies...")
    new_leads = []
    processed = 0
    skipped_no_li = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_company, c, existing_urls): c
            for c in companies
        }

        for future in as_completed(futures):
            processed += 1
            if processed % 50 == 0:
                log(f"[PROGRESS] Processed {processed}/{len(companies)} | Found so far: {len(new_leads)}")
            try:
                result = future.result()
                if result is not None:
                    # Add to new_leads and mark URL as seen (thread-safe via list append + GIL)
                    new_leads.append(result)
                    existing_urls.add(result["profile_url"].lower())
                else:
                    skipped_no_li += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    log(f"  [ERR] {e}")

    log(f"\n[DONE] Scraped {processed} companies")
    log(f"  New leads found: {len(new_leads)}")
    log(f"  Skipped (no LinkedIn): {skipped_no_li}")
    log(f"  Errors: {errors}")

    if not new_leads:
        log("[WARN] No new leads found.")
        return

    # Append to CSV
    file_exists = os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for lead in new_leads:
            writer.writerow(lead)

    log(f"\n[SAVED] {len(new_leads)} new leads appended to {OUTPUT_CSV}")
    total = len(existing_urls)
    log(f"[TOTAL] CSV now has approximately {total} unique leads")


if __name__ == "__main__":
    start = time.time()
    main()
    elapsed = time.time() - start
    print(f"\n[TIME] Total runtime: {elapsed:.1f}s")
