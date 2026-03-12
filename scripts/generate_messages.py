"""
Message Generator — Stage 5 of the outreach pipeline.

Reads:  leads/personalized/personalized_leads.json
Output: leads/messages/outreach_messages.json

Generates per lead:
  connection_request  — < 300 chars, no pitch, ends with curiosity question
  followup_1          — Day 7:  give-first, share insight, end with question
  followup_2          — Day 14: reference their product/company, soft ask
  followup_3          — Day 21: final short message, easy exit

Usage:
    python3 scripts/generate_messages.py
    python3 scripts/generate_messages.py --limit 5
    python3 scripts/generate_messages.py --dry-run
    python3 scripts/generate_messages.py --rerun
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

ROOT        = Path(__file__).parent.parent
INPUT_PATH  = ROOT / "leads" / "personalized" / "personalized_leads.json"
OUTPUT_PATH = ROOT / "leads" / "messages"      / "outreach_messages.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You write LinkedIn outreach messages for Mohit, a freelance Project Manager.

WHO MOHIT IS:
  Freelance PM — Agile, Scrum, Waterfall, Hybrid, Kanban
  Helps tech startups (5–50 people) run sprints and ship faster
  Available fractionally — no hiring overhead, starts within days

TONE RULES (non-negotiable):
  - Peer-to-peer, not vendor-to-buyer
  - Short sentences. No fluff.
  - Never mention "synergy", "leverage", "circle back", "touch base", "value-add"
  - Never use exclamation marks
  - Max 2 uses of "I" per message
  - Always end with a question — never a CTA like "Let me know if you're interested"
  - No emoji

MESSAGE RULES:

  connection_request:
    - Hard limit: 300 characters (count carefully — this will be rejected by LinkedIn if over)
    - Start with their first name
    - Reference the hook — something specific and observable about them
    - Do NOT mention Mohit's services
    - End with one short curiosity question
    - Tone: curious peer, not recruiter

  followup_1 (Day 7 — after connecting):
    - Give first: share a short insight, resource, or observation relevant to their situation
    - Do NOT pitch services yet
    - Reference the hook or pain point naturally — don't force it
    - End with a question
    - Max 60 words

  followup_2 (Day 14):
    - Reference something specific about their company or product
    - Soft ask: offer something bounded and free (a template, a 15-min call, a quick audit)
    - Frame as "something that might be useful" — not a sales pitch
    - End with a low-commitment question
    - Max 75 words

  followup_3 (Day 21 — final):
    - Acknowledge this is the last message
    - Leave the door open without pressure
    - Offer a referral out: "if timing isn't right, no worries — know anyone building fast?"
    - Max 50 words

Return ONLY valid JSON. No markdown. No explanation.
"""

USER_TEMPLATE = """\
Generate the outreach sequence for this lead.

First name:   {first_name}
Full name:    {name}
Title:        {title}
Company:      {company}
Company size: {company_size}
Location:     {location}

Pain point:   {pain_point}
Hook:         {hook}
Relevance:    {relevance}

Company description: {company_description}
Funding stage:       {funding_stage}
Buying signal:       {buying_signal}

Return ONLY this JSON:
{{
  "connection_request": "<must be under 300 characters — start with first name, end with question>",
  "followup_1":         "<Day 7 — give-first, max 60 words, end with question>",
  "followup_2":         "<Day 14 — soft ask, max 75 words, end with question>",
  "followup_3":         "<Day 21 — final, max 50 words, leave door open>"
}}"""


# ── Validation ────────────────────────────────────────────────────────────────

BANNED_WORDS = [
    "synergy", "leverage", "circle back", "touch base",
    "value-add", "passionate", "excited to connect",
    "hope this finds you", "reaching out to", "i wanted to reach",
]

def validate_messages(msgs: dict, first_name: str) -> list[str]:
    """Return list of validation errors. Empty list = pass."""
    errors = []

    cr = msgs.get("connection_request", "")

    # Connection request length
    if len(cr) > 300:
        errors.append(f"connection_request too long: {len(cr)} chars (max 300)")

    # Must start with first name
    if first_name and not cr.lower().startswith(first_name.lower()):
        errors.append(f"connection_request must start with '{first_name}'")

    # Check all messages
    all_msgs = [cr,
                msgs.get("followup_1", ""),
                msgs.get("followup_2", ""),
                msgs.get("followup_3", "")]

    for idx, msg in enumerate(all_msgs):
        label = ["connection_request", "followup_1", "followup_2", "followup_3"][idx]

        # No banned words
        msg_lower = msg.lower()
        for bw in BANNED_WORDS:
            if bw in msg_lower:
                errors.append(f"{label} contains banned phrase: '{bw}'")

        # Max 2 uses of "I"
        i_count = msg.split().count("I") + msg.count(" I ")
        if i_count > 2:
            errors.append(f"{label} uses 'I' {i_count} times (max 2)")

        # Must end with question
        stripped = msg.strip()
        if stripped and not stripped.endswith("?"):
            errors.append(f"{label} does not end with a question mark")

    return errors


# ── Claude call ───────────────────────────────────────────────────────────────

def generate_messages(client: Anthropic, lead: dict, max_retries: int = 2) -> dict:
    first_name = (lead.get("first_name") or
                  (lead.get("name") or "").split()[0])

    prompt = USER_TEMPLATE.format(
        first_name=first_name,
        name=lead.get("name", ""),
        title=lead.get("title", ""),
        company=lead.get("company", ""),
        company_size=lead.get("company_size", ""),
        location=lead.get("location", ""),
        pain_point=lead.get("pain_point", ""),
        hook=lead.get("hook", ""),
        relevance=lead.get("relevance", ""),
        company_description=str(lead.get("company_description", "") or "")[:250],
        funding_stage=lead.get("funding_stage", ""),
        buying_signal=lead.get("buying_signal", ""),
    )

    for attempt in range(1, max_retries + 1):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        msgs = json.loads(raw.strip())

        errors = validate_messages(msgs, first_name)
        if not errors:
            return msgs

        logger.warning(f"  Attempt {attempt} validation errors: {errors}")
        if attempt < max_retries:
            # Feed errors back to Claude for correction
            prompt += f"\n\nPrevious attempt failed validation:\n" + "\n".join(f"- {e}" for e in errors) + "\n\nFix these issues and return corrected JSON only."

    # Return last attempt even if validation failed — log errors
    logger.warning(f"  Returning messages with {len(errors)} unresolved validation issue(s)")
    return msgs


# ── I/O ───────────────────────────────────────────────────────────────────────

def load_input() -> list[dict]:
    if not INPUT_PATH.exists():
        logger.error(f"Input not found: {INPUT_PATH}")
        logger.info("Run scripts/personalize.py first.")
        sys.exit(1)
    with open(INPUT_PATH) as f:
        return json.load(f)


def load_output() -> dict:
    if not OUTPUT_PATH.exists():
        return {}
    with open(OUTPUT_PATH) as f:
        return {r["linkedin_url"]: r for r in json.load(f) if r.get("linkedin_url")}


def save_output(results: dict) -> None:
    with open(OUTPUT_PATH, "w") as f:
        json.dump(list(results.values()), f, indent=2, default=str)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate LinkedIn outreach messages")
    parser.add_argument("--limit",   type=int, default=0, help="Max leads to process (0=all)")
    parser.add_argument("--dry-run", action="store_true",  help="Preview without calling Claude")
    parser.add_argument("--rerun",   action="store_true",  help="Regenerate already-done leads")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY and not args.dry_run:
        logger.error("ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    leads   = load_input()
    results = load_output()
    logger.info(f"Loaded {len(leads)} personalized leads")
    logger.info(f"Already generated: {len(results)}")

    to_process = [
        lead for lead in leads
        if args.rerun or lead.get("linkedin_url", "") not in results
    ]
    if args.limit:
        to_process = to_process[:args.limit]

    logger.info(f"To generate: {len(to_process)}")

    if not to_process:
        logger.info("All leads already have messages. Use --rerun to regenerate.")
        return

    if args.dry_run:
        print(f"\nDRY RUN — would generate messages for {len(to_process)} leads:")
        for lead in to_process[:10]:
            print(f"  {lead.get('name','?'):25s} | {lead.get('company',''):20s} | hook: {lead.get('hook','')[:50]}")
        return

    client  = Anthropic(api_key=ANTHROPIC_API_KEY)
    success = 0
    failed  = 0

    for i, lead in enumerate(to_process, 1):
        name = lead.get("name") or lead.get("company") or f"lead_{i}"
        url  = lead.get("linkedin_url", "")

        logger.info(f"[{i}/{len(to_process)}] {name}")

        try:
            msgs = generate_messages(client, lead)

            cr_len = len(msgs.get("connection_request", ""))
            logger.info(f"  connection_request ({cr_len} chars): {msgs['connection_request'][:80]}...")
            logger.info(f"  followup_1: {msgs.get('followup_1','')[:70]}...")

            results[url] = {
                **lead,
                "connection_request": msgs["connection_request"],
                "followup_1":         msgs["followup_1"],
                "followup_2":         msgs["followup_2"],
                "followup_3":         msgs["followup_3"],
                "messages_generated_at": datetime.now(timezone.utc).isoformat(),
            }
            success += 1

        except json.JSONDecodeError as e:
            failed += 1
            logger.warning(f"  ❌ JSON parse error: {e}")
        except Exception as e:
            failed += 1
            logger.warning(f"  ❌ Failed: {e}")

        if i % 10 == 0:
            save_output(results)
            logger.info(f"  💾 Saved progress ({i}/{len(to_process)})")

        time.sleep(0.4)

    save_output(results)

    print("\n" + "=" * 50)
    print("MESSAGE GENERATION COMPLETE")
    print("=" * 50)
    print(f"  Processed : {len(to_process)}")
    print(f"  Succeeded : {success}")
    print(f"  Failed    : {failed}")
    print(f"  Total     : {len(results)}")
    print(f"  Output  → {OUTPUT_PATH}")
    print()

    # Print sample output for first successful lead
    if results:
        sample = next(iter(results.values()))
        sname  = sample.get("name", "?")
        print(f"── Sample: {sname} ──────────────────────────────")
        print(f"\nConnection request ({len(sample.get('connection_request',''))} chars):")
        print(f"  {sample.get('connection_request','')}")
        print(f"\nFollowup 1 (Day 7):")
        print(f"  {sample.get('followup_1','')}")
        print(f"\nFollowup 2 (Day 14):")
        print(f"  {sample.get('followup_2','')}")
        print(f"\nFollowup 3 (Day 21):")
        print(f"  {sample.get('followup_3','')}")
        print()


if __name__ == "__main__":
    main()
