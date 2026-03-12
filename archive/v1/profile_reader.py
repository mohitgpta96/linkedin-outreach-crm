"""
Profile Reader — FREE APIs ONLY. No web scraping.

APIs used:
  1. Apollo.io API    — People Enrichment by LinkedIn URL (75 free credits/month)
  2. HN Algolia API   — "Show HN / Launch HN" posts, founder comments (free, no auth)
  3. GitHub API       — founder bio/activity (60/hr no auth, 5000/hr with GITHUB_TOKEN)
  4. Existing CSV     — what_they_do, growth_signals, pm_job_title, industry (always available)
"""

import logging
import os
import re
import time
import random
import requests
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).parent / ".env")
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")

NOTE_LIMIT = 295


# ── 1. Apollo.io People Enrichment API ───────────────────────────────────────
def apollo_enrich(profile_url: str) -> dict:
    """
    Enrich a person by LinkedIn URL using Apollo.io People Enrichment.
    Uses 1 credit per successful match.
    Free plan: 75 credits/month.
    https://apolloio.github.io/apollo-api-docs/?shell#people-enrichment
    """
    result = {"apollo_headline": "", "apollo_bio": "", "apollo_city": ""}
    if not APOLLO_API_KEY or not profile_url:
        return result

    try:
        r = requests.post(
            "https://api.apollo.io/api/v1/people/match",
            headers={
                "Content-Type":  "application/json",
                "Cache-Control": "no-cache",
                "X-Api-Key":     APOLLO_API_KEY,
            },
            json={
                "linkedin_url":     profile_url,
                "reveal_personal_emails": False,
                "reveal_phone_number":    False,
            },
            timeout=10,
        )
        if r.status_code != 200:
            return result

        person = r.json().get("person") or {}
        headline = (person.get("headline") or "").strip()
        bio      = (person.get("summary")  or "").strip()
        city     = (person.get("city")     or "").strip()
        org      = (person.get("organization") or {})
        org_desc = (org.get("short_description") or "").strip()

        result["apollo_headline"] = headline[:150] if headline else ""
        result["apollo_bio"]      = (bio or org_desc)[:200]
        result["apollo_city"]     = city
    except Exception as e:
        logger.warning(f"[enrichment] Apollo.io error: {e}")
    return result


# ── 2. HN Algolia API ─────────────────────────────────────────────────────────
def hn_search(name: str, company: str) -> dict:
    """
    Search HN for:
    - "Show HN: {company}" or "Launch HN: {company} (YC ...)" — founder's own launch post
    - Comments by or about the founder/company
    Free, no auth. https://hn.algolia.com/api/v1/search
    """
    result = {"hn_launch_title": "", "hn_launch_url": "", "hn_comment": ""}

    queries = [
        f"Show HN {company}",
        f"Launch HN {company}",
        f"{company} YC",
        f'"{name}"',
    ]

    for q in queries:
        try:
            r = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": q, "tags": "story", "hitsPerPage": 5},
                timeout=6,
            )
            if r.status_code != 200:
                continue

            for hit in r.json().get("hits", []):
                title = hit.get("title", "")
                url   = hit.get("url", "")
                # Must be clearly about this company
                if company.lower() in title.lower() or company.lower() in (url or "").lower():
                    result["hn_launch_title"] = title[:120]
                    result["hn_launch_url"]   = url
                    break

            if result["hn_launch_title"]:
                break
        except Exception as e:
            logger.warning(f"[enrichment] HN story search error: {e}")
        time.sleep(random.uniform(0.2, 0.4))

    # Also look for founder comments
    if not result["hn_comment"]:
        try:
            r = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": f"{name} {company}", "tags": "comment", "hitsPerPage": 3},
                timeout=6,
            )
            if r.status_code == 200:
                for hit in r.json().get("hits", []):
                    text = re.sub(r"<[^>]+>", "", hit.get("comment_text", "")).strip()
                    if len(text) > 60 and company.lower() in text.lower():
                        result["hn_comment"] = text[:200]
                        break
        except Exception as e:
            logger.warning(f"[enrichment] HN comment search error: {e}")

    return result


# ── 2. GitHub API ─────────────────────────────────────────────────────────────
def github_search(name: str, company: str) -> dict:
    """Search GitHub for founder profile — bio, company field."""
    result = {"github_bio": ""}
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    parts = name.lower().split()
    query = f"{' '.join(parts)} {company} type:user"
    try:
        r = requests.get(
            "https://api.github.com/search/users",
            params={"q": query, "per_page": 3},
            headers=headers, timeout=6,
        )
        if r.status_code != 200:
            return result

        for user in r.json().get("items", []):
            r2 = requests.get(
                f"https://api.github.com/users/{user['login']}",
                headers=headers, timeout=6,
            )
            if r2.status_code != 200:
                continue
            p   = r2.json()
            bio = (p.get("bio") or "").strip()
            co  = (p.get("company") or "").strip()
            full_name = (p.get("name") or "").lower()
            last = parts[-1] if parts else ""
            if last and last in full_name and bio:
                result["github_bio"] = f"{bio} ({co})" if co else bio
                result["github_bio"] = result["github_bio"][:200]
                break
    except Exception as e:
        logger.warning(f"[enrichment] GitHub search error: {e}")
    return result


# ── Master enricher ───────────────────────────────────────────────────────────
def enrich_lead_for_note(lead: dict) -> dict:
    """Enrich lead using free APIs. Returns merged dict."""
    name        = str(lead.get("name", ""))
    company     = str(lead.get("company", ""))
    profile_url = str(lead.get("profile_url", ""))
    enriched    = dict(lead)

    if APOLLO_API_KEY and profile_url.startswith("https://www.linkedin.com/in/"):
        print(f"    🚀 Apollo.io enrichment...")
        enriched.update(apollo_enrich(profile_url))
        time.sleep(random.uniform(0.3, 0.6))

    print(f"    🟠 HN Algolia API...")
    enriched.update(hn_search(name, company))

    print(f"    🐙 GitHub API...")
    enriched.update(github_search(name, company))

    return enriched


# ── Note Generator ────────────────────────────────────────────────────────────
def generate_note(lead: dict) -> str:
    """
    Generate personalized connection note.
    Priority: HN launch post > HN comment > GitHub bio >
              PM job title > growth signal > what_they_do > industry fallback
    """
    first    = str(lead.get("first_name") or lead.get("name", "")).split()[0]
    company  = str(lead.get("company", ""))
    industry = str(lead.get("industry", "nan")).replace("nan", "")
    pm_title = str(lead.get("pm_job_title", "nan")).replace("nan", "")
    growth   = str(lead.get("growth_signals", "nan")).replace("nan", "")
    what_do  = str(lead.get("what_they_do", "nan")).replace("nan", "")

    hn_launch    = str(lead.get("hn_launch_title", "")).strip()
    hn_comment   = str(lead.get("hn_comment", "")).strip()
    gh_bio       = str(lead.get("github_bio", "")).strip()
    apollo_hl    = str(lead.get("apollo_headline", "")).strip()
    apollo_bio   = str(lead.get("apollo_bio", "")).strip()

    note = ""

    # 1. HN launch / show post — most specific
    if hn_launch and len(hn_launch) > 10:
        # Clean "Show HN: / Launch HN:" prefix
        clean = re.sub(r"^(Show HN|Launch HN)\s*:\s*", "", hn_launch, flags=re.I).strip()
        note = (
            f"{first} — saw your \"{clean[:65]}\" post on HN. "
            f"What's the product challenge {company} is solving right now?"
        )

    # 2. HN comment by founder
    elif hn_comment and len(hn_comment) > 40:
        snippet = hn_comment[:55].strip()
        note = (
            f"{first} — your HN comment \"{snippet}...\" stood out. "
            f"What's the product insight driving {company}?"
        )

    # 3. GitHub bio (specific)
    elif gh_bio and len(gh_bio) > 20:
        note = (
            f"{first} — saw your GitHub: \"{gh_bio[:65]}\". "
            f"What's the biggest product bet {company} is making?"
        )

    # 3.5 Apollo headline/bio
    elif apollo_hl and len(apollo_hl) > 20:
        note = (
            f"{first} — {apollo_hl[:80]}. "
            f"What's the biggest product bet {company} is making?"
        )
    elif apollo_bio and len(apollo_bio) > 30:
        note = (
            f"{first} — {apollo_bio[:80]}. "
            f"Curious what product challenge {company} is most focused on?"
        )

    # 4. PM job title from CSV
    elif pm_title and len(pm_title) > 3:
        role = pm_title.replace("Product Manager", "PM").replace("product manager", "PM")[:40]
        note = (
            f"{first} — saw {company} is hiring for {role}. "
            f"What product challenge is driving this hire?"
        )

    # 5. Growth signal from CSV
    elif growth and len(growth) > 20:
        note = (
            f"{first} — noticed {growth[:65].lower()}. "
            f"What's the biggest product bet {company} is making right now?"
        )

    # 6. What they do from CSV
    elif what_do and len(what_do) > 20:
        note = (
            f"{first} — {what_do[:70]}. "
            f"Curious what product area is taking most of your bandwidth?"
        )

    # 7. Industry fallback
    else:
        ind = industry.split(",")[0].strip()[:30] if industry else "tech"
        note = (
            f"{first} — love what {company} is building in {ind.lower()}. "
            f"What's the product challenge you're most focused on?"
        )

    # Enforce char limit
    note = note.strip()
    if len(note) > NOTE_LIMIT:
        cut = max(note[:NOTE_LIMIT].rfind("?"), note[:NOTE_LIMIT].rfind("."))
        note = note[:cut + 1] if cut > 80 else note[:NOTE_LIMIT - 3] + "..."

    return note


if __name__ == "__main__":
    # Test with a YC company (likely on HN) and an India company
    for test in [
        {"name": "Max Brodeur Urbas", "first_name": "Max", "company": "Gumloop",
         "industry": "AI Automation", "pm_job_title": "Product Manager",
         "growth_signals": "YC W24, AI automation platform, hiring PM"},
        {"name": "Akshay Mehrotra", "first_name": "Akshay", "company": "EarlySalary",
         "industry": "Fintech / Lending", "pm_job_title": "Product Manager",
         "growth_signals": "India fintech Series C — building credit products, needs PM"},
    ]:
        print(f"\n--- {test['name']} / {test['company']} ---")
        enriched = enrich_lead_for_note(test)
        note = generate_note(enriched)
        print(f"HN launch: {enriched.get('hn_launch_title','-')}")
        print(f"GitHub:    {enriched.get('github_bio','-')[:60]}")
        print(f"Note ({len(note)} chars): {note}")
