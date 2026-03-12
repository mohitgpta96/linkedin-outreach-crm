"""
messages.py — Generate 6 personalized outreach messages per lead using Claude.
Reads docs/messaging-playbook.md + docs/ideal-client-profile.md before generating.
Validates each message with scripts/validate-message.sh.

Output fields:
- msg_connection_note  (<300 chars)
- msg_first_dm         (<75 words)
- msg_followup_day7
- msg_followup_day14
- msg_followup_day21
- msg_followup_day28

Each message includes [SPECIFIC: <hook>] marker for validation.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger        = logging.getLogger(__name__)
DOCS_DIR      = Path(__file__).parent.parent / "docs"
VALIDATE_SH   = Path(__file__).parent.parent / "scripts" / "validate-message.sh"
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def _load_doc(filename: str) -> str:
    path = DOCS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")[:3000]  # cap to avoid huge prompts
    return ""


def _validate_message(content: str, message_type: str) -> bool:
    """Run validate-message.sh. Returns True if pass."""
    if not VALIDATE_SH.exists():
        return True  # skip if script not found
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(f"# {message_type}\n\n")
            f.write(f"connection_note:\n{content}\n\n")
            f.write(f"[SPECIFIC: included]\n")
            fname = f.name
        result = subprocess.run([str(VALIDATE_SH), fname], capture_output=True, text=True)
        os.unlink(fname)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"[messages] Validation error: {e}")
        return True  # don't block on validation errors


def _call_claude(prompt: str) -> str:
    """Call Claude claude-sonnet-4-6 API. Returns response text."""
    if not ANTHROPIC_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set in .env")
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def generate_messages(lead: dict) -> dict:
    """
    Generate 6 outreach messages for a lead.
    Returns dict with msg_* keys.
    """
    playbook = _load_doc("messaging-playbook.md")
    icp      = _load_doc("ideal-client-profile.md")

    name         = lead.get("founder_name") or lead.get("name") or "there"
    first_name   = (lead.get("first_name") or name.split()[0]).capitalize()
    company      = lead.get("company_name") or lead.get("company") or "your company"
    headline     = lead.get("headline") or ""
    about        = lead.get("about") or lead.get("about_snippet") or ""
    what_do      = lead.get("what_they_do") or ""
    pain_pts     = lead.get("pain_points") or lead.get("inferred_pain_points") or ""
    growth       = lead.get("growth_signals") or ""
    signal_text  = lead.get("signal_text") or ""
    industry     = lead.get("industry") or "tech"
    location     = lead.get("location") or ""

    # Build enrichment context
    context = f"""
Prospect: {name} ({first_name})
Company: {company}
Headline: {headline}
About: {about}
What they do: {what_do}
Buying signal (they need PM structure): {signal_text}
Growth signals: {growth}
Pain points: {pain_pts}
Industry: {industry}
Location: {location}
""".strip()

    prompt = f"""You are an expert LinkedIn outreach copywriter for Mohit — a FREELANCE / FRACTIONAL Project Manager.

CRITICAL CONTEXT:
- Mohit is NOT looking for a full-time job. He offers FRACTIONAL PM SERVICES (part-time, contract, project-based).
- He helps founders/CTOs who are overwhelmed managing product delivery themselves.
- His pitch: "You need PM structure NOW — fractional PM is faster and cheaper than a 3-month full-time hire."
- If the prospect posted a PM job listing, that means they KNOW they need PM help → Mohit is a faster alternative.
- NEVER imply Mohit is applying for a job. He is OFFERING A SERVICE.

## Messaging Playbook (follow strictly):
{playbook}

## Ideal Client Profile:
{icp}

## Prospect Context:
{context}

## Task:
Write 6 LinkedIn messages for {first_name} at {company}. Each message must:
1. Include [SPECIFIC: <exact observation used>] at the end (required for tracking)
2. Reference something SPECIFIC about {first_name} or {company}
3. NEVER use "I" more than twice in any single message
4. Sound peer-to-peer, NOT salesy
5. Position Mohit as offering FRACTIONAL PM SERVICES — not as a job candidate

Output EXACTLY this format (no extra text):
---CONNECTION_NOTE---
(max 300 characters, must start with first name, end with curiosity question)

---FIRST_DM---
(max 75 words, give-first, ends with question)

---FOLLOWUP_DAY7---
(new angle from Day 7, max 75 words)

---FOLLOWUP_DAY14---
(reference company website/product, soft ask for 15-min chat, max 75 words)

---FOLLOWUP_DAY21---
(referral ask: "if timing isn't right, know anyone?", max 75 words)

---FOLLOWUP_DAY28---
(final breakup message, max 75 words)
"""

    raw = _call_claude(prompt)

    def _extract(marker: str, next_marker: str | None, text: str) -> str:
        start = text.find(marker)
        if start == -1:
            return ""
        start += len(marker)
        end = text.find(next_marker, start) if next_marker else len(text)
        return text[start:end].strip()

    markers = [
        "---CONNECTION_NOTE---",
        "---FIRST_DM---",
        "---FOLLOWUP_DAY7---",
        "---FOLLOWUP_DAY14---",
        "---FOLLOWUP_DAY21---",
        "---FOLLOWUP_DAY28---",
    ]

    msgs = {
        "msg_connection_note":  _extract(markers[0], markers[1], raw),
        "msg_first_dm":         _extract(markers[1], markers[2], raw),
        "msg_followup_day7":    _extract(markers[2], markers[3], raw),
        "msg_followup_day14":   _extract(markers[3], markers[4], raw),
        "msg_followup_day21":   _extract(markers[4], markers[5], raw),
        "msg_followup_day28":   _extract(markers[5], None,       raw),
    }

    # Enforce char limit on connection note
    if len(msgs["msg_connection_note"]) > 300:
        note = msgs["msg_connection_note"]
        cut  = max(note[:300].rfind("?"), note[:300].rfind("."))
        msgs["msg_connection_note"] = note[:cut+1] if cut > 50 else note[:297] + "..."

    # Validate (log warnings but don't block)
    for key, text in msgs.items():
        if text and not _validate_message(text, key):
            logger.warning(f"[messages] {key} failed validation for {name}")

    return msgs
