"""
Fix founder names in existing YC leads by re-scraping YC pages.
Also fixes msg_connection_note with improved phrasing.
Reads leads.csv, updates name/first_name/msg fields for source==YC rows, rewrites the file.
"""

import csv
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
import requests

OUTPUT_CSV = "/Users/mohit/Desktop/LinkedIn Outreach/output/leads.csv"
MAX_WORKERS = 25
REQUEST_TIMEOUT = 12

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
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

print_lock = threading.Lock()
def log(msg):
    with print_lock:
        print(msg)


def scrape_name_for_slug(li_slug, company_slug):
    """
    Scrape YC company page to find the real name for a given LinkedIn slug.
    Returns (real_name, li_slug) or (None, li_slug) if not found.
    """
    url = f"https://www.ycombinator.com/companies/{company_slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        html = unescape(resp.text)

        # Find name+slug pairs from founder cards
        pairs = re.findall(
            r'text-xl font-bold\">([^<]{2,60})<.*?linkedin\.com/in/([a-zA-Z0-9\-]+)',
            html,
            re.DOTALL
        )

        # Build slug -> name map
        slug_to_name = {}
        for name_raw, slug in pairs:
            name_clean = name_raw.strip()
            word_count = len(name_clean.split())
            has_emoji = bool(re.search(r'[^\x00-\x7F]', name_clean))
            if word_count <= 5 and not has_emoji and slug not in slug_to_name:
                slug_to_name[slug] = name_clean

        # Look up our target slug
        if li_slug in slug_to_name:
            return slug_to_name[li_slug]
        # Try case-insensitive
        li_slug_lower = li_slug.lstrip('-').lower()
        for k, v in slug_to_name.items():
            if k.lower() == li_slug_lower:
                return v
        return None
    except Exception:
        return None


def get_company_slug_from_profile(row):
    """Extract company slug from company name for YC page URL."""
    company = row.get("company", "")
    # Convert company name to slug format (lowercase, hyphenated)
    slug = re.sub(r'[^a-z0-9\s-]', '', company.lower())
    slug = re.sub(r'\s+', '-', slug.strip())
    return slug


def rebuild_messages(first_name, company_name, one_liner, website, batch):
    """Rebuild messages with the correct first_name."""
    one_liner_clean = (one_liner or f"building {company_name}").strip().rstrip(".")
    website_domain = re.sub(r'^https?://(www\.)?', '', website or "").rstrip("/") or company_name.lower().replace(" ", "") + ".com"

    msg_note = (
        f"{first_name}, \"{one_liner_clean}\" — love what you're solving at {company_name}. "
        f"Who's currently owning the roadmap and sprint process as you scale?"
    )
    msg_dm = (
        f"{first_name}, spent time understanding {company_name} — {one_liner_clean}. "
        f"With a small team and a lot of product surface, it's easy to end up building the loudest request instead of the highest-leverage one. "
        f"What does your current prioritization process look like?"
    )
    msg_f4 = (
        f"{first_name}, no pressure — just thinking about {company_name} and the PM question. "
        f"What's your biggest operational headache right now: shipping speed, customer alignment, or internal coordination?"
    )
    msg_f10 = (
        f"{first_name}, one more thought: most {website_domain}-stage teams hit a wall at 15–20 people without someone owning product coordination. "
        f"Is a dedicated PM on your roadmap? Would love 15 minutes to share how others have handled this."
    )
    msg_f17 = (
        f"{first_name}, if the PM conversation isn't the right fit right now, would you know anyone in your network building a similar-stage product team? "
        f"Either way — rooting for {company_name}."
    )
    msg_f25 = (
        f"{first_name}, last message from me. I'll leave the door open. "
        f"Keep shipping — what you're building at {company_name} is genuinely interesting."
    )
    wc_note = len(msg_note.split())
    wc_dm = len(msg_dm.split())
    return msg_note, msg_dm, msg_f4, msg_f10, msg_f17, msg_f25, wc_note, wc_dm


def fix_row(row):
    """For a YC row, try to get the real founder name and rebuild messages."""
    profile_url = row.get("profile_url", "")
    li_slug_match = re.search(r'linkedin\.com/in/([a-zA-Z0-9\-]+)', profile_url)
    if not li_slug_match:
        return row

    li_slug = li_slug_match.group(1)
    company_slug = get_company_slug_from_profile(row)

    real_name = scrape_name_for_slug(li_slug, company_slug)

    if real_name:
        first_name = real_name.split()[0]
        row["name"] = real_name
        row["first_name"] = first_name
        row["headline"] = f"Co-Founder at {row['company']} | {row.get('source','YC')}"
        row["background_summary"] = f"Founder building {row['company']}."
    else:
        first_name = row.get("first_name", "Founder")

    # Rebuild all messages with correct name
    one_liner = row.get("what_they_do", "")
    website = row.get("company_website", "")
    batch = row.get("source", "YC")
    company = row.get("company", "")

    m_note, m_dm, m_f4, m_f10, m_f17, m_f25, wc_note, wc_dm = rebuild_messages(
        first_name, company, one_liner, website, batch
    )
    row["msg_connection_note"] = m_note
    row["msg_first_dm"] = m_dm
    row["msg_followup_day4"] = m_f4
    row["msg_followup_day10"] = m_f10
    row["msg_followup_day17"] = m_f17
    row["msg_followup_day25"] = m_f25
    row["msg_word_count_note"] = wc_note
    row["msg_word_count_dm"] = wc_dm

    return row


def main():
    # Load all rows
    with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    log(f"[INIT] Loaded {len(rows)} rows from CSV")

    # Separate YC (new) vs non-YC rows
    yc_rows = [r for r in rows if r.get("source") == "YC"]
    other_rows = [r for r in rows if r.get("source") != "YC"]
    log(f"[INIT] YC rows to fix: {len(yc_rows)} | Other rows (preserve): {len(other_rows)}")

    # Fix names in parallel
    fixed_rows = []
    processed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fix_row, row): row for row in yc_rows}
        for future in as_completed(futures):
            processed += 1
            if processed % 100 == 0:
                log(f"[PROGRESS] Fixed {processed}/{len(yc_rows)}")
            try:
                result = future.result()
                fixed_rows.append(result)
            except Exception as e:
                # Keep original if error
                fixed_rows.append(futures[future])

    # Count how many were actually fixed
    name_fixed = sum(1 for r in fixed_rows if ' ' in r.get('name', ''))
    log(f"\n[NAMES] Fixed {name_fixed}/{len(fixed_rows)} rows now have 2-part names")

    # Combine: other rows first (preserves original 20), then fixed YC rows
    all_rows = other_rows + fixed_rows

    # Write back
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in all_rows:
            # Ensure all columns present
            clean = {col: row.get(col, "") for col in CSV_COLUMNS}
            writer.writerow(clean)

    log(f"\n[SAVED] Rewrote {len(all_rows)} rows to {OUTPUT_CSV}")
    log(f"[TOTAL] {len(all_rows)} leads total")


if __name__ == "__main__":
    import time
    start = time.time()
    main()
    print(f"\n[TIME] Runtime: {time.time()-start:.1f}s")
