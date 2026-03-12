"""
Dedupe — Stage 2 of the outreach pipeline.

Reads:  leads/qualified/qualified_leads.csv
Writes: leads/qualified/clean_leads.csv

Removes:
  1. Exact duplicate profile_url
  2. Exact duplicate company (keep highest icp_score)
  3. Fuzzy duplicate names at same company (Levenshtein distance < 3)

Usage:
    python3 scripts/dedupe.py
    python3 scripts/dedupe.py --dry-run   # show stats without writing
"""
import argparse
import logging
from pathlib import Path

import pandas as pd

try:
    from rapidfuzz.distance import Levenshtein
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT       = Path(__file__).parent.parent
INPUT_PATH = ROOT / "leads" / "qualified" / "qualified_leads.csv"
OUTPUT_PATH = ROOT / "leads" / "qualified" / "clean_leads.csv"


def normalise(val: str) -> str:
    """Lowercase, strip whitespace, remove common suffixes."""
    val = str(val or "").lower().strip()
    for suffix in [" inc", " ltd", " llc", " pvt", " corp", " co.", ",", "."]:
        val = val.replace(suffix, "")
    return val.strip()


def dedupe_profile_url(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove exact duplicate profile_urls — keep first occurrence."""
    before = len(df)
    df = df[df["profile_url"].notna() & (df["profile_url"].str.strip() != "")]
    df = df.drop_duplicates(subset=["profile_url"], keep="first")
    removed = before - len(df)
    if removed:
        logger.info(f"  profile_url dedupe: removed {removed}")
    return df, removed


def dedupe_company(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Per company, keep only the lead with the highest icp_score.
    If scores are equal, keep the one with more fields filled.
    """
    before = len(df)

    df["_company_norm"] = df["company"].apply(normalise)

    # Score completeness: count non-empty fields
    key_fields = ["profile_url", "name", "title", "signal_text",
                  "what_they_do", "inferred_pain_points", "msg_connection_note"]
    available = [f for f in key_fields if f in df.columns]
    df["_completeness"] = df[available].apply(
        lambda row: sum(1 for v in row if str(v).strip() not in ("", "nan")), axis=1
    )

    score_col = df["icp_score"] if "icp_score" in df.columns else pd.Series(0, index=df.index)
    df["_icp_score_num"] = pd.to_numeric(score_col, errors="coerce").fillna(0)

    # Sort: best score first, then most complete
    df = df.sort_values(["_icp_score_num", "_completeness"], ascending=[False, False])
    df = df.drop_duplicates(subset=["_company_norm"], keep="first")

    df = df.drop(columns=["_company_norm", "_completeness", "_icp_score_num"])

    removed = before - len(df)
    if removed:
        logger.info(f"  company dedupe: removed {removed} (kept highest-score per company)")
    return df, removed


def dedupe_fuzzy_names(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Remove leads where (name, company) is near-identical to another lead.
    Uses Levenshtein distance < 3 on the name field within same company.
    Falls back to exact match if rapidfuzz not installed.
    """
    if not FUZZY_AVAILABLE:
        # Fallback: exact name match within same company
        before = len(df)
        df["_name_norm"] = df["name"].apply(normalise)
        df["_company_norm"] = df["company"].apply(normalise)
        df = df.drop_duplicates(subset=["_name_norm", "_company_norm"], keep="first")
        df = df.drop(columns=["_name_norm", "_company_norm"])
        removed = before - len(df)
        if removed:
            logger.info(f"  name dedupe (exact): removed {removed}")
        return df, removed

    before = len(df)
    df = df.reset_index(drop=True)

    keep = [True] * len(df)
    names = df["name"].apply(normalise).tolist()
    companies = df["company"].apply(normalise).tolist()

    for i in range(len(df)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(df)):
            if not keep[j]:
                continue
            # Only compare within same company
            if companies[i] != companies[j]:
                continue
            dist = Levenshtein.distance(names[i], names[j])
            if dist < 3:
                keep[j] = False
                logger.debug(f"  fuzzy match: '{names[i]}' ≈ '{names[j]}' (dist={dist})")

    df = df[keep].reset_index(drop=True)
    removed = before - len(df)
    if removed:
        logger.info(f"  name fuzzy dedupe: removed {removed}")
    return df, removed


def main():
    parser = argparse.ArgumentParser(description="Dedupe qualified leads")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without writing")
    args = parser.parse_args()

    if not INPUT_PATH.exists():
        logger.error(f"Input not found: {INPUT_PATH}")
        logger.info("Run scripts/icp_filter.py first to generate qualified_leads.csv")
        return

    df = pd.read_csv(INPUT_PATH, low_memory=False, dtype=str).fillna("")
    original_count = len(df)
    logger.info(f"Loaded {original_count} qualified leads")

    if df.empty:
        logger.info("No leads to dedupe.")
        return

    total_removed = 0

    # Step 1 — exact profile_url
    df, n = dedupe_profile_url(df)
    total_removed += n

    # Step 2 — one lead per company (keep best)
    df, n = dedupe_company(df)
    total_removed += n

    # Step 3 — fuzzy name match within same company
    df, n = dedupe_fuzzy_names(df)
    total_removed += n

    df = df.reset_index(drop=True)

    print("\n" + "=" * 45)
    print("DEDUPE RESULTS")
    print("=" * 45)
    print(f"  Input    : {original_count}")
    print(f"  Removed  : {total_removed}")
    print(f"  Output   : {len(df)}")
    print("=" * 45)

    if not args.dry_run:
        df.to_csv(OUTPUT_PATH, index=False)
        logger.info(f"Saved → {OUTPUT_PATH}")
    else:
        logger.info("DRY RUN — nothing written")


if __name__ == "__main__":
    main()
