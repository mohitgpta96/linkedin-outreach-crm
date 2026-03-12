"""
Filter: Keep only leads who are actively hiring a Project Manager.
===================================================================
Deletes ALL leads with no PM hiring signal.

PM hiring signal = ANY of:
  1. signal_text contains PM hiring keywords
  2. growth_signals contains "Actively hiring PM"
  3. source is a PM job listing (The Muse, RemoteOK, HN, Wellfound, LinkedIn Jobs)
  4. careers_page_roles mentions PM

Usage:
    python3 filter_pm_leads.py           # dry-run (shows counts, no delete)
    python3 filter_pm_leads.py --apply   # actually delete non-PM leads
"""

import argparse
import re
import pandas as pd

CSV_PATH = '/Users/mohit/Desktop/LinkedIn Outreach/output/leads.csv'

# Keywords that confirm PM hiring intent
PM_SIGNAL_KEYWORDS = re.compile(
    r'project manager|product manager|\bpm\b|program manager|'
    r'project management|product management|hiring pm|looking for pm|'
    r'need a pm|we.re hiring a pm|pm role',
    re.IGNORECASE
)

# Sources that are inherently PM job listings
PM_SOURCES = re.compile(
    r'the muse|remoteok|hacker news|hn hiring|wellfound|linkedin jobs|'
    r'yc jobs|ycombinator',
    re.IGNORECASE
)


def has_pm_signal(row) -> bool:
    """Return True if this lead has any PM hiring signal."""

    # 1. growth_signals says PM hiring
    gs = str(row.get('growth_signals', '') or '')
    if PM_SIGNAL_KEYWORDS.search(gs):
        return True

    # 2. signal_text mentions PM hiring
    st = str(row.get('signal_text', '') or '')
    if PM_SIGNAL_KEYWORDS.search(st):
        return True

    # 3. careers_page_roles mentions PM
    cr = str(row.get('careers_page_roles', '') or '')
    if PM_SIGNAL_KEYWORDS.search(cr):
        return True

    # 4. source is a PM job listing platform
    src = str(row.get('source', '') or '')
    if PM_SOURCES.search(src):
        return True

    # 5. headline / about / what_they_do mentions they're hiring PM
    for col in ('headline', 'about_snippet', 'what_they_do'):
        val = str(row.get(col, '') or '')
        # Only match explicit hiring phrases, not just "project manager" generically
        if re.search(
            r'hiring\s+.*project\s+manager|looking\s+for\s+.*pm|'
            r'need\s+.*project\s+manager|join\s+.*as\s+.*pm',
            val, re.IGNORECASE
        ):
            return True

    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true',
                        help='Actually delete non-PM leads (without this flag, dry-run only)')
    args = parser.parse_args()

    print("=" * 60)
    print("PM Lead Filter")
    print("=" * 60)

    df = pd.read_csv(CSV_PATH, engine='python', on_bad_lines='skip')
    print(f"Total leads before filter: {len(df)}")

    # Apply PM signal check
    mask = df.apply(has_pm_signal, axis=1)
    pm_df    = df[mask].copy()
    non_pm_df = df[~mask].copy()

    print(f"\nLeads WITH PM hiring signal : {len(pm_df)}")
    print(f"Leads WITHOUT PM signal     : {len(non_pm_df)}  ← will be deleted")

    # Breakdown of why leads were kept
    print("\n--- Why leads were kept ---")
    kept_reasons = {
        'growth_signals (Actively hiring PM)': df[mask]['growth_signals'].astype(str).str.contains(
            'Actively hiring PM', case=False, na=False).sum(),
        'signal_text (PM keywords)': df[mask]['signal_text'].astype(str).str.contains(
            PM_SIGNAL_KEYWORDS.pattern, case=False, na=False).sum(),
        'source (PM job listing platform)': df[mask]['source'].astype(str).str.contains(
            PM_SOURCES.pattern, case=False, na=False).sum(),
        'careers_page_roles (PM mentioned)': df[mask]['careers_page_roles'].astype(str).str.contains(
            PM_SIGNAL_KEYWORDS.pattern, case=False, na=False).sum(),
    }
    for reason, count in kept_reasons.items():
        print(f"  {count:5d}  {reason}")

    print("\n--- Source distribution of kept leads ---")
    print(pm_df['source'].value_counts().to_string())

    print("\n--- Location distribution of kept leads ---")
    print(pm_df['location'].value_counts().head(15).to_string())

    if not args.apply:
        print("\n" + "=" * 60)
        print("DRY RUN — no changes made.")
        print(f"Run with --apply to delete {len(non_pm_df)} non-PM leads")
        print("=" * 60)
        return

    # Backup before delete
    backup_path = CSV_PATH.replace('leads.csv', 'leads_backup_pre_filter.csv')
    df.to_csv(backup_path, index=False)
    print(f"\nBackup saved: {backup_path}")

    # Save filtered data
    pm_df = pm_df.reset_index(drop=True)
    pm_df.to_csv(CSV_PATH, index=False)

    print(f"\n✅ Deleted {len(non_pm_df)} non-PM leads")
    print(f"✅ Kept {len(pm_df)} PM-hiring leads")
    print(f"✅ Saved to {CSV_PATH}")
    print("\nRestart Streamlit to see updated counts.")


if __name__ == '__main__':
    main()
