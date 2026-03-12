"""
Personalization — Stage 4 of the outreach pipeline.

Reads:  leads/enriched/enriched_leads.json
Output: leads/personalized/personalized_leads.json

For each lead, Claude generates:
  - pain_point   : primary operational pain, grounded in evidence from their data
  - hook         : one specific, concrete thing about them to open with
  - relevance    : one sentence on why Mohit (fractional PM) is the right fit

Claude uses enriched profile data, post themes, company context,
and buying signals to generate specific — not generic — output.

Usage:
    python3 scripts/personalize.py
    python3 scripts/personalize.py --limit 10
    python3 scripts/personalize.py --dry-run
    python3 scripts/personalize.py --rerun       # regenerate already-done leads
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
INPUT_PATH  = ROOT / "leads" / "enriched"  / "enriched_leads.json"
OUTPUT_PATH = ROOT / "leads" / "personalized" / "personalized_leads.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a personalization engine for a freelance Project Manager's LinkedIn outreach.

PM PROFILE — Mohit:
  Role: Freelance Project Manager (Agile, Scrum, Waterfall, Hybrid, Kanban)
  Services: Fractional PM (10–20 hrs/week), Project Setup, Project Recovery, AI-assisted PM workflows
  Sweet spot: Tech startups (5–50 employees) — need PM execution but can't justify a full-time hire
  Differentiator: Available immediately, no hiring overhead, cross-project experience, AI-literate

YOUR JOB:
  For each lead, generate 3 fields grounded in actual evidence from their profile and company data.
  Do NOT invent generic pain points. Cite something specific.

FIELD DEFINITIONS:

  pain_point:
    The lead's most likely operational pain RIGHT NOW.
    Must be specific and evidence-based — reference their role, company stage, or signals.
    BAD:  "They probably need a PM."
    GOOD: "As a 3-person founding team post-seed, they're shipping product themselves
           while managing investor updates and hiring — classic PM gap."

  hook:
    One concrete, specific thing about this person/company to open a message with.
    Must be something you can SEE in the data — a post topic, a product they built,
    a milestone, a job they posted, a challenge they mentioned.
    BAD:  "You're building an interesting product."
    GOOD: "Saw you're hiring a PM at Ruvo — that role usually gets created after
           a few missed sprints."

  relevance:
    One sentence explaining why Mohit specifically is the right fit for this lead.
    Must connect THEIR pain to HIS service — not a generic pitch.
    BAD:  "Mohit can help with project management."
    GOOD: "A fractional PM covers their sprint management gap immediately — no 3-month
           hiring timeline, no equity cost, available for 10 hrs/week to start."

RULES:
  - Be direct and specific. One sentence per field is enough.
  - Never use: "synergy", "leverage", "circle back", "touch base", "passionate"
  - pain_point should feel like something the lead would nod to if they read it
  - hook must be something you can VERIFY from the data given
  - If data is sparse, say what you CAN infer from their title + company stage — don't hallucinate
"""

USER_TEMPLATE = """\
Generate personalization for this lead:

Name:                {name}
Title:               {title}
Company:             {company}
Company Size:        {company_size}
Location:            {location}
LinkedIn URL:        {linkedin_url}

Company Description: {company_description}
Industry:            {company_industry}
Funding Stage:       {funding_stage}
Hiring Engineers:    {hiring_engineers}
Careers URL:         {careers_url}

ICP Score:           {icp_score}
Persona:             {persona}
Buying Signal:       {buying_signal}
Signal Text:         {signal_text}
PM Hiring Evidence:  {pm_hiring_evidence}

Post Themes:         {post_themes}
Recent Post:         {recent_notable_post}

Existing Pain Points (if any): {inferred_pain_points}

Return ONLY this JSON — no markdown, no extra text:
{{
  "pain_point": "<specific operational pain, 1–2 sentences, evidence-based>",
  "hook":       "<one specific observable thing about them to open with>",
  "relevance":  "<one sentence connecting their pain to Mohit's fractional PM service>"
}}"""


# ── Claude call ───────────────────────────────────────────────────────────────

def personalize_lead(client: Anthropic, lead: dict) -> dict:
    """Call Claude to generate pain_point, hook, relevance for one lead."""
    prompt = USER_TEMPLATE.format(
        name=lead.get("name", ""),
        title=lead.get("title", ""),
        company=lead.get("company", ""),
        company_size=lead.get("company_size", ""),
        location=lead.get("location", ""),
        linkedin_url=lead.get("linkedin_url") or lead.get("profile_url", ""),
        company_description=str(lead.get("company_description", "") or "")[:300],
        company_industry=lead.get("company_industry") or lead.get("industry", ""),
        funding_stage=lead.get("funding_stage", ""),
        hiring_engineers=lead.get("hiring_engineers", ""),
        careers_url=lead.get("careers_url", ""),
        icp_score=lead.get("icp_score", ""),
        persona=lead.get("persona", ""),
        buying_signal=lead.get("buying_signal", ""),
        signal_text=str(lead.get("signal_text", "") or "")[:300],
        pm_hiring_evidence=str(lead.get("pm_hiring_evidence", "") or "")[:200],
        post_themes=lead.get("post_themes", ""),
        recent_notable_post=str(lead.get("recent_notable_post", "") or "")[:200],
        inferred_pain_points=str(lead.get("inferred_pain_points", "") or "")[:200],
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    result = json.loads(raw.strip())

    # Validate required fields are present and non-empty
    for field in ("pain_point", "hook", "relevance"):
        if not result.get(field):
            raise ValueError(f"Claude returned empty '{field}'")

    return result


# ── I/O helpers ───────────────────────────────────────────────────────────────

def load_input() -> list[dict]:
    if not INPUT_PATH.exists():
        logger.error(f"Input not found: {INPUT_PATH}")
        logger.info("Run scripts/enrich_leads.py first.")
        sys.exit(1)
    with open(INPUT_PATH) as f:
        return json.load(f)


def load_output() -> dict:
    """Load existing output keyed by linkedin_url."""
    if not OUTPUT_PATH.exists():
        return {}
    with open(OUTPUT_PATH) as f:
        data = json.load(f)
    return {r.get("linkedin_url", ""): r for r in data}


def save_output(results: dict) -> None:
    with open(OUTPUT_PATH, "w") as f:
        json.dump(list(results.values()), f, indent=2, default=str)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate personalization for enriched leads")
    parser.add_argument("--limit",   type=int, default=0,    help="Max leads to process (0=all)")
    parser.add_argument("--dry-run", action="store_true",    help="Print what would run without calling Claude")
    parser.add_argument("--rerun",   action="store_true",    help="Regenerate already-personalized leads")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY and not args.dry_run:
        logger.error("ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    leads   = load_input()
    results = load_output()
    logger.info(f"Loaded {len(leads)} enriched leads")
    logger.info(f"Already personalized: {len(results)}")

    # Filter to leads not yet done (unless --rerun)
    to_process = [
        lead for lead in leads
        if args.rerun or lead.get("linkedin_url", "") not in results
    ]
    if args.limit:
        to_process = to_process[:args.limit]

    logger.info(f"To personalize: {len(to_process)}")

    if not to_process:
        logger.info("All leads already personalized. Use --rerun to regenerate.")
        return

    if args.dry_run:
        print(f"\nDRY RUN — would personalize {len(to_process)} leads:")
        for lead in to_process[:10]:
            print(f"  {lead.get('name','?'):25s} | {lead.get('title',''):30s} | {lead.get('company','')}")
        return

    client  = Anthropic(api_key=ANTHROPIC_API_KEY)
    success = 0
    failed  = 0

    for i, lead in enumerate(to_process, 1):
        name = lead.get("name") or lead.get("company") or f"lead_{i}"
        url  = lead.get("linkedin_url", "")

        logger.info(f"[{i}/{len(to_process)}] {name}")

        try:
            personalization = personalize_lead(client, lead)

            # Merge into lead record
            enriched_lead = {
                **lead,
                "pain_point":       personalization["pain_point"],
                "hook":             personalization["hook"],
                "relevance":        personalization["relevance"],
                "personalized_at":  datetime.now(timezone.utc).isoformat(),
            }
            results[url] = enriched_lead
            success += 1

            logger.info(f"  pain  : {personalization['pain_point'][:80]}")
            logger.info(f"  hook  : {personalization['hook'][:80]}")
            logger.info(f"  fit   : {personalization['relevance'][:80]}")

        except json.JSONDecodeError as e:
            failed += 1
            logger.warning(f"  ❌ JSON parse error: {e}")
        except Exception as e:
            failed += 1
            logger.warning(f"  ❌ Failed: {e}")

        # Save every 10 leads
        if i % 10 == 0:
            save_output(results)
            logger.info(f"  💾 Saved progress ({i}/{len(to_process)})")

        time.sleep(0.4)

    save_output(results)

    print("\n" + "=" * 50)
    print("PERSONALIZATION COMPLETE")
    print("=" * 50)
    print(f"  Processed : {len(to_process)}")
    print(f"  Succeeded : {success}")
    print(f"  Failed    : {failed}")
    print(f"  Total     : {len(results)}")
    print(f"  Output  → {OUTPUT_PATH}")
    print()


if __name__ == "__main__":
    main()
