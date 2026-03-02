"""
Enrichment Phase 2B: Recent Posts & Activity Analysis
Uses apimaestro/linkedin-profile-posts (4.6★, 15K users).
Input: username (LinkedIn profile username or full URL) - one profile at a time.
Extracts themes, tone, most relevant post for outreach.
"""

import re
import time
import logging
from apify_client import ApifyClient

from config import (
    APIFY_TOKEN,
    APIFY_LINKEDIN_POSTS_SCRAPER,
    MAX_POSTS_TO_ANALYZE,
    MAX_PROFILES_TO_ENRICH,
)

logger = logging.getLogger(__name__)

TOPIC_CATEGORIES = {
    "product growth":    ["launch", "shipped", "feature", "product", "roadmap", "release", "v2"],
    "team scaling":      ["hiring", "team", "culture", "growing", "headcount", "onboard"],
    "founder struggles": ["challenge", "struggle", "hard", "difficult", "overwhelm", "chaos", "burnout"],
    "funding/startup":   ["funding", "raise", "investor", "series", "seed", "startup", "vc"],
    "delivery/process":  ["sprint", "process", "deadline", "delivery", "agile", "pm", "project"],
    "lessons learned":   ["learned", "mistake", "lesson", "failed", "insight", "reflection"],
    "customer/sales":    ["customer", "client", "revenue", "sales", "churn", "growth", "mrr"],
}

TONE_SIGNALS = {
    "excited":       ["🚀", "🎉", "excited", "thrilled", "amazing", "incredible", "love"],
    "frustrated":    ["frustrated", "annoying", "struggling", "chaos", "overwhelmed", "hard truth"],
    "candid":        ["honest", "real talk", "let me be", "truth is", "confession"],
    "inspirational": ["inspire", "believe", "dream", "possible", "journey", "lesson"],
    "informational": ["here's how", "tips", "framework", "guide", "steps", "breakdown"],
}

PM_KEYWORDS = [
    "project manager", "pm", "roadmap", "sprint", "process",
    "hiring", "chaos", "overwhelm", "deliver", "ship", "team",
]


def _extract_username(profile_url: str) -> str:
    """Extract LinkedIn username from a full profile URL."""
    # linkedin.com/in/username or linkedin.com/in/username/
    match = re.search(r"linkedin\.com/in/([^/?#]+)", profile_url)
    if match:
        return match.group(1).rstrip("/")
    # If already a username (no URL structure), return as-is
    if "/" not in profile_url and "linkedin" not in profile_url:
        return profile_url
    return profile_url  # fallback: pass full URL, actor handles it


def _detect_themes(texts: list[str]) -> list[str]:
    all_text = " ".join(texts).lower()
    scores = {
        cat: sum(1 for kw in kws if kw in all_text)
        for cat, kws in TOPIC_CATEGORIES.items()
    }
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [cat for cat, score in ranked[:3] if score > 0]


def _detect_tone(texts: list[str]) -> str:
    all_text = " ".join(texts).lower()
    tone_scores = {
        tone: sum(1 for signal in signals if signal.lower() in all_text)
        for tone, signals in TONE_SIGNALS.items()
    }
    best = max(tone_scores, key=tone_scores.get)
    return best if tone_scores[best] > 0 else "neutral"


def _find_relevant_post(posts: list[dict]) -> str:
    best_score, best_text = 0, ""
    for post in posts:
        text = post.get("text") or post.get("content") or post.get("postText", "")
        score = sum(1 for kw in PM_KEYWORDS if kw in text.lower())
        if score > best_score:
            best_score, best_text = score, text
    return best_text[:300] if best_text else ""


def enrich_with_posts(leads: list[dict]) -> list[dict]:
    """
    For each lead with a profile_url, scrape their recent posts.
    apimaestro/linkedin-profile-posts processes one profile per run.
    We call it per lead with a small delay to respect rate limits.
    """
    if not APIFY_TOKEN:
        logger.warning("APIFY_TOKEN not set — skipping post enrichment.")
        return leads

    to_enrich = [
        lead for lead in leads
        if lead.get("profile_url") and not lead.get("post_themes")
    ][:MAX_PROFILES_TO_ENRICH]

    if not to_enrich:
        logger.info("[Post Enrichment] Nothing to enrich.")
        return leads

    client = ApifyClient(APIFY_TOKEN)
    enrichment_map: dict[str, dict] = {}

    for i, lead in enumerate(to_enrich):
        profile_url = lead["profile_url"]
        username = _extract_username(profile_url)
        logger.info(f"[Post Enrichment] {i+1}/{len(to_enrich)}: {username}")

        # apimaestro/linkedin-profile-posts input: { "username": "...", "total_posts": N }
        run_input = {
            "username":    username,
            "total_posts": MAX_POSTS_TO_ANALYZE,
            "proxy":       {"useApifyProxy": True},
        }

        try:
            run = client.actor(APIFY_LINKEDIN_POSTS_SCRAPER).call(run_input=run_input)
            posts = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        except Exception as exc:
            logger.error(f"[Post Enrichment] Failed for {username}: {exc}")
            time.sleep(1)
            continue

        if posts:
            texts = [
                p.get("text") or p.get("content") or p.get("postText", "")
                for p in posts
            ]
            enrichment_map[profile_url] = {
                "post_themes":         _detect_themes(texts),
                "post_tone":           _detect_tone(texts),
                "recent_notable_post": _find_relevant_post(posts),
            }

        time.sleep(0.5)  # be gentle with rate limits

    for lead in leads:
        data = enrichment_map.get(lead.get("profile_url", ""))
        if not data:
            continue
        lead["post_themes"]         = ", ".join(data["post_themes"]) if data["post_themes"] else ""
        lead["post_tone"]           = data["post_tone"]
        lead["recent_notable_post"] = data["recent_notable_post"]

    logger.info(f"[Post Enrichment] Enriched {len(enrichment_map)} profiles.")
    return leads
