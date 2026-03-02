"""
Career page enrichment script.
Checks company career/jobs pages for PM openings.
Updates quality_score (+40 if found, capped at 100) and growth_signals.
Also extracts company size hints if company_size is empty.
"""

import pandas as pd
import requests
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

CSV_PATH = '/Users/mohit/Desktop/LinkedIn Outreach/output/leads.csv'
MAX_LEADS = 500
WORKERS = 20
TIMEOUT = 5

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36'
}

PM_KEYWORDS = [
    'project manager',
    'product manager',
    r'\bpm\b',
    'program manager',
    'project management',
    'product management',
]
PM_PATTERN = re.compile('|'.join(PM_KEYWORDS), re.IGNORECASE)

TEAM_SIZE_PATTERNS = [
    re.compile(r'team of (\d+)', re.IGNORECASE),
    re.compile(r'(\d+)\+?\s*employees', re.IGNORECASE),
    re.compile(r'(\d+)\+?\s*people', re.IGNORECASE),
    re.compile(r'(\d+)\+?\s*members', re.IGNORECASE),
    re.compile(r'(\d+)\s*person team', re.IGNORECASE),
]


def fetch_text(url: str) -> str:
    """Fetch a URL and return plain text (stripped HTML tags). Returns '' on error."""
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        if resp.status_code != 200:
            return ''
        # Strip HTML tags quickly with regex
        text = re.sub(r'<[^>]+>', ' ', resp.text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        return text
    except Exception:
        return ''


def normalize_url(url: str) -> str:
    """Ensure URL has https:// prefix and no trailing slash."""
    url = url.strip()
    if not url.startswith('http'):
        url = 'https://' + url
    return url.rstrip('/')


def check_company(idx: int, website: str, current_size: str) -> dict:
    """
    Try career/jobs URLs for a company.
    Returns dict with:
      - idx: row index
      - pm_found: bool
      - company_size_hint: str or None
    """
    base = normalize_url(website)
    urls_to_try = [
        base + '/careers',
        base + '/jobs',
        base + '/about/careers',
        base,  # homepage as fallback
    ]

    pm_found = False
    size_hint = None

    for url in urls_to_try:
        text = fetch_text(url)
        if not text:
            continue

        # Check PM keywords
        if PM_PATTERN.search(text):
            pm_found = True

        # Try to extract company size if not already set
        if not current_size or str(current_size).strip() in ('', 'nan', 'None'):
            for pat in TEAM_SIZE_PATTERNS:
                m = pat.search(text)
                if m:
                    n = int(m.group(1))
                    if 1 <= n <= 100000:  # sanity check
                        if n <= 10:
                            size_hint = '1-10'
                        elif n <= 50:
                            size_hint = '11-50'
                        elif n <= 200:
                            size_hint = '51-200'
                        elif n <= 500:
                            size_hint = '201-500'
                        elif n <= 1000:
                            size_hint = '501-1000'
                        else:
                            size_hint = '1000+'
                        break

        # If we found PM hiring, no need to check more pages
        if pm_found:
            break

    return {'idx': idx, 'pm_found': pm_found, 'size_hint': size_hint}


def main():
    print("=" * 60)
    print("Career Page Enrichment — PM Hiring Signal")
    print("=" * 60)

    # Load CSV
    df = pd.read_csv(CSV_PATH, engine='python', on_bad_lines='skip')
    print(f"Loaded {len(df)} total leads.")

    # Filter leads with non-empty company_website
    has_website_mask = df['company_website'].notna() & (df['company_website'].str.strip() != '')
    website_df = df[has_website_mask].copy()
    print(f"Leads with company_website: {len(website_df)}")

    # Take first MAX_LEADS
    subset = website_df.head(MAX_LEADS)
    print(f"Processing first {len(subset)} leads...\n")

    # Prepare work items: (original_index, website, current_size)
    work_items = [
        (row.Index, row.company_website, row.company_size if hasattr(row, 'company_size') else '')
        for row in subset.itertuples()
    ]

    results = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        future_to_idx = {
            executor.submit(check_company, idx, website, size): idx
            for idx, website, size in work_items
        }

        for future in as_completed(future_to_idx):
            result = future.result()
            results[result['idx']] = result
            completed += 1
            if completed % 50 == 0:
                found_so_far = sum(1 for r in results.values() if r['pm_found'])
                print(f"  Progress: {completed}/{len(work_items)} checked | PM found: {found_so_far}")

    print(f"\nDone checking. Total checked: {len(results)}")

    # Apply updates to original DataFrame
    pm_found_rows = []
    size_updated = 0

    for idx, result in results.items():
        if result['pm_found']:
            # Add +40 to quality_score, cap at 100
            current_score = df.at[idx, 'quality_score']
            try:
                current_score = float(current_score)
            except (ValueError, TypeError):
                current_score = 50.0
            new_score = min(100.0, current_score + 40.0)
            df.at[idx, 'quality_score'] = new_score

            # Update growth_signals
            existing = str(df.at[idx, 'growth_signals']) if pd.notna(df.at[idx, 'growth_signals']) else ''
            if 'Actively hiring PM' not in existing:
                if existing.strip() and existing.strip() not in ('nan', 'None', ''):
                    df.at[idx, 'growth_signals'] = existing + '; Actively hiring PM'
                else:
                    df.at[idx, 'growth_signals'] = 'Actively hiring PM'

            pm_found_rows.append(idx)

        # Update company_size if hint found and field is empty
        if result['size_hint']:
            current_size = df.at[idx, 'company_size']
            if pd.isna(current_size) or str(current_size).strip() in ('', 'nan', 'None'):
                df.at[idx, 'company_size'] = result['size_hint']
                size_updated += 1

    # ---- Summary ----
    print("\n" + "=" * 60)
    print(f"RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total leads checked     : {len(results)}")
    print(f"PM hiring found         : {len(pm_found_rows)}")
    print(f"Company size updated    : {size_updated}")
    print()

    if pm_found_rows:
        print("Top 20 companies actively hiring a PM:")
        print("-" * 50)
        top20 = pm_found_rows[:20]
        for i, idx in enumerate(top20, 1):
            name = df.at[idx, 'name']
            company = df.at[idx, 'company']
            score = df.at[idx, 'quality_score']
            website = df.at[idx, 'company_website']
            print(f"  {i:2d}. {name} @ {company}  (score={score:.0f})  [{website}]")

    print()
    print("Updated Quality Score Distribution:")
    print("-" * 40)
    score_dist = df['quality_score'].value_counts(bins=[0, 30, 50, 70, 85, 100], sort=False)
    print(score_dist.to_string())
    print()
    print(f"Mean score: {df['quality_score'].mean():.1f}")
    print(f"Leads at 100: {(df['quality_score'] == 100).sum()}")

    # Save back to CSV
    df.to_csv(CSV_PATH, index=False)
    print()
    print(f"Done! Saved {len(df)} leads to leads.csv")


if __name__ == '__main__':
    main()
