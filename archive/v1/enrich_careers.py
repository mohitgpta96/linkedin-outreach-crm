"""
Career page enrichment — PM Hiring Signal Detection
=====================================================
Checks career/jobs pages for ALL leads with a company_website.
Skips leads already marked "Actively hiring PM".

Usage:
    python3 enrich_careers.py           # process all leads with website
    python3 enrich_careers.py --limit 200   # only first N unprocessed
"""

import argparse
import pandas as pd
import requests
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

CSV_PATH = '/Users/mohit/Desktop/LinkedIn Outreach/output/leads.csv'
WORKERS  = 20
TIMEOUT  = 6

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
        text = re.sub(r'<[^>]+>', ' ', resp.text)
        text = re.sub(r'\s+', ' ', text)
        return text
    except Exception:
        return ''


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith('http'):
        url = 'https://' + url
    return url.rstrip('/')


def check_company(idx: int, website: str, current_size: str) -> dict:
    """
    Try career/jobs URLs for a company.
    Returns dict: idx, pm_found, company_size_hint
    """
    base = normalize_url(website)
    urls_to_try = [
        base + '/careers',
        base + '/jobs',
        base + '/about/careers',
        base,
    ]

    pm_found    = False
    size_hint   = None

    for url in urls_to_try:
        text = fetch_text(url)
        if not text:
            continue

        if PM_PATTERN.search(text):
            pm_found = True

        if not current_size or str(current_size).strip() in ('', 'nan', 'None'):
            for pat in TEAM_SIZE_PATTERNS:
                m = pat.search(text)
                if m:
                    n = int(m.group(1))
                    if 1 <= n <= 100000:
                        if n <= 10:       size_hint = '1-10'
                        elif n <= 50:     size_hint = '11-50'
                        elif n <= 200:    size_hint = '51-200'
                        elif n <= 500:    size_hint = '201-500'
                        elif n <= 1000:   size_hint = '501-1000'
                        else:             size_hint = '1000+'
                        break

        if pm_found:
            break

    return {'idx': idx, 'pm_found': pm_found, 'size_hint': size_hint}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0,
                        help='Max leads to check (0 = all unprocessed)')
    args = parser.parse_args()

    print("=" * 60)
    print("Career Page Enrichment — PM Hiring Signal")
    print("=" * 60)

    df = pd.read_csv(CSV_PATH, engine='python', on_bad_lines='skip')
    print(f"Loaded {len(df)} total leads.")

    # Ensure careers_page_roles column exists
    if 'careers_page_roles' not in df.columns:
        df['careers_page_roles'] = ''
    if 'company_size' not in df.columns:
        df['company_size'] = ''
    if 'growth_signals' not in df.columns:
        df['growth_signals'] = ''

    # Filter: has website
    has_website = (
        df['company_website'].notna() &
        (df['company_website'].astype(str).str.strip() != '') &
        (df['company_website'].astype(str).str.lower() != 'nan')
    )

    # Skip leads already marked as hiring PM
    already_done = df['growth_signals'].astype(str).str.contains('Actively hiring PM', case=False, na=False)
    to_process = df[has_website & ~already_done].copy()

    print(f"Leads with company_website: {has_website.sum()}")
    print(f"Already enriched (PM found): {(has_website & already_done).sum()}")
    print(f"Remaining to check: {len(to_process)}")

    if args.limit > 0:
        to_process = to_process.head(args.limit)
        print(f"Processing first {len(to_process)} (--limit set)")
    else:
        print(f"Processing ALL {len(to_process)} leads...")

    print()

    if to_process.empty:
        print("Nothing to process.")
        df.to_csv(CSV_PATH, index=False)
        return

    work_items = [
        (row.Index, row.company_website,
         row.company_size if hasattr(row, 'company_size') else '')
        for row in to_process.itertuples()
    ]

    results = {}
    completed = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        future_to_idx = {
            executor.submit(check_company, idx, website, size): idx
            for idx, website, size in work_items
        }

        for future in as_completed(future_to_idx):
            result = future.result()
            results[result['idx']] = result
            completed += 1
            if completed % 100 == 0:
                found_so_far = sum(1 for r in results.values() if r['pm_found'])
                elapsed = time.time() - start
                rate = completed / elapsed * 60
                remaining = (len(work_items) - completed) / (completed / elapsed) if completed else 0
                print(f"  {completed}/{len(work_items)} checked | "
                      f"PM found: {found_so_far} | "
                      f"{rate:.0f}/min | "
                      f"~{remaining/60:.1f}m left")

                # Save progress every 200 rows
                if completed % 200 == 0:
                    _apply_results(df, results)
                    try:
                        df.to_csv(CSV_PATH, index=False)
                        print(f"    ✓ Progress saved")
                    except Exception as e:
                        print(f"    ⚠️  Progress save failed (continuing): {e}")

    print(f"\nDone checking {len(results)} leads in {(time.time()-start)/60:.1f} minutes.")

    _apply_results(df, results)

    pm_found_rows = [idx for idx, r in results.items() if r['pm_found']]
    size_updated  = sum(1 for r in results.values() if r['size_hint'])

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Checked           : {len(results)}")
    print(f"PM hiring found   : {len(pm_found_rows)} (new)")
    total_pm = df['growth_signals'].astype(str).str.contains('Actively hiring PM', na=False).sum()
    print(f"Total PM signal   : {total_pm} (including previously enriched)")
    print(f"Company size added: {size_updated}")

    if pm_found_rows:
        print("\nSample — companies actively hiring a PM (new finds):")
        print("-" * 50)
        for i, idx in enumerate(pm_found_rows[:15], 1):
            name    = df.at[idx, 'name']
            company = df.at[idx, 'company']
            score   = df.at[idx, 'quality_score']
            website = df.at[idx, 'company_website']
            print(f"  {i:2d}. {name} @ {company}  (score={score:.0f})  [{website}]")

    try:
        df.to_csv(CSV_PATH, index=False)
        print(f"\nSaved {len(df)} leads → {CSV_PATH}")
    except Exception as e:
        raise RuntimeError(f"[enrich_careers] Failed to save final CSV: {e}") from e
    print("\nNext step: run  python3 filter_pm_leads.py  to delete non-PM leads")


def _apply_results(df: pd.DataFrame, results: dict) -> None:
    """Apply PM-found and size-hint updates to df in-place."""
    for idx, result in results.items():
        if result['pm_found']:
            try:
                current_score = float(df.at[idx, 'quality_score'])
            except (ValueError, TypeError):
                current_score = 50.0
            df.at[idx, 'quality_score'] = min(100.0, current_score + 40.0)

            existing = str(df.at[idx, 'growth_signals']) if pd.notna(df.at[idx, 'growth_signals']) else ''
            if 'Actively hiring PM' not in existing:
                if existing.strip() and existing.strip() not in ('nan', 'None', ''):
                    df.at[idx, 'growth_signals'] = existing + '; Actively hiring PM'
                else:
                    df.at[idx, 'growth_signals'] = 'Actively hiring PM'

        if result['size_hint']:
            current_size = df.at[idx, 'company_size']
            if pd.isna(current_size) or str(current_size).strip() in ('', 'nan', 'None'):
                df.at[idx, 'company_size'] = result['size_hint']


if __name__ == '__main__':
    main()
