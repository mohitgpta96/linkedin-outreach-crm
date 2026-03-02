"""
Free Enrichment: GitHub API Profile Enricher
============================================
For leads found via GitHub, fetch their real company, bio, website, and location.

Rate limits:
  - No token: 60 requests/hour (runs 1042 leads in ~17.4 hours)
  - With GITHUB_TOKEN in .env: 5000/hour (runs all in ~13 minutes)

Usage:
    python3 enrichment/github_profile_enrich.py
    python3 enrichment/github_profile_enrich.py --batch 200   # only first 200
"""

import sys, os, time, re, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # Optional — add to .env for 5000/hr
HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    RATE_LIMIT = 50     # stay under 5000/hr
    SLEEP = 0.8         # seconds between requests
else:
    RATE_LIMIT = 45     # stay safely under 60/hr
    SLEEP = 1.5         # seconds between requests

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "output", "leads.csv")

# ── Pain point templates (refined for GitHub founders) ──────────────
def infer_pain_points(bio: str, company: str, repos: int, followers: int) -> str:
    points = []
    bio_l = bio.lower()

    if any(x in bio_l for x in ['founder', 'ceo', 'co-founder']):
        points.append("Founder wearing too many hats — needs PM to own product roadmap")
    if any(x in bio_l for x in ['engineer', 'developer', 'cto', 'technical']):
        points.append("Technical founder — product decisions competing with engineering time")
    if repos > 20:
        points.append(f"Active builder ({repos}+ repos) — feature delivery needs structured prioritization")
    if followers > 500:
        points.append("High-visibility founder — needs PM to manage community product expectations")
    if any(x in bio_l for x in ['building', 'startup', 'seed', 'early stage']):
        points.append("Early-stage startup — no PM structure yet, moving fast without clear priorities")
    if any(x in bio_l for x in ['saas', 'b2b', 'enterprise', 'platform']):
        points.append("B2B SaaS product — roadmap alignment with customer needs requires dedicated PM")

    if not points:
        points = [
            "No dedicated PM — founder managing product and operations simultaneously",
            "Engineering-heavy team likely needs PM to bridge product and development",
        ]
    return " | ".join(points[:3])


def gen_messages(name: str, company: str, bio: str, website: str) -> dict:
    first = name.split()[0] if name else "there"
    co = company.strip().lstrip('@') if company else "your company"
    bio_short = bio[:80] if bio else ""
    web = website.replace('https://','').replace('http://','').rstrip('/') if website else ""

    connection_note = (
        f"{first}, saw what you're building at {co} — impressive work. "
        f"How are you currently managing the product roadmap as you scale?"
    )[:280]

    first_dm = (
        f"{first}, took a look at {co}{(' — ' + web) if web else ''}. "
        f"As a PM, the scaling challenge caught my eye. "
        f"How are you currently handling product prioritization with your engineering team?"
    )[:300]

    followup_4 = (
        f"{first}, no rush — just curious: what's the biggest bottleneck slowing {co} "
        f"down right now? Would love to think through it with you."
    )

    followup_10 = (
        f"{first}, saw some recent updates from {co}. "
        f"Still thinking about the scaling question I raised. "
        f"Open to a 15-min call to share what's worked for similar-stage teams?"
    )

    followup_17 = (
        f"{first}, one last thought — if a dedicated PM isn't the right fit for {co} yet, "
        f"would you know someone in your network who's actively hiring one? "
        f"Either way, rooting for what you're building."
    )

    followup_25 = (
        f"{first}, final note from me. {co} looks like something worth following. "
        f"Leaving the door open if timing changes. Wish you the best."
    )

    return {
        "msg_connection_note": connection_note,
        "msg_first_dm": first_dm,
        "msg_followup_day4": followup_4,
        "msg_followup_day10": followup_10,
        "msg_followup_day17": followup_17,
        "msg_followup_day25": followup_25,
        "msg_word_count_note": len(connection_note.split()),
        "msg_word_count_dm": len(first_dm.split()),
    }


def fetch_github_user(username: str) -> dict:
    """Fetch user data from GitHub API. Returns dict or None on error."""
    url = f"https://api.github.com/users/{username}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 403:
            # Rate limited
            reset = int(r.headers.get('X-RateLimit-Reset', time.time() + 3600))
            wait = max(reset - time.time() + 5, 60)
            print(f"  ⚠ Rate limited — sleeping {int(wait/60)} minutes...")
            time.sleep(wait)
            # Retry once
            r2 = requests.get(url, headers=HEADERS, timeout=10)
            return r2.json() if r2.status_code == 200 else None
        elif r.status_code == 404:
            return None
        else:
            print(f"  HTTP {r.status_code} for {username}")
            return None
    except Exception as e:
        print(f"  Error fetching {username}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=0, help="Only process first N leads (0 = all)")
    args = parser.parse_args()

    df = pd.read_csv(CSV_PATH)

    # Only GitHub leads that haven't been enriched yet
    github_mask = df['profile_url'].astype(str).str.contains('github.com/', na=False)
    needs_enrich = github_mask & (df['company'].isna() | (df['company'].astype(str) == 'nan') | (df['company'] == ''))

    to_enrich = df[needs_enrich].copy()
    if args.batch > 0:
        to_enrich = to_enrich.head(args.batch)

    total = len(to_enrich)
    print(f"GitHub leads to enrich: {total}")
    if GITHUB_TOKEN:
        print(f"Using GitHub token — rate limit: 5000/hr")
    else:
        print(f"No GitHub token — rate limit: 60/hr (add GITHUB_TOKEN to .env for 80x speedup)")
    print(f"Estimated time: {total * SLEEP / 60:.1f} minutes")
    print()

    enriched = 0
    for i, (idx, row) in enumerate(to_enrich.iterrows()):
        profile_url = str(row['profile_url'])
        username = profile_url.rstrip('/').split('/')[-1]

        print(f"[{i+1}/{total}] {row.get('name', username)} (@{username})", end=" ... ", flush=True)

        data = fetch_github_user(username)
        if not data:
            print("skip")
            time.sleep(SLEEP)
            continue

        # Extract fields
        real_name = data.get('name') or row.get('name', username)
        company = (data.get('company') or '').strip().lstrip('@')
        bio = (data.get('bio') or '').strip()
        website = (data.get('blog') or '').strip()
        location = (data.get('location') or '').strip()
        followers = data.get('followers', 0)
        repos = data.get('public_repos', 0)

        # Update fields
        df.at[idx, 'name'] = real_name
        if company:
            df.at[idx, 'company'] = company
        if bio:
            df.at[idx, 'about_snippet'] = bio[:250]
            df.at[idx, 'headline'] = bio[:120]
        if website:
            df.at[idx, 'company_website'] = website
        if location:
            # Normalize location
            lo = location.lower()
            if any(x in lo for x in ['india', 'bangalore', 'mumbai', 'delhi']):
                df.at[idx, 'location'] = 'India'
            elif any(x in lo for x in ['united states', 'usa', 'san francisco', 'new york', 'california']):
                df.at[idx, 'location'] = 'United States'
            elif any(x in lo for x in ['united kingdom', 'london', 'uk']):
                df.at[idx, 'location'] = 'United Kingdom'
            elif any(x in lo for x in ['uae', 'dubai', 'emirates']):
                df.at[idx, 'location'] = 'UAE'
            else:
                df.at[idx, 'location'] = location[:50]

        # Enrich pain points + messages
        pain = infer_pain_points(bio, company, repos, followers)
        df.at[idx, 'inferred_pain_points'] = pain
        msgs = gen_messages(real_name, company or username, bio, website)
        for k, v in msgs.items():
            df.at[idx, k] = v

        df.at[idx, 'what_they_do'] = bio[:200] if bio else f"Tech founder at {company or username}"

        enriched += 1
        print(f"{real_name} @ {company or '(no company)'}")

        # Save every 50 rows
        if enriched % 50 == 0:
            df.to_csv(CSV_PATH, index=False)
            print(f"  ✓ Saved progress ({enriched}/{total})")

        time.sleep(SLEEP)

    df.to_csv(CSV_PATH, index=False)
    print(f"\n✅ Enriched {enriched}/{total} GitHub leads")
    print(f"CSV saved: {CSV_PATH}")


if __name__ == "__main__":
    main()
