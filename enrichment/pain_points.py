"""
Enrichment Phase 2D: Pain Point Inference + Message Generation
Takes all collected data and infers:
1. What problems this company likely faces (inferred_pain_points)
2. How Mohit as a PM specifically helps them (pm_value_prop)
3. 5 personalized outreach messages (expert-optimized per all frameworks)
4. Quality score (0–100)
5. Lead temperature (Hot / Warm / Cold)
"""

import re
import logging
from datetime import datetime, date
from typing import Optional

from config import (
    QUALITY_SCORE_HOT,
    QUALITY_SCORE_WARM,
    HOT_DAYS,
    WARM_DAYS,
)

logger = logging.getLogger(__name__)


# ─── Quality Score ────────────────────────────────────────────────────────────

def _calculate_quality_score(lead: dict) -> int:
    score = 0
    title = (lead.get("title") or "").lower()

    # +30: Founder/CEO/CTO title
    if any(t in title for t in ["founder", "ceo", "cto", "chief"]):
        score += 30

    # +20: Small company (< 100 employees)
    size_raw = lead.get("company_size") or lead.get("company_size_raw") or ""
    size_match = re.search(r"(\d+)", str(size_raw))
    if size_match and int(size_match.group(1)) < 100:
        score += 20
    elif not size_raw:
        score += 10  # unknown = assume small (startup)

    # +20: Signal < 7 days old
    days = _days_since_signal(lead.get("signal_date") or lead.get("trigger_date") or "")
    if days is not None and days < 7:
        score += 20
    elif days is not None and days < 30:
        score += 10

    # +15: Multiple sources confirm same person
    if lead.get("source_count", 1) > 1:
        score += 15

    # +10: SaaS/tech/IT industry
    industry = (lead.get("industry") or "").lower()
    what = (lead.get("what_they_do") or "").lower()
    if any(kw in industry or kw in what for kw in ["saas", "software", "tech", "it service", "startup"]):
        score += 10

    # +5: Contact info found
    if lead.get("profile_url") or lead.get("company_website"):
        score += 5

    return min(score, 100)


def _days_since_signal(date_str: str) -> Optional[int]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            signal_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            return (date.today() - signal_date).days
        except ValueError:
            continue
    return None


def _lead_temperature(lead: dict) -> str:
    days = _days_since_signal(lead.get("signal_date") or lead.get("trigger_date") or "")
    if days is None:
        return "Unknown"
    if days < HOT_DAYS:
        return "Hot"
    if days < WARM_DAYS:
        return "Warm"
    return "Cold"


# ─── Pain Point Inference ─────────────────────────────────────────────────────

def _infer_pain_points(lead: dict) -> str:
    points = []
    title        = (lead.get("title") or "").lower()
    signal_text  = (lead.get("signal_text") or "").lower()
    about        = (lead.get("about_snippet") or "").lower()
    post_themes  = (lead.get("post_themes") or "").lower()
    post_text    = (lead.get("recent_notable_post") or "").lower()
    size         = lead.get("company_size") or lead.get("company_size_raw") or ""
    what_they_do = (lead.get("what_they_do") or "").lower()

    all_text = " ".join([signal_text, about, post_themes, post_text])

    # No dedicated PM
    if any(kw in all_text for kw in ["no pm", "no project manager", "need a pm", "need a project manager"]):
        points.append("No dedicated PM — founder is managing product + ops simultaneously")
    elif "founder" in title or "ceo" in title:
        points.append("Founder/CEO likely juggling product decisions, hiring, and operations without a PM")

    # Engineering team pulling into product
    if any(kw in all_text for kw in ["engineer", "dev", "technical", "cto"]):
        points.append("Engineering team being pulled into product decisions instead of shipping")

    # Scaling chaos
    size_match = re.search(r"(\d+)", str(size))
    size_num = int(size_match.group(1)) if size_match else 0
    if 10 <= size_num <= 60:
        points.append(f"Growing team (~{size_num} people) with increasing coordination complexity")
    elif not size_num:
        points.append("Early-stage team where processes likely haven't been formalized yet")

    # Sprint/delivery issues mentioned explicitly
    if any(kw in all_text for kw in ["sprint", "deadline", "delivery", "chaos", "overwhelm"]):
        points.append("Sprint process or delivery cadence breaking down under growth pressure")

    # Roadmap clarity
    if any(kw in all_text for kw in ["roadmap", "priorities", "prioritiz"]):
        points.append("Unclear product roadmap — too many ideas competing for limited engineering time")

    return " | ".join(points[:4]) if points else "Standard startup scaling challenges — no dedicated PM"


def _build_value_prop(lead: dict) -> str:
    props = []
    signal_text  = (lead.get("signal_text") or "").lower()
    post_text    = (lead.get("recent_notable_post") or "").lower()
    what_they_do = lead.get("what_they_do") or ""
    company      = lead.get("company") or "your company"
    first_name   = lead.get("first_name") or "them"

    all_text = signal_text + " " + post_text

    if any(kw in all_text for kw in ["roadmap", "priorit"]):
        props.append(f"Own the product roadmap → free {first_name} to focus on fundraising + customers")

    if any(kw in all_text for kw in ["sprint", "delivery", "deadline", "ship"]):
        props.append(f"Fix sprint process at {company} → predictable delivery instead of last-minute chaos")

    if any(kw in all_text for kw in ["engineer", "technical"]):
        props.append("Be the bridge between engineering and business — shield engineers from scope creep")

    if any(kw in all_text for kw in ["hir", "onboard", "scal"]):
        props.append("Run hiring coordination + PM onboarding as team scales past 20 people")

    if what_they_do:
        props.append(f"Bring external PM perspective on {what_they_do[:60]}...")

    return " | ".join(props[:3]) if props else (
        f"Own the roadmap, run sprints, and shield {first_name} from operational chaos"
    )


# ─── Message Generation (Expert-Optimized) ───────────────────────────────────

def _word_count(text: str) -> int:
    return len(text.split())


def _generate_messages(lead: dict) -> dict:
    """
    Generate 5 messages per expert frameworks:
    - Will Allred: < 75 words, more You than I
    - Josh Braun: end with curiosity question
    - Justin Welsh: give first (observation before ask)
    - Aaron Ross: referral variant on Day 17
    - Lemlist: 5-touch sequence (Day 0, 4, 10, 17, 25)
    """
    first_name   = lead.get("first_name") or "there"
    company      = lead.get("company") or "your company"
    signal_text  = (lead.get("signal_text") or "")[:200]
    notable_post = (lead.get("recent_notable_post") or "")[:150]
    what_they_do = (lead.get("what_they_do") or f"what you're building at {company}")[:100]
    pain_points  = lead.get("inferred_pain_points") or ""
    source       = lead.get("source") or ""

    # Personalized context (what triggered this lead)
    if "post" in source or lead.get("signal_type") == "post":
        trigger_ref = f'your post about "{signal_text[:80].strip()}"' if signal_text else "your recent post"
    elif "funding" in (lead.get("signal_type") or ""):
        funding = lead.get("funding_amount") or lead.get("funding_stage") or "recent funding"
        trigger_ref = f"your {funding} round"
    else:
        trigger_ref = f"the PM role at {company}"

    pain_hook = ""
    if "roadmap" in pain_points.lower():
        pain_hook = "roadmap ownership across your team"
    elif "sprint" in pain_points.lower() or "delivery" in pain_points.lower():
        pain_hook = "the delivery process as your team scales"
    elif "engineer" in pain_points.lower():
        pain_hook = "keeping your engineers focused on building (not managing)"
    else:
        pain_hook = "how you're managing product priorities right now"

    # Use company name + what they do for a natural observation
    if what_they_do and not what_they_do.lower().startswith(company.lower()):
        product_obs = f"{company} — {what_they_do[:70].rstrip('. ')} — is solving a real problem."
    elif what_they_do:
        product_obs = f"{what_they_do[:80].rstrip('. ')} — genuinely solving a real problem."
    else:
        product_obs = f"What you're building at {company} is solving a real problem."

    # ── CONNECTION REQUEST NOTE (~40 words, starts with THEM) ──
    connection_note = (
        f"{first_name}, saw {trigger_ref}. "
        f"{product_obs} "
        f"How are you currently thinking about {pain_hook}?"
    )
    # Trim to < 300 chars for connection note
    if len(connection_note) > 290:
        connection_note = (
            f"{first_name}, saw {trigger_ref}. "
            f"How are you thinking about {pain_hook}?"
        )

    # ── FIRST DM — Day 0 (~60 words, give-first) ──
    what_snippet = what_they_do[:70].strip().rstrip(".") if what_they_do else f"what you're building at {company}"
    first_dm = (
        f"{first_name}, spent time on {company} — {what_snippet}. "
        f"Really interesting problem space. "
        f"Curious: {pain_hook}?"
    )

    # ── FOLLOW-UP #1 — Day 4 (new angle) ──
    followup_1 = (
        f"{first_name}, no pressure — just saw your latest post about "
        f"{notable_post[:50].strip() or 'delivery speed'}. "
        f"What does your current process look like? Happy to share what's worked for similar-stage teams."
    )

    # ── FOLLOW-UP #2 — Day 10 (website reference) ──
    followup_2 = (
        f"{first_name}, one more thought: {company}'s mission is around "
        f"{what_they_do[:60].strip() or 'solving a real problem'} — "
        f"yet that's exactly what your internal team is navigating right now. "
        f"Still open to a quick 15-min call?"
    )

    # ── FOLLOW-UP #3 — Day 17 (referral / low pressure — Aaron Ross) ──
    followup_3 = (
        f"{first_name}, if the PM role is still open and timing isn't right, "
        f"would you know someone else hiring in a similar space? "
        f"Either way, rooting for {company}."
    )

    # ── FOLLOW-UP #4 — Day 25 (breakup) ──
    followup_4 = (
        f"{first_name}, last one from me — I'll leave the door open. "
        f"Loved what you're building at {company}."
    )

    return {
        "msg_connection_note":  connection_note,
        "msg_first_dm":         first_dm,
        "msg_followup_day4":    followup_1,
        "msg_followup_day10":   followup_2,
        "msg_followup_day17":   followup_3,
        "msg_followup_day25":   followup_4,
        "msg_word_count_note":  _word_count(connection_note),
        "msg_word_count_dm":    _word_count(first_dm),
    }


# ─── Main Enrichment Function ─────────────────────────────────────────────────

def enrich_with_pain_points(leads: list[dict]) -> list[dict]:
    """
    Final enrichment pass: add quality score, temperature, pain points,
    value prop, and all 5 generated messages.
    """
    for lead in leads:
        lead["inferred_pain_points"] = _infer_pain_points(lead)
        lead["pm_value_prop"]        = _build_value_prop(lead)
        lead["quality_score"]        = _calculate_quality_score(lead)
        lead["lead_temperature"]     = _lead_temperature(lead)

        # Suggested opener = connection note
        messages = _generate_messages(lead)
        lead.update(messages)
        lead["suggested_opener"] = messages["msg_connection_note"]

        # Warm-up status default
        if not lead.get("warm_up_status"):
            lead["warm_up_status"] = "Not started"
        if not lead.get("outreach_status"):
            lead["outreach_status"] = "Not contacted"
        if not lead.get("pipeline_stage"):
            lead["pipeline_stage"] = "Found"
        if not lead.get("verified"):
            lead["verified"] = ""
        if not lead.get("notes"):
            lead["notes"] = ""

    # Sort by quality score descending
    leads.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    logger.info(f"[Pain Points] Enriched {len(leads)} leads with pain points + messages.")
    return leads
