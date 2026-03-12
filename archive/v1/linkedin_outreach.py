#!/usr/bin/env python3
"""
LinkedIn Outreach Automation

Profile reading  → profile_reader.py (public scraping + DuckDuckGo, NO LinkedIn login)
Connection send  → Playwright with Mohit's LinkedIn session (unavoidable for sending)

Usage:
  python3 linkedin_outreach.py --login       # First time: login to LinkedIn
  python3 linkedin_outreach.py               # Send today's batch (15 requests)
  python3 linkedin_outreach.py --dry-run     # Preview notes without sending
  python3 linkedin_outreach.py --limit 5     # Send only N today
"""

import argparse
import csv
import random
import time
from datetime import datetime, date
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from profile_reader import enrich_lead_for_note, generate_note

# ── Config ───────────────────────────────────────────────────────────────────
LEADS_CSV   = Path(__file__).parent / "output" / "leads.csv"
SESSION_DIR = Path(__file__).parent / "output" / ".linkedin_session"
LOG_FILE    = Path(__file__).parent / "logs" / "outreach_log.csv"
DAILY_LIMIT = 15
MIN_DELAY   = 30
MAX_DELAY   = 80
NOTE_LIMIT  = 295


# ── Helpers ──────────────────────────────────────────────────────────────────
def human_delay():
    t = random.uniform(MIN_DELAY, MAX_DELAY)
    print(f"  ⏳ Waiting {t:.0f}s...")
    time.sleep(t)


def type_like_human(page, selector, text):
    page.click(selector)
    time.sleep(0.4)
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.04, 0.13))


def count_sent_today() -> int:
    if not LOG_FILE.exists():
        return 0
    today = date.today().isoformat()
    try:
        log = pd.read_csv(LOG_FILE)
        return int(((log["date"].str.startswith(today)) & (log["status"] == "sent")).sum())
    except Exception as e:
        raise RuntimeError(f"[outreach] Cannot read log file — aborting to avoid exceeding daily limit: {e}") from e


def log_result(lead: dict, status: str, note_sent: str):
    LOG_FILE.parent.mkdir(exist_ok=True)
    file_exists = LOG_FILE.exists()
    fields = ["date", "name", "first_name", "title", "company", "location",
              "profile_url", "quality_score", "lead_temperature",
              "status", "note_sent", "ddg_news", "recent_blog", "ddg_snippet",
              "industry", "source"]
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "date":             datetime.now().isoformat(),
            "name":             lead.get("name", ""),
            "first_name":       lead.get("first_name", ""),
            "title":            lead.get("title", ""),
            "company":          lead.get("company", ""),
            "location":         lead.get("location", ""),
            "profile_url":      lead.get("profile_url", ""),
            "quality_score":    lead.get("quality_score", ""),
            "lead_temperature": lead.get("lead_temperature", ""),
            "status":           status,
            "note_sent":        note_sent,
            "ddg_news":         str(lead.get("ddg_news", ""))[:100],
            "recent_blog":      str(lead.get("recent_blog", ""))[:100],
            "ddg_snippet":      str(lead.get("ddg_snippet", ""))[:100],
            "industry":         lead.get("industry", ""),
            "source":           lead.get("source", ""),
        })


def update_lead_csv(df, profile_url, note_sent):
    mask = df["profile_url"] == profile_url
    df.loc[mask, "pipeline_stage"]      = "Request Sent"
    df.loc[mask, "outreach_status"]     = "Connection request sent"
    df.loc[mask, "warm_up_status"]      = f"Request sent {date.today().isoformat()}"
    df.loc[mask, "msg_connection_note"] = note_sent
    return df


def get_queue(df, limit):
    ready = df[
        (df["pipeline_stage"] == "Found") &
        (df["profile_url"].notna()) &
        (df["profile_url"].str.startswith("https://www.linkedin.com/in/", na=False))
    ].copy()
    temp_map = {"Hot": 0, "Warm": 1, "Cold": 2}
    ready["_t"] = ready["lead_temperature"].map(temp_map).fillna(3)
    ready = ready.sort_values(["quality_score", "_t"], ascending=[False, True])
    ready.drop(columns=["_t"], inplace=True)
    return ready.head(limit)


# ── LinkedIn sender (uses session only for SENDING) ──────────────────────────
def send_connection_request(page, profile_url: str, note: str) -> str:
    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(2.5, 4))

        if page.locator("button:has-text('Pending')").count() > 0:
            print("  ⚠️  Already pending")
            return "pending"

        if page.locator("button:has-text('Message')").count() > 0:
            print("  ✅ Already connected")
            return "already_connected"

        connect_btn = page.locator("button:has-text('Connect')").first
        if connect_btn.count() == 0:
            more_btn = page.locator("button:has-text('More')").first
            if more_btn.count() > 0:
                more_btn.click()
                time.sleep(0.8)
                opt = page.locator("span:has-text('Connect')").first
                if opt.count() > 0:
                    opt.click()
                    time.sleep(1)
                else:
                    return "no_button"
            else:
                return "no_button"
        else:
            connect_btn.click()
            time.sleep(random.uniform(1, 2))

        add_note = page.locator("button:has-text('Add a note')")
        if add_note.count() > 0:
            add_note.click()
            time.sleep(0.8)
            note_area = page.locator("textarea[name='message']")
            if note_area.count() > 0:
                type_like_human(page, "textarea[name='message']", note[:NOTE_LIMIT])
                time.sleep(0.5)

        send_btn = page.locator("button:has-text('Send')").first
        if send_btn.count() > 0:
            send_btn.click()
            time.sleep(random.uniform(1.5, 2.5))
            print("  ✅ Sent!")
            return "sent"
        else:
            return "failed"

    except PlaywrightTimeoutError:
        print("  ❌ Timeout")
        return "failed"
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return "failed"


# ── Login ────────────────────────────────────────────────────────────────────
def decrypt_chrome_cookies() -> list:
    """
    Extract LinkedIn cookies directly from Chrome using browser_cookie3.
    No new Chrome window — reads from existing Chrome profile.
    Returns Playwright-compatible cookie list.
    """
    import browser_cookie3
    try:
        cj = browser_cookie3.chrome(domain_name='.linkedin.com')
        cookies = []
        for c in cj:
            cookies.append({
                "name":     c.name,
                "value":    c.value,
                "domain":   c.domain.lstrip("."),
                "path":     c.path or "/",
                "secure":   bool(c.secure),
                "httpOnly": False,
                "sameSite": "None",
            })
        print(f"  ✅ Extracted {len(cookies)} LinkedIn cookies from Chrome")
        return cookies
    except Exception as e:
        print(f"  ❌ Cookie extraction failed: {e}")
        return []


def login_mode():
    """Extract LinkedIn session from existing Chrome — no new window needed."""
    print("\n🔐 Extracting LinkedIn session from your Chrome...")
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    cookies = decrypt_chrome_cookies()
    if not cookies:
        print("  ❌ Could not extract cookies. Make sure you're logged into LinkedIn in Chrome.")
        return

    # Save cookies to a JSON file for Playwright to load
    cookies_file = SESSION_DIR / "linkedin_cookies.json"
    import json
    with open(cookies_file, "w") as f:
        json.dump(cookies, f, indent=2)
    print(f"  ✅ {len(cookies)} cookies saved to session. No new browser window needed.")
    print("  ✅ Ready to send connection requests.")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--login",   action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit",   type=int, default=None)
    args = parser.parse_args()

    if args.login:
        login_mode()
        return

    df          = pd.read_csv(LEADS_CSV)
    daily_limit = args.limit or DAILY_LIMIT
    sent_today  = count_sent_today()
    remaining   = daily_limit - sent_today

    if remaining <= 0:
        print(f"✅ Daily limit ({daily_limit}) reached. Come back tomorrow.")
        return

    queue = get_queue(df, remaining)
    print(f"\n📋 Queue: {len(queue)} leads | Sent today: {sent_today} | Limit: {daily_limit}\n")

    # ── Step 1: Enrich all leads BEFORE opening LinkedIn ─────────────────────
    print("=" * 60)
    print("STEP 1: Reading profiles via public web (no LinkedIn login)")
    print("=" * 60)
    enriched_leads = []
    for i, (_, lead) in enumerate(queue.iterrows(), 1):
        lead_dict = lead.to_dict()
        print(f"\n[{i}/{len(queue)}] {lead['name']} — {lead['company']}")
        enriched = enrich_lead_for_note(lead_dict)
        note     = generate_note(enriched)
        enriched["_final_note"] = note
        enriched_leads.append(enriched)
        print(f"  ✉️  Note ({len(note)} chars): {note}")

    if args.dry_run:
        print("\n[DRY RUN] No requests sent.")
        return

    cookies_file = SESSION_DIR / "linkedin_cookies.json"
    if not cookies_file.exists():
        print("\n❌ Run: python3 linkedin_outreach.py --login")
        return

    import json
    with open(cookies_file) as f:
        li_cookies = json.load(f)

    # ── Step 2: Open browser with Chrome cookies → send requests ─────────────
    print("\n" + "=" * 60)
    print("STEP 2: Sending connection requests (using your Chrome session)")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",
            args=["--start-maximized"],
        )
        context = browser.new_context(no_viewport=True)
        context.add_cookies(li_cookies)
        page = context.new_page()
        page.goto("https://www.linkedin.com/feed", wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        if "login" in page.url:
            print("❌ Session expired. Run: python3 linkedin_outreach.py --login")
            browser.close()
            return

        sent_count = 0
        for i, enriched in enumerate(enriched_leads, 1):
            note = enriched["_final_note"]
            print(f"\n[{i}/{len(enriched_leads)}] {enriched['name']} — {enriched['company']}")
            print(f"  ✉️  Sending with note: {note[:80]}...")
            status = send_connection_request(page, enriched["profile_url"], note)
            log_result(enriched, status, note)
            if status in ("sent", "pending", "already_connected"):
                df = update_lead_csv(df, enriched["profile_url"], note)
                df.to_csv(LEADS_CSV, index=False)
                if status == "sent":
                    sent_count += 1
            if i < len(enriched_leads):
                human_delay()

        context.close()
        browser.close()

    print(f"\n✅ Done! Sent {sent_count}/{len(enriched_leads)} requests today.")
    print(f"📊 Log: {LOG_FILE}")


if __name__ == "__main__":
    main()
