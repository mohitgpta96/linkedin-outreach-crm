"""
Lead Qualification Engine — Claude-powered ICP scoring.

Can be used two ways:

  1. As a module in the pipeline:
       from scripts.qualify_lead import qualify_lead
       result = qualify_lead({"name": "...", "title": "...", ...})

  2. As a standalone CLI:
       python3 scripts/qualify_lead.py --lead '{"name":"Karim","title":"CEO","company":"Metorial",...}'
       python3 scripts/qualify_lead.py --file leads/raw/raw_leads.csv --limit 10

Output schema per lead:
  {
    "score":         int (0–100),
    "accepted":      bool,
    "reason":        str,
    "persona_match": str,
    "buying_signal": str,
    "confidence":    str,
    "gate":          str   (which gate stopped it, if rejected)
  }
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SCORE_THRESHOLD   = 70


# ── Gate 1: Hard Rules (no API cost) ─────────────────────────────────────────

# Titles that are ALWAYS accepted — checked first, bypass reject list entirely.
# Use full-word / prefix matching so "Head of Engineering" is never rejected
# even though "engineer" appears in the reject list.
_ALLOW_TITLES = [
    "founder",
    "co-founder",
    "cofounder",
    "technical co-founder",
    "technical cofounder",
    "ceo",
    "chief executive",
    "cto",
    "chief technology",
    "chief technical",
    "vp engineering",
    "vp of engineering",
    "vice president engineering",
    "head of engineering",
    "head of product",
    "director of engineering",
    "engineering director",
    "engineering manager",
    "director of product",
    "general manager",
    "managing director",
    "president",
]

# Titles that disqualify — checked only if title is NOT in the allow-list above.
_REJECT_TITLE_KEYWORDS = [
    "recruiter",
    "talent",           # talent acquisition, talent partner, talent manager
    "hr manager",
    "human resources",
    "people ops",
    "chief people",
    "marketing specialist",
    "marketing manager",
    "growth hacker",
    "seo",
    "content writer",
    "brand manager",
    "social media",
    "sales rep",
    "account executive",
    "account manager",
    "bdr",
    "sdr",
    "designer",         # ux designer, ui designer, graphic designer, product designer
    "software engineer",
    "frontend developer",
    "frontend engineer",
    "backend developer",
    "backend engineer",
    "full stack",
    "mobile engineer",
    "mobile developer",
    "qa engineer",
    "devops",
    "site reliability",
    "data scientist",
    "data analyst",
    "data engineer",
    "accountant",
    "finance manager",
    "legal counsel",
    "lawyer",
    "intern",
    "student",
]

# Industries that are never a fit
_REJECT_INDUSTRIES = {
    "staffing", "outsourcing", "body shop", "manpower",
    "recruitment agency", "headhunting", "executive search",
    "digital marketing agency", "seo agency", "advertising agency",
    "pr agency", "media agency",
    "web3", "crypto", "nft", "defi", "dao", "blockchain protocol",
    "gambling", "casino", "sports betting",
    "adult content", "adult entertainment",
}

# Company name patterns that signal agencies / outsourcing shops
_REJECT_COMPANY_PATTERNS = [
    "solutions pvt", "consultants pvt", "outsourcing pvt", "services pvt",
    "staffing solutions", "manpower solutions", "talent solutions",
    "it services", "it consulting", "consulting llp",
]

MAX_EMPLOYEES = 200
MIN_EMPLOYEES = 2


def _hard_gate(lead: dict):
    """
    Returns a rejection result dict if the lead fails hard rules.
    Returns None if the lead passes (proceed to Claude scoring).
    """
    title    = str(lead.get("title", "")    or "").lower().strip()
    industry = str(lead.get("industry", "") or "").lower().strip()
    company  = str(lead.get("company", "")  or "").lower().strip()
    name     = str(lead.get("name", "")     or "").strip()
    url      = str(lead.get("linkedin_url", "") or lead.get("profile_url", "") or "").strip()
    what     = str(lead.get("what_they_do", "") or "").lower().strip()

    # 1. Missing required fields
    if not url:
        return _reject("no_linkedin_url", "No LinkedIn URL — cannot reach this lead", "none")
    if not name and not company:
        return _reject("no_identity", "Neither name nor company present", "none")
    if not company:
        return _reject("no_company", "No company name — cannot assess fit", "none")

    # 2. Title check — allow-list first, then reject-list
    # Step A: if title matches allow-list → skip reject check entirely
    title_allowed = any(allowed in title for allowed in _ALLOW_TITLES)

    # Step B: if not allowed → check reject keywords
    if not title_allowed:
        for kw in _REJECT_TITLE_KEYWORDS:
            if kw in title:
                return _reject(
                    "title_not_decision_maker",
                    f"Title '{lead.get('title')}' is not a buying decision maker",
                    "none",
                )

    # 3. Industry disqualifies
    combined = f"{industry} {what} {company}"
    for bad_ind in _REJECT_INDUSTRIES:
        if bad_ind in combined:
            return _reject(
                "industry_disqualified",
                f"Industry '{bad_ind}' is never a fit for freelance PM services",
                "none",
            )

    # 4. Company name suggests agency/outsourcing
    for pattern in _REJECT_COMPANY_PATTERNS:
        if pattern in company:
            return _reject(
                "company_type_disqualified",
                f"Company name suggests outsourcing/agency: '{lead.get('company')}'",
                "none",
            )

    # 5. Company too large
    size_raw = str(lead.get("company_size", "") or "").strip()
    if size_raw:
        try:
            upper = int(size_raw.split("-")[-1]) if "-" in size_raw else int(float(size_raw))
            if upper > MAX_EMPLOYEES:
                return _reject(
                    "company_too_large",
                    f"Company has {size_raw} employees — too large for fractional PM pitch",
                    "none",
                )
            if upper < MIN_EMPLOYEES:
                return _reject(
                    "company_too_small",
                    f"Company has {size_raw} employees — too early/small",
                    "none",
                )
        except ValueError:
            pass  # unparseable — let Claude decide

    return None  # passed all hard gates


def _reject(gate: str, reason: str, persona: str) -> dict:
    return {
        "score":         0,
        "accepted":      False,
        "reason":        reason,
        "persona_match": persona,
        "buying_signal": "none",
        "confidence":    "high",
        "gate":          gate,
    }


# ── Gate 2: Claude ICP Score ──────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a strict ICP (Ideal Client Profile) scoring engine for a freelance Project Manager.

PM PROFILE:
  Name: Mohit
  Role: Freelance Project Manager (Agile, Scrum, Waterfall, Hybrid, Kanban)
  Services: Fractional PM, Project Setup & Structure, Project Recovery/Audit, AI-assisted PM workflows
  Sweet spot: Tech startups (5–50 employees) that need PM execution but cannot justify a full-time hire
  Rate: $30–60/hr or $500–2000 fixed projects

TARGET PERSONAS (in priority order):

  PERSONA A — Founder/CEO/Co-Founder (HIGHEST VALUE)
    Stage: seed to Series B
    Size:  3–50 employees
    Pain:  Playing PM themselves. Missing deadlines. Context-switching. Burning out.
    Score: Max 100 if founder + tech startup + 5–50 employees + any buying signal

  PERSONA B — CTO / VP Engineering / Head of Engineering
    Stage: Series A to Series C
    Size:  10–100 engineers
    Pain:  Hiring devs but nobody managing delivery. Sprints chaotic.
    Score: Max 90

  PERSONA C — Engineering Manager / Director of Engineering
    Stage: Any startup to mid-size
    Pain:  Spending 60%+ of time in process work instead of engineering leadership.
    Score: Max 80

  PERSONA D — Technical PM / Program Manager (low priority)
    Stage: Mid-size to large
    Pain:  Too many workstreams, needs extra PM bandwidth.
    Score: Max 65 (often too large or too structured)

ACCEPT:
  Industries: SaaS, FinTech, HealthTech, DevTools, EdTech, AI/ML startups,
              E-commerce tech, PropTech, Infrastructure tech, CleanTech
  Locations: India, USA, UK, Germany, UAE, Singapore, Canada, Australia
  Size: 3–100 employees (ideal 5–50)
  Funding: bootstrapped, pre-seed, seed, series A, series B

REJECT:
  Score 0–30: Non-tech, large enterprise, staffing, agency, crypto
  Score 31–50: Tech but too large (100–200 emp), or no buying signal at all
  Score 51–69: Possible fit but missing key data or weak signal

BUYING SIGNALS (increase score significantly):
  +25 pts: PM/Scrum Master/Project Manager job posted (pm_hiring_evidence or signal_text)
  +20 pts: Recent funding round announced (within 6 months)
  +15 pts: YC-backed (source contains YC or ycombinator)
  +10 pts: Team growing fast (signal_text mentions hiring, scaling)
  +5  pts: Active LinkedIn poster (post_themes or recent_notable_post not empty)

SCORING RUBRIC:
  90–100: Perfect fit. Founder/CEO, 5–50 employees, tech, has PM hiring signal.
  75–89:  Strong fit. Right persona, right size, some buying signal.
  70–74:  Acceptable. Right persona but weak/no signal, or secondary persona with signal.
  50–69:  Weak fit. Too large, or wrong persona, or no signal.
  0–49:   Reject. Wrong industry, no buying signal, or disqualifying factors.

Be STRICT. Only score ≥70 leads that Mohit should genuinely reach out to.
A score of 70 means: worth a connection request, not just a maybe.

Return ONLY valid JSON. No markdown. No explanation outside the JSON.
"""

_USER_TEMPLATE = """\
Score this lead:

Name:          {name}
Title:         {title}
Company:       {company}
Industry:      {industry}
Company Size:  {company_size}
Location:      {location}
LinkedIn URL:  {linkedin_url}
What They Do:  {what_they_do}
Signal Text:   {signal_text}
Source:        {source}
PM Evidence:   {pm_hiring_evidence}
Post Themes:   {post_themes}

Return ONLY this JSON:
{{
  "score":         <integer 0–100>,
  "accepted":      <true if score >= 70 else false>,
  "reason":        "<one clear sentence explaining the score — cite specific evidence>",
  "persona_match": "<founder|cto|eng_manager|tpm|none>",
  "buying_signal": "<pm_job|funding|yc_backed|growing|active_poster|none>",
  "confidence":    "<high|medium|low>",
  "gate":          "claude_score"
}}"""


def _claude_score(client: Anthropic, lead: dict) -> dict:
    """Call Claude to score a lead. Returns scoring dict."""
    prompt = _USER_TEMPLATE.format(
        name=lead.get("name", ""),
        title=lead.get("title", ""),
        company=lead.get("company", ""),
        industry=lead.get("industry", ""),
        company_size=lead.get("company_size", ""),
        location=lead.get("location", ""),
        linkedin_url=lead.get("linkedin_url") or lead.get("profile_url", ""),
        what_they_do=str(lead.get("what_they_do", "") or "")[:300],
        signal_text=str(lead.get("signal_text", "") or "")[:400],
        source=lead.get("source", ""),
        pm_hiring_evidence=str(lead.get("pm_hiring_evidence", "") or "")[:200],
        post_themes=str(lead.get("post_themes", "") or "")[:150],
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=350,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)
    result.setdefault("gate", "claude_score")
    return result


# ── Public API ────────────────────────────────────────────────────────────────

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def qualify_lead(lead: dict, client=None) -> dict:
    """
    Score a single lead.

    Args:
        lead:   dict with fields: name, title, company, industry,
                company_size, location, linkedin_url (or profile_url),
                and optionally: what_they_do, signal_text, source,
                pm_hiring_evidence, post_themes
        client: optional Anthropic client (reuse for batch calls)

    Returns:
        {
          "score":         int,
          "accepted":      bool,
          "reason":        str,
          "persona_match": str,
          "buying_signal": str,
          "confidence":    str,
          "gate":          str
        }
    """
    # Gate 1: hard rules (free)
    hard_result = _hard_gate(lead)
    if hard_result:
        return hard_result

    # Gate 2: Claude scoring (Anthropic API)
    c = client or _get_client()
    return _claude_score(c, lead)


def qualify_batch(leads: list[dict]) -> list[dict]:
    """Score a list of leads. Reuses one Anthropic client for efficiency."""
    c = _get_client()
    results = []
    for lead in leads:
        result = qualify_lead(lead, client=c)
        result["_input"] = lead
        results.append(result)
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Score a lead for ICP fit")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lead",  type=str, help="JSON string of a single lead")
    group.add_argument("--file",  type=str, help="Path to a CSV of leads")
    parser.add_argument("--limit", type=int, default=0, help="Limit rows from --file (0=all)")
    args = parser.parse_args()

    if args.lead:
        lead   = json.loads(args.lead)
        result = qualify_lead(lead)
        print(json.dumps(result, indent=2))
        return

    # CSV mode
    import pandas as pd
    path = Path(args.file)
    if not path.exists():
        logger.error(f"File not found: {path}")
        sys.exit(1)

    df = pd.read_csv(path, low_memory=False, dtype=str).fillna("")
    if args.limit:
        df = df.head(args.limit)

    c = _get_client()
    accepted, rejected = [], []

    for i, (_, row) in enumerate(df.iterrows(), 1):
        lead   = row.to_dict()
        result = qualify_lead(lead, client=c)
        name   = lead.get("name") or lead.get("company") or f"row_{i}"

        if result["accepted"]:
            accepted.append({**lead, **result})
            print(f"  ✅ [{i}] {name:30s} score:{result['score']:3d}  {result['persona_match']}  {result['buying_signal']}")
        else:
            rejected.append({**lead, **result})
            print(f"  ❌ [{i}] {name:30s} score:{result['score']:3d}  {result['reason'][:60]}")

    print(f"\nAccepted: {len(accepted)} / {len(df)}")
    print(f"Rejected: {len(rejected)} / {len(df)}")


if __name__ == "__main__":
    _cli()
