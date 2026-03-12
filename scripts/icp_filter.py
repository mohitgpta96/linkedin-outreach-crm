"""
ICP Filter — Stage 1 of the outreach pipeline.

Reads:  leads/raw/raw_leads.csv
Writes: leads/qualified/qualified_leads.csv
Logs:   logs/rejected_leads.csv

Steps:
  1. Hard reject (Python rules, no API cost)
  2. Claude ICP score (Anthropic API, ~$0.003/lead)
  3. Accept if score >= 70

Usage:
    python3 scripts/icp_filter.py
    python3 scripts/icp_filter.py --dry-run        # score without writing
    python3 scripts/icp_filter.py --limit 20       # process first N leads
    python3 scripts/icp_filter.py --rescore        # re-score already-scored leads
"""
import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
RAW_PATH     = ROOT / "leads" / "raw" / "raw_leads.csv"
QUAL_PATH    = ROOT / "leads" / "qualified" / "qualified_leads.csv"
REJECT_PATH  = ROOT / "logs" / "rejected_leads.csv"

# ── Thresholds ─────────────────────────────────────────────────────────────────
SCORE_THRESHOLD = 70

# ── Hard Reject Rules ─────────────────────────────────────────────────────────

REJECT_TITLES = [
    "recruiter", "talent acquisition", "talent partner", "hr ", "human resources",
    "head of hr", "chief people", "people ops", "people operations",
    "marketing", "growth hacker", "seo", "content writer", "brand manager",
    "sales manager", "account executive", "account manager", "business development rep",
    "finance", "cfo", "accountant", "legal", "counsel", "lawyer",
    "designer", "ux designer", "ui designer", "graphic designer",
    "data scientist", "data analyst", "machine learning engineer",
    "software engineer", "frontend engineer", "backend engineer",
    "devops", "sre", "site reliability",
]

REJECT_INDUSTRIES = [
    "staffing", "outsourcing", "body shop", "manpower", "headhunting",
    "recruitment agency", "digital marketing agency", "seo agency",
    "advertising agency", "media agency", "pr agency",
    "web3", "crypto", "nft", "blockchain", "defi", "dao",
    "gambling", "casino", "betting", "adult",
    "real estate agency", "insurance brokerage",
]

REJECT_COMPANY_KEYWORDS = [
    "consulting llp", "pvt ltd consultants", "services pvt", "outsourcing pvt",
    "staffing solutions", "manpower solutions", "talent solutions",
]

MAX_COMPANY_SIZE = 200
MIN_COMPANY_SIZE = 2


def hard_reject(row: dict) -> tuple[bool, str]:
    """
    Returns (should_reject, reason).
    Fast Python checks — no API cost.
    """
    title    = str(row.get("title", "") or "").lower().strip()
    industry = str(row.get("industry", "") or "").lower().strip()
    company  = str(row.get("company", "") or "").lower().strip()
    name     = str(row.get("name", "") or "").strip()
    purl     = str(row.get("profile_url", "") or "").strip()
    what     = str(row.get("what_they_do", "") or "").lower().strip()
    signal   = str(row.get("signal_text", "") or "").lower().strip()

    # 1. Missing critical fields
    if not purl:
        return True, "no_profile_url"
    if not name and not company:
        return True, "no_name_and_no_company"
    if not company:
        return True, "no_company"

    # 2. Title is non-decision-maker
    for t in REJECT_TITLES:
        if t in title:
            return True, f"title_reject:{t}"

    # 3. Industry / company type
    combined_industry = f"{industry} {what} {company} {signal}"
    for ind in REJECT_INDUSTRIES:
        if ind in combined_industry:
            return True, f"industry_reject:{ind}"

    for kw in REJECT_COMPANY_KEYWORDS:
        if kw in company:
            return True, f"company_keyword_reject:{kw}"

    # 4. Company size
    size_raw = str(row.get("company_size", "") or "").strip()
    if size_raw:
        # Handle ranges like "11-50", "51-200"
        try:
            if "-" in size_raw:
                upper = int(size_raw.split("-")[-1])
                lower = int(size_raw.split("-")[0])
            else:
                upper = int(float(size_raw))
                lower = upper

            if upper > MAX_COMPANY_SIZE:
                return True, f"company_too_large:{size_raw}"
            if upper < MIN_COMPANY_SIZE:
                return True, f"company_too_small:{size_raw}"
        except ValueError:
            pass  # unparseable size — don't reject, let Claude decide

    return False, ""


# ── Claude ICP Scoring ─────────────────────────────────────────────────────────

ICP_SYSTEM_PROMPT = """You are an ICP (Ideal Client Profile) scoring engine for a freelance Project Manager's LinkedIn outreach.

The PM is: Mohit — Freelance Project Manager (Agile, Scrum, Waterfall, Hybrid)
His services: Fractional PM, Project Setup, Project Recovery, AI-assisted PM workflows
His sweet spot: Tech startups (5–50 employees) that need PM structure but can't justify a full-time hire

PRIMARY PERSONA (highest value):
  Founder / CEO / Co-Founder at a tech startup, 3–50 employees, seed to Series B
  Pain: playing PM themselves, context-switching, missing deadlines

SECONDARY PERSONA (good fit):
  CTO / VP Engineering / Head of Engineering at a growing startup (5–100 employees)
  Pain: hiring devs but no one managing delivery, sprints chaotic, deadlines slipping

ACCEPT:
  Titles: founder, co-founder, ceo, cto, vp engineering, head of engineering, engineering director
  Industries: SaaS, FinTech, HealthTech, DevTools, EdTech, AI/ML, E-commerce tech, Infrastructure tech
  Company size: 3–100 employees (ideal: 5–50)
  Funding: bootstrapped, pre-seed, seed, series A, series B
  Geography: India, USA, UK, Germany, UAE, Singapore, Canada, Australia

REJECT:
  Companies with 200+ employees
  Non-tech companies
  Staffing / outsourcing / agencies
  Crypto/web3 (unless well-funded)
  Anyone with no buying signal

BUYING SIGNALS (detectable from data):
  - PM/Scrum Master job posting in signal_text or pm_hiring_evidence
  - Recent funding announcement in signal_text
  - YC-backed (source contains YC)
  - Company growing (team_size 10–50, hiring signal present)
  - Active LinkedIn poster (post_themes or recent_notable_post not empty)

You must return ONLY valid JSON. No explanation, no markdown, no extra text.
"""

ICP_USER_TEMPLATE = """Score this lead for ICP fit:

Name: {name}
Title: {title}
Company: {company}
Industry: {industry}
Company Size: {company_size}
Location: {location}
What They Do: {what_they_do}
Signal Text: {signal_text}
Source: {source}
PM Hiring Evidence: {pm_hiring_evidence}
Post Themes: {post_themes}

Return ONLY this JSON:
{{
  "icp_score": <integer 0-100>,
  "persona": "<founder|cto|eng_manager|tpm|none>",
  "pass": <true if score >= 70 else false>,
  "buying_signal": "<pm_job|funding|yc_backed|growing|active_poster|none>",
  "reject_reason": "<specific reason if pass=false, else null>",
  "confidence": "<high|medium|low>",
  "fit_summary": "<one sentence max explaining the score>"
}}"""


def score_with_claude(client: Anthropic, row: dict, dry_run: bool = False) -> dict:
    """Call Claude to score a lead. Returns scoring dict."""
    if dry_run:
        return {
            "icp_score": 75,
            "persona": "founder",
            "pass": True,
            "buying_signal": "yc_backed",
            "reject_reason": None,
            "confidence": "high",
            "fit_summary": "DRY RUN",
        }

    prompt = ICP_USER_TEMPLATE.format(
        name=row.get("name", ""),
        title=row.get("title", ""),
        company=row.get("company", ""),
        industry=row.get("industry", ""),
        company_size=row.get("company_size", ""),
        location=row.get("location", ""),
        what_they_do=str(row.get("what_they_do", "") or "")[:300],
        signal_text=str(row.get("signal_text", "") or "")[:400],
        source=row.get("source", ""),
        pm_hiring_evidence=str(row.get("pm_hiring_evidence", "") or "")[:200],
        post_themes=str(row.get("post_themes", "") or "")[:150],
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=ICP_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ── CSV helpers ────────────────────────────────────────────────────────────────

def load_raw(path: Path) -> pd.DataFrame:
    if not path.exists():
        logger.error(f"Raw leads file not found: {path}")
        logger.info("Create it at: leads/raw/raw_leads.csv")
        sys.exit(1)
    df = pd.read_csv(path, low_memory=False, dtype=str).fillna("")
    logger.info(f"Loaded {len(df)} raw leads from {path}")
    return df


def append_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    df_new = pd.DataFrame(rows)
    if path.exists():
        df_new.to_csv(path, mode="a", header=False, index=False)
    else:
        df_new.to_csv(path, index=False)


def load_existing_profile_urls(path: Path) -> set:
    """Return set of profile_urls already in the output file."""
    if not path.exists():
        return set()
    df = pd.read_csv(path, low_memory=False, dtype=str).fillna("")
    return set(df["profile_url"].dropna().tolist())


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ICP Filter — hard rules + Claude scoring")
    parser.add_argument("--dry-run",  action="store_true", help="Score without writing output")
    parser.add_argument("--limit",    type=int, default=0,  help="Process only first N leads (0=all)")
    parser.add_argument("--rescore",  action="store_true",  help="Re-score leads already in qualified.csv")
    args = parser.parse_args()

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not anthropic_key and not args.dry_run:
        logger.error("ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client = Anthropic(api_key=anthropic_key) if not args.dry_run else None

    df = load_raw(RAW_PATH)
    if args.limit:
        df = df.head(args.limit)
        logger.info(f"Processing first {args.limit} leads (--limit)")

    # Skip already-processed leads unless --rescore
    if not args.rescore:
        existing_urls = load_existing_profile_urls(QUAL_PATH)
        existing_urls |= load_existing_profile_urls(REJECT_PATH)
        before = len(df)
        df = df[~df["profile_url"].isin(existing_urls)]
        skipped = before - len(df)
        if skipped:
            logger.info(f"Skipping {skipped} already-processed leads (use --rescore to override)")

    if df.empty:
        logger.info("No new leads to process.")
        return

    logger.info(f"Processing {len(df)} leads...")

    # Counters
    hard_rejected  = 0
    claude_rejected = 0
    accepted       = 0
    errors         = 0

    accepted_rows  = []
    rejected_rows  = []

    for i, (_, row) in enumerate(df.iterrows(), 1):
        lead = row.to_dict()
        name = lead.get("name") or lead.get("company") or f"row_{i}"

        # ── Stage 1: Hard Reject ──────────────────────────────────────────
        should_reject, reason = hard_reject(lead)
        if should_reject:
            hard_rejected += 1
            lead["reject_stage"]  = "hard_reject"
            lead["reject_reason"] = reason
            lead["icp_score"]     = 0
            lead["rejected_at"]   = datetime.utcnow().isoformat()
            rejected_rows.append(lead)
            logger.debug(f"  HARD REJECT [{i}] {name} — {reason}")
            continue

        # ── Stage 2: Claude ICP Score ─────────────────────────────────────
        try:
            result = score_with_claude(client, lead, dry_run=args.dry_run)

            lead["icp_score"]    = result.get("icp_score", 0)
            lead["persona"]      = result.get("persona", "")
            lead["buying_signal"] = result.get("buying_signal", "")
            lead["icp_confidence"] = result.get("confidence", "")
            lead["fit_summary"]  = result.get("fit_summary", "")
            lead["scored_at"]    = datetime.utcnow().isoformat()

            score = int(lead["icp_score"])

            if score >= SCORE_THRESHOLD and result.get("pass"):
                accepted += 1
                lead["pipeline_stage"] = "icp_passed"
                accepted_rows.append(lead)
                logger.info(
                    f"  ✅ [{i}/{len(df)}] {name} — score:{score} "
                    f"persona:{result.get('persona')} "
                    f"signal:{result.get('buying_signal')}"
                )
            else:
                claude_rejected += 1
                lead["reject_stage"]  = "claude_score"
                lead["reject_reason"] = result.get("reject_reason") or f"score:{score}"
                lead["rejected_at"]   = datetime.utcnow().isoformat()
                rejected_rows.append(lead)
                logger.info(
                    f"  ❌ [{i}/{len(df)}] {name} — score:{score} "
                    f"— {lead['reject_reason']}"
                )

        except json.JSONDecodeError as e:
            errors += 1
            logger.warning(f"  ⚠️  [{i}] {name} — Claude returned invalid JSON: {e}")
            lead["reject_stage"]  = "error"
            lead["reject_reason"] = f"json_parse_error"
            rejected_rows.append(lead)

        except Exception as e:
            errors += 1
            logger.warning(f"  ⚠️  [{i}] {name} — Claude call failed: {e}")
            lead["reject_stage"]  = "error"
            lead["reject_reason"] = str(e)[:100]
            rejected_rows.append(lead)

        # Batch save every 10 leads to avoid losing progress on crash
        if i % 10 == 0 and not args.dry_run:
            append_csv(QUAL_PATH, accepted_rows)
            append_csv(REJECT_PATH, rejected_rows)
            accepted_rows  = []
            rejected_rows  = []
            logger.info(f"  💾 Progress saved at {i}/{len(df)}")

        time.sleep(0.3)  # gentle rate limit on Anthropic

    # Save remaining
    if not args.dry_run:
        append_csv(QUAL_PATH, accepted_rows)
        append_csv(REJECT_PATH, rejected_rows)

    # ── Summary ───────────────────────────────────────────────────────────────
    total = hard_rejected + claude_rejected + accepted
    print("\n" + "=" * 55)
    print("ICP FILTER RESULTS")
    print("=" * 55)
    print(f"  Total processed   : {total}")
    print(f"  Hard rejected     : {hard_rejected:4d}  ({hard_rejected/max(total,1)*100:.0f}%)")
    print(f"  Claude rejected   : {claude_rejected:4d}  ({claude_rejected/max(total,1)*100:.0f}%)")
    print(f"  ACCEPTED (≥{SCORE_THRESHOLD})   : {accepted:4d}  ({accepted/max(total,1)*100:.0f}%)")
    if errors:
        print(f"  Errors            : {errors}")
    print("=" * 55)
    if not args.dry_run:
        print(f"  Qualified → {QUAL_PATH}")
        print(f"  Rejected  → {REJECT_PATH}")
    else:
        print("  DRY RUN — nothing written")
    print()


if __name__ == "__main__":
    main()
