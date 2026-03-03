"""
Deep PM Enrichment
==================
For every confirmed PM-hiring lead:
  1. Re-scrapes the careers page and extracts the ACTUAL PM job title + description
  2. Builds a `pm_hiring_evidence` column — the specific proof they are hiring a PM
  3. Filters out non-tech/non-startup companies (Waste Management, HVAC, construction, etc.)
  4. Regenerates personalized outreach messages that reference the SPECIFIC job posting

New columns added:
  pm_job_title          — exact PM job title from their careers page
  pm_job_description    — first 300 chars of the job description
  pm_hiring_evidence    — human-readable explanation: "HOW WE KNOW they're hiring a PM"

Usage:
    python3 deep_enrich_pm.py           # dry-run: shows what would change, no save
    python3 deep_enrich_pm.py --apply   # run full enrichment and save
"""

import argparse
import re
import time
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pandas as pd
from bs4 import BeautifulSoup

CSV_PATH = '/Users/mohit/Desktop/LinkedIn Outreach/output/leads.csv'
WORKERS  = 15
TIMEOUT  = 7

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36'
}

# ── PM keyword patterns ───────────────────────────────────────────────────────
PM_ROLE_PATTERN = re.compile(
    r'\b((?:senior\s+|junior\s+|associate\s+|lead\s+|staff\s+|principal\s+)?'
    r'(?:product|project|program|technical)\s+manager'
    r'|(?:product|project|program)\s+management'
    r'|head\s+of\s+(?:product|project)'
    r'|\bpm\b)',
    re.IGNORECASE
)

# Job title extraction: look for PM roles that appear as headings/list items
JOB_TITLE_PATTERN = re.compile(
    r'((?:senior\s+|junior\s+|associate\s+|lead\s+|staff\s+|principal\s+|'
    r'group\s+|vp\s+of\s+|director\s+of\s+|head\s+of\s+)?'
    r'(?:product|project|program|technical)\s+manager'
    r'(?:\s*[-–—,]\s*[^\n\.]{0,60})?'
    r'|(?:product|project|program)\s+manager\s+(?:for|at|–|-)\s*[^\n\.]{0,50})',
    re.IGNORECASE
)

# Clearly non-tech industries — only remove if NO tech signals override
# Conservative: only the most obviously wrong industries (physical/industrial work)
BAD_INDUSTRY_PATTERNS = re.compile(
    r'\b(waste management|home improvement|hvac|plumbing|'
    r'building interior|grocery|retail store|'
    r'medical device implementation|hospital\b|'
    r'trucking|freight carrier|food service|restaurant|hotel\b|'
    r'printing|book publisher|crane|industrial crane|'
    r'project manager.*new berlin|project manager.*wi\b)\b',
    re.IGNORECASE
)

# Tech / startup companies — always keep even if matched above
TECH_SIGNALS = re.compile(
    r'\b(saas|api|software|platform|ai\b|ml\b|cloud|fintech|edtech|insurtech|'
    r'startup|tech\b|b2b|developer|engineering|product-led|yc\b|'
    r'app\b|mobile app|web app|marketplace|cursor|word processor|'
    r'robotics|autonomous|ml platform|data platform)\b',
    re.IGNORECASE
)

# Large well-known enterprises that definitely have PM teams already (not our ICP)
LARGE_CORP_NAMES = re.compile(
    r'\b(walmart|amazon\b|google\b|microsoft\b|apple\b|meta\b|blackrock|'
    r'capital one|charles schwab|liberty mutual|jpmorgan|jp morgan|'
    r'cisco\b|ibm\b|oracle\b|sap\b|salesforce|kroger|dhl\b|fedex|ups\b|'
    r'accenture|deloitte|kpmg|pwc\b|ernst.*young|hitachi|schneider electric|'
    r'kyndryl|konecranes|abm industries|hachette|bd\b|enovis|uline\b|spectrum\b|'
    r'blackrock|wind river|tiktok|epam\b|the muse\b)\b',
    re.IGNORECASE
)


# ── HTML fetch + parse ────────────────────────────────────────────────────────

def fetch_soup(url: str):
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        if resp.status_code != 200:
            return None
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception:
        return None


def extract_pm_job(soup):
    """
    Returns (pm_job_title, pm_job_description_snippet).
    Tries to find the actual PM job listing heading and surrounding text.
    """
    if not soup:
        return '', ''

    full_text = soup.get_text(separator=' ', strip=True)
    full_text = re.sub(r'\s+', ' ', full_text)

    # Strategy 1: Find heading tags (h1-h4, li, strong) that mention PM
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'li', 'strong', 'dt', 'a', 'span']):
        text = tag.get_text(strip=True)
        if PM_ROLE_PATTERN.search(text) and 10 < len(text) < 120:
            job_title = text.strip()
            # Get description: look at sibling or parent text
            desc = ''
            parent = tag.find_parent(['div', 'section', 'article', 'li'])
            if parent:
                parent_text = parent.get_text(separator=' ', strip=True)
                parent_text = re.sub(r'\s+', ' ', parent_text)
                # Take up to 300 chars after the title
                start = parent_text.find(job_title)
                if start >= 0:
                    desc = parent_text[start + len(job_title):start + len(job_title) + 320].strip()
            return job_title, desc[:300]

    # Strategy 2: Regex on full page text — find PM role with context
    m = JOB_TITLE_PATTERN.search(full_text)
    if m:
        job_title = m.group(0).strip()
        end = m.end()
        desc = full_text[end:end + 320].strip()
        # Remove leading punctuation
        desc = re.sub(r'^[^a-zA-Z0-9]+', '', desc)
        return job_title, desc[:300]

    # Strategy 3: Generic PM mention — just return snippet
    pm_match = PM_ROLE_PATTERN.search(full_text)
    if pm_match:
        start = max(0, pm_match.start() - 40)
        snippet = full_text[start:pm_match.end() + 280].strip()
        return '', snippet[:300]

    return '', ''


def scrape_pm_evidence(website: str) -> dict:
    """
    Scrapes careers pages and returns PM job info.
    """
    base = website.strip().rstrip('/')
    if not base.startswith('http'):
        base = 'https://' + base

    career_urls = [
        base + '/careers',
        base + '/jobs',
        base + '/about/careers',
        base + '/work-with-us',
        base + '/join-us',
        base + '/open-roles',
        base,
    ]

    for url in career_urls:
        soup = fetch_soup(url)
        if not soup:
            continue
        text = soup.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        if not PM_ROLE_PATTERN.search(text):
            continue
        # Found PM mention on this page
        job_title, job_desc = extract_pm_job(soup)
        return {
            'found': True,
            'job_title': job_title,
            'job_desc': job_desc,
            'source_url': url,
        }

    return {'found': False, 'job_title': '', 'job_desc': '', 'source_url': ''}


# ── Evidence builder ──────────────────────────────────────────────────────────

def build_evidence(row, scrape_result=None):
    """
    Returns a clear, human-readable explanation of WHY we know this person is hiring a PM.
    """
    src = str(row.get('source', '') or '')
    st  = str(row.get('signal_text', '') or '')
    gs  = str(row.get('growth_signals', '') or '')

    lines = []

    # Use scrape result if available
    if scrape_result and scrape_result.get('found'):
        jt = scrape_result.get('job_title', '')
        jd = scrape_result.get('job_desc', '')
        su = scrape_result.get('source_url', '')
        if jt:
            lines.append(f'📋 Job posted on careers page: "{jt}"')
        else:
            lines.append(f'📋 PM role found on careers page ({su.split("/")[-1] or "homepage"})')
        if jd:
            # Trim to first sentence or 150 chars
            first_sent = re.split(r'[.!?]', jd)[0].strip()
            if first_sent and len(first_sent) < 200:
                lines.append(f'   Role description: {first_sent}')
            else:
                lines.append(f'   Role description: {jd[:150]}...')

    # Source signal
    if re.search(r'hacker.?news|hn.?hiring|\bhn\b', src, re.IGNORECASE):
        lines.append(f'🟠 HN "Who is Hiring?" thread: mentioned PM role')
        if st and len(st) > 10:
            lines.append(f'   "{st[:180]}"')
    elif re.search(r'the.?muse', src, re.IGNORECASE):
        lines.append(f'🔵 The Muse job listing: {st[:120]}')
    elif re.search(r'remoteok', src, re.IGNORECASE):
        lines.append(f'🌐 RemoteOK job listing: {st[:120]}')
    elif re.search(r'yc|ycombinator', src, re.IGNORECASE):
        lines.append(f'🚀 YC-backed startup — PM role found on company website')
        batch = re.search(r'(YC\s*(?:W|S|Winter|Summer|Fall|Spring)\s*\d{2,4})', src, re.IGNORECASE)
        if batch:
            lines.append(f'   Batch: {batch.group(1)}')

    # LinkedIn/Crunchbase source — show signal_text once
    signal_shown = any('signal' in l.lower() or 'hiring' in l.lower() for l in lines)
    if re.search(r'linkedin|crunchbase', src, re.IGNORECASE) and st and len(st) > 10 and not signal_shown:
        lines.append(f'💼 LinkedIn/Crunchbase: "{st[:160]}"')

    # Growth signals — only show non-duplicate info
    if 'Actively hiring PM' in gs:
        if not any('careers page' in l.lower() or 'job posted' in l.lower() for l in lines):
            lines.append('✅ PM role confirmed on company careers page')
    elif PM_ROLE_PATTERN.search(gs) and gs.strip() != st.strip():
        # Only show if different from signal_text
        lines.append(f'📈 Growth signal: {gs[:150]}')

    # Fallback
    if not lines:
        lines.append('⚠️  PM keyword found — requires manual verification')

    return '\n'.join(lines)


# ── Industry filter ───────────────────────────────────────────────────────────

def is_non_tech(row) -> bool:
    """Return True if this is clearly NOT a tech/startup founder hire."""
    company = str(row.get('company', '') or '')
    signal  = str(row.get('signal_text', '') or '')
    src     = str(row.get('source', '') or '')
    name    = str(row.get('name', '') or '')

    # Always remove well-known large corporations (they have PM teams)
    if LARGE_CORP_NAMES.search(company):
        return True

    # Remove The Muse / RemoteOK leads with no founder name
    # (these are HR postings, not founder-direct connections)
    if re.search(r'the.?muse|remoteok', src, re.IGNORECASE):
        if not name or name.lower() in ('nan', 'none', ''):
            return True

    # Remove clearly non-tech job titles from The Muse / RemoteOK
    if re.search(r'the.?muse|remoteok', src, re.IGNORECASE):
        bad_titles = re.compile(
            r'\b(hvac|plumbing|electrical|home improvement|waste|'
            r'construction project manager|real estate project manager|'
            r'building interiors|field project manager|'
            r'service project manager|industrial|crane|'
            r'food|restaurant|hotel|hospital|medical device)\b',
            re.IGNORECASE
        )
        if bad_titles.search(signal):
            return True

    # Check industry-level match (only if no tech override)
    fields = company + ' ' + signal
    if BAD_INDUSTRY_PATTERNS.search(fields):
        if TECH_SIGNALS.search(fields):
            return False
        return True

    return False


# ── Message generator ─────────────────────────────────────────────────────────

def gen_messages_v2(name, company, pm_job_title,
                    pm_job_desc, signal_text, website):
    """
    Generate outreach messages that explicitly reference the PM job posting evidence.
    """
    first = name.split()[0] if name and name.lower() not in ('nan', 'none', '') else 'there'
    co    = (company or 'your company').strip().lstrip('@')
    web   = (website or '').replace('https://','').replace('http://','').rstrip('/')

    # Build a specific reference phrase
    if pm_job_title and len(pm_job_title) > 5:
        role_ref = f'the {pm_job_title} role'
        role_short = pm_job_title[:60]
    elif signal_text and len(signal_text) > 10:
        role_ref = 'the PM opening'
        role_short = signal_text[:80]
    else:
        role_ref = 'a PM role'
        role_short = ''

    # Connection note (≤ 280 chars, starts with THEM, ends with question)
    connection_note = (
        f"{first} — saw {co} is hiring for {role_ref}. "
        f"What kind of PM ownership are you looking for as the team scales?"
    )[:280]

    # First DM (≤ 300 chars, give-first, ends with question)
    web_ref = f' — {web}' if web else ''
    first_dm = (
        f"{first}, took a look at {co}{web_ref}. "
        f"Your search for a PM to own {role_short[:50] or 'product delivery'} caught my eye. "
        f"What's the biggest product challenge you're hoping the PM will solve first?"
    )[:300]

    # Follow-ups
    followup_4 = (
        f"{first}, no pressure — just curious what's slowing {co} down the most right now. "
        f"Happy to think through the PM scope with you if useful."
    )

    followup_10 = (
        f"{first}, still thinking about the {role_ref} at {co}. "
        f"Open to a 15-min chat about what's worked for similar-stage teams on the product side?"
    )

    followup_17 = (
        f"{first}, if the timing on the {role_ref} isn't right yet — "
        f"would you know anyone in your network who is actively hiring a PM? "
        f"Either way, rooting for {co}."
    )

    followup_25 = (
        f"{first}, last note from me. "
        f"{co} looks like something worth following. "
        f"Leaving the door open if the PM search is still ongoing. Wish you the best."
    )

    return {
        'msg_connection_note':  connection_note,
        'msg_first_dm':         first_dm,
        'msg_followup_day4':    followup_4,
        'msg_followup_day10':   followup_10,
        'msg_followup_day17':   followup_17,
        'msg_followup_day25':   followup_25,
        'msg_word_count_note':  len(connection_note.split()),
        'msg_word_count_dm':    len(first_dm.split()),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true',
                        help='Save results to CSV (without this: dry run only)')
    parser.add_argument('--limit', type=int, default=0,
                        help='Only process first N leads (0 = all)')
    args = parser.parse_args()

    print("=" * 65)
    print("Deep PM Enrichment")
    print("=" * 65)

    df = pd.read_csv(CSV_PATH, engine='python', on_bad_lines='skip')
    print(f"Loaded {len(df)} leads\n")

    # Ensure new columns exist
    for col in ['pm_job_title', 'pm_job_description', 'pm_hiring_evidence']:
        if col not in df.columns:
            df[col] = ''

    # ── Step 1: Filter non-tech companies ────────────────────────────────────
    print("Step 1: Filtering non-tech / no-founder leads...")
    non_tech_mask = df.apply(is_non_tech, axis=1)
    non_tech_count = non_tech_mask.sum()
    print(f"  Non-tech / enterprise leads to remove: {non_tech_count}")
    if non_tech_count > 0 and not args.apply:
        sample = df[non_tech_mask][['name', 'company', 'source']].head(10)
        print("  Sample (would be deleted):")
        for _, r in sample.iterrows():
            print(f"    {r['company']} (src={r['source']})")

    # ── Step 2: Scrape careers pages for PM job details ──────────────────────
    print("\nStep 2: Scraping careers pages for PM job title + description...")

    # Process all leads with a website that haven't been scraped for PM details yet
    needs_scrape = (
        df['company_website'].notna() &
        (df['company_website'].astype(str).str.strip() != '') &
        (df['company_website'].astype(str).str.lower() != 'nan') &
        (~non_tech_mask)
    )
    to_scrape = df[needs_scrape].copy()

    if args.limit > 0:
        to_scrape = to_scrape.head(args.limit)

    print(f"  Careers pages to scrape: {len(to_scrape)}")

    scrape_results = {}
    start = time.time()
    completed = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        future_to_idx = {
            executor.submit(scrape_pm_evidence, row['company_website']): idx
            for idx, row in to_scrape.iterrows()
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result()
            except Exception:
                result = {'found': False, 'job_title': '', 'job_desc': '', 'source_url': ''}
            scrape_results[idx] = result
            completed += 1
            if completed % 100 == 0:
                found = sum(1 for r in scrape_results.values() if r.get('found'))
                elapsed = time.time() - start
                rate = completed / elapsed * 60
                remaining = (len(to_scrape) - completed) / (completed / elapsed)
                print(f"  {completed}/{len(to_scrape)} scraped | "
                      f"PM job details found: {found} | "
                      f"{rate:.0f}/min | ~{remaining/60:.1f}m left")

    elapsed = time.time() - start
    found_count = sum(1 for r in scrape_results.values() if r.get('found'))
    print(f"\n  Done in {elapsed/60:.1f}m — PM job details extracted: {found_count}/{len(scrape_results)}")

    # ── Step 3: Apply results ─────────────────────────────────────────────────
    print("\nStep 3: Building pm_hiring_evidence and regenerating messages...")

    updated = 0
    for idx, row in df.iterrows():
        if non_tech_mask.at[idx]:
            continue

        scrape = scrape_results.get(idx)
        row_dict = row.to_dict()

        # Store PM job details from scrape
        if scrape and scrape.get('found'):
            if scrape.get('job_title'):
                df.at[idx, 'pm_job_title'] = scrape['job_title']
            if scrape.get('job_desc'):
                df.at[idx, 'pm_job_description'] = scrape['job_desc'][:300]

        # Build evidence
        evidence = build_evidence(row_dict, scrape)
        df.at[idx, 'pm_hiring_evidence'] = evidence

        # Regenerate messages
        msgs = gen_messages_v2(
            name=str(row_dict.get('name', '') or ''),
            company=str(row_dict.get('company', '') or ''),
            pm_job_title=str(df.at[idx, 'pm_job_title'] or ''),
            pm_job_desc=str(df.at[idx, 'pm_job_description'] or ''),
            signal_text=str(row_dict.get('signal_text', '') or ''),
            website=str(row_dict.get('company_website', '') or ''),
        )
        for k, v in msgs.items():
            df.at[idx, k] = v

        updated += 1

    print(f"  Evidence + messages updated for {updated} leads")

    # ── Step 4: Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("RESULTS SUMMARY")
    print("=" * 65)

    final_df = df[~non_tech_mask].copy() if args.apply else df
    kept = len(final_df) if args.apply else len(df) - non_tech_count

    print(f"  Non-tech / enterprise leads removed : {non_tech_count}")
    print(f"  Leads remaining after filter        : {kept}")
    print(f"  PM job title extracted              : {(df['pm_job_title'].astype(str).str.strip() != '').sum()}")
    print(f"  PM job description extracted        : {(df['pm_job_description'].astype(str).str.strip() != '').sum()}")
    print(f"  pm_hiring_evidence populated        : {(df['pm_hiring_evidence'].astype(str).str.strip() != '').sum()}")

    # Show 10 sample evidences
    print("\n--- Sample pm_hiring_evidence (first 10 leads) ---")
    sample_df = df[~non_tech_mask].head(10)
    for _, r in sample_df.iterrows():
        print(f"\n  {r['name']} @ {r['company']}")
        if str(r.get('pm_job_title', '')).strip() not in ('', 'nan'):
            print(f"  PM Job Title: {r['pm_job_title']}")
        ev = str(r.get('pm_hiring_evidence', '')).replace('\n', '\n    ')
        print(f"  Evidence:\n    {ev}")
        print(f"  Connection note: {str(r['msg_connection_note'])[:140]}")

    if not args.apply:
        print("\n" + "=" * 65)
        print("DRY RUN — no changes saved.")
        print("Run with --apply to save results.")
        print("=" * 65)
        return

    # Apply deletion of non-tech leads + save
    backup = CSV_PATH.replace('leads.csv', 'leads_pre_deep_enrich.csv')
    df.to_csv(backup, index=False)
    print(f"\nBackup saved: {backup}")

    final_df = df[~non_tech_mask].reset_index(drop=True)
    final_df.to_csv(CSV_PATH, index=False)
    print(f"Saved {len(final_df)} leads → {CSV_PATH}")
    print("\nRestart Streamlit to see changes: pkill -f 'streamlit' && streamlit run streamlit_app.py")


if __name__ == '__main__':
    main()
