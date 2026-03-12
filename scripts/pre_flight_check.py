#!/usr/bin/env python3
"""
pre_flight_check.py — System health check before running pipeline
Checks: Scrapin.io API, Neon Postgres, leads count, Anthropic key

Usage:
    python3 scripts/pre_flight_check.py
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SCRAPIN_KEY   = os.getenv("SCRAPIN_API_KEY", "")
DATABASE_URL  = os.getenv("DATABASE_URL", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CSV_PATH      = Path(__file__).parent.parent / "output" / "leads.csv"

checks = []

print("\n" + "="*55)
print("Pre-flight Check")
print("="*55)


# ── 1. Neon Postgres ─────────────────────────────────────────────────────────
print("\n[1] Neon Postgres")
if not DATABASE_URL:
    print("  ⚠️  DATABASE_URL not set — will use CSV fallback")
    checks.append(("Neon Postgres", "WARN", "DATABASE_URL missing — CSV fallback active"))
else:
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM leads")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"  ✅ Connected — {count} leads in DB")
        checks.append(("Neon Postgres", "OK", f"{count} leads"))
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        checks.append(("Neon Postgres", "FAIL", str(e)))


# ── 2. Scrapin.io API ────────────────────────────────────────────────────────
print("\n[2] Scrapin.io API")
if not SCRAPIN_KEY:
    print("  ⚠️  SCRAPIN_API_KEY not set — enrichment will be skipped")
    checks.append(("Scrapin.io", "WARN", "SCRAPIN_API_KEY missing"))
else:
    try:
        r = requests.get(
            "https://api.scrapin.io/enrichment/profile",
            params={"linkedInUrl": "https://www.linkedin.com/in/williamhgates", "apikey": SCRAPIN_KEY},
            timeout=10,
        )
        if r.status_code == 200:
            print(f"  ✅ API reachable (HTTP 200)")
            credits_remaining = r.headers.get("X-Credits-Remaining", "unknown")
            print(f"  Credits remaining: {credits_remaining}")
            checks.append(("Scrapin.io", "OK", f"credits={credits_remaining}"))
        elif r.status_code == 402:
            print(f"  ❌ No credits remaining (HTTP 402)")
            checks.append(("Scrapin.io", "FAIL", "No credits"))
        elif r.status_code == 401:
            print(f"  ❌ Invalid API key (HTTP 401)")
            checks.append(("Scrapin.io", "FAIL", "Invalid key"))
        else:
            print(f"  ⚠️  Unexpected status: HTTP {r.status_code}")
            checks.append(("Scrapin.io", "WARN", f"HTTP {r.status_code}"))
    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        checks.append(("Scrapin.io", "FAIL", str(e)))


# ── 3. Anthropic API key ─────────────────────────────────────────────────────
print("\n[3] Anthropic API")
if not ANTHROPIC_KEY:
    print("  ⚠️  ANTHROPIC_API_KEY not set — message generation will fail")
    checks.append(("Anthropic", "WARN", "ANTHROPIC_API_KEY missing"))
else:
    print(f"  ✅ Key present (sk-ant-...{ANTHROPIC_KEY[-6:]})")
    checks.append(("Anthropic", "OK", "Key present"))


# ── 4. Leads CSV ─────────────────────────────────────────────────────────────
print("\n[4] Leads CSV")
if CSV_PATH.exists():
    import pandas as pd
    df = pd.read_csv(CSV_PATH)
    with_url = df["profile_url"].notna().sum() if "profile_url" in df.columns else 0
    print(f"  ✅ {len(df)} leads ({with_url} with LinkedIn URL)")
    checks.append(("Leads CSV", "OK", f"{len(df)} leads"))
else:
    print(f"  ⚠️  {CSV_PATH} not found")
    checks.append(("Leads CSV", "WARN", "File not found"))


# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print("Summary")
print("="*55)
fails = [c for c in checks if c[1] == "FAIL"]
warns = [c for c in checks if c[1] == "WARN"]

for name, status, msg in checks:
    icon = "✅" if status == "OK" else ("⚠️ " if status == "WARN" else "❌")
    print(f"  {icon} {name:20s} {msg}")

print()
if fails:
    print(f"❌ GO / NO-GO: NO-GO — {len(fails)} failure(s). Fix before running pipeline.")
    sys.exit(1)
else:
    print("✅ GO — system ready")
    if warns:
        print(f"   ({len(warns)} warning(s) — check above)")
