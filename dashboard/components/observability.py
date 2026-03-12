"""
Observability — API health, credits, pipeline status, error log.
"""
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

LOG_FILE    = Path(__file__).parent.parent.parent / "logs" / "pipeline.log"
SCRAPIN_KEY = os.getenv("SCRAPIN_API_KEY", "")
DB_URL      = os.getenv("DATABASE_URL", "")
ANTH_KEY    = os.getenv("ANTHROPIC_API_KEY", "")


def _check_scrapin() -> dict:
    if not SCRAPIN_KEY:
        return {"status": "warn", "msg": "SCRAPIN_API_KEY not set"}
    try:
        import requests
        r = requests.get(
            "https://api.scrapin.io/enrichment/profile",
            params={"linkedInUrl": "https://www.linkedin.com/in/williamhgates", "apikey": SCRAPIN_KEY},
            timeout=8,
        )
        credits = r.headers.get("X-Credits-Remaining", "?")
        if r.status_code == 200:
            return {"status": "ok", "msg": f"Reachable — credits remaining: {credits}"}
        elif r.status_code == 402:
            return {"status": "fail", "msg": "No credits (HTTP 402)"}
        elif r.status_code == 401:
            return {"status": "fail", "msg": "Invalid API key (HTTP 401)"}
        else:
            return {"status": "warn", "msg": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"status": "fail", "msg": str(e)}


def _check_neon() -> dict:
    if not DB_URL:
        return {"status": "warn", "msg": "DATABASE_URL not set — CSV fallback active"}
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL, connect_timeout=4)
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM leads")
        count = cur.fetchone()[0]
        conn.close()
        return {"status": "ok", "msg": f"Connected — {count} leads in DB"}
    except Exception as e:
        return {"status": "fail", "msg": str(e)}


def _check_anthropic() -> dict:
    if not ANTH_KEY:
        return {"status": "warn", "msg": "ANTHROPIC_API_KEY not set"}
    return {"status": "ok", "msg": f"Key present (...{ANTH_KEY[-6:]})"}


def _status_badge(status: str) -> str:
    colors = {"ok": "#00875A", "warn": "#FF8B00", "fail": "#DE350B"}
    labels = {"ok": "✅ OK", "warn": "⚠️ WARN", "fail": "❌ FAIL"}
    color  = colors.get(status, "#6B778C")
    label  = labels.get(status, status.upper())
    return (
        f'<span style="background:{color}; color:#fff; padding:2px 8px; '
        f'border-radius:3px; font-size:0.8em; font-weight:600;">{label}</span>'
    )


def render() -> None:
    st.title("🔭 Observability")

    # ── API Health ────────────────────────────────────────────────────────────
    st.subheader("API Health")

    checks = [
        ("Scrapin.io",    _check_scrapin()),
        ("Neon Postgres", _check_neon()),
        ("Anthropic",     _check_anthropic()),
    ]

    for name, result in checks:
        col1, col2 = st.columns([1, 4])
        col1.markdown(f"**{name}**")
        col2.markdown(
            f"{_status_badge(result['status'])} &nbsp; {result['msg']}",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Run Pre-flight Check ──────────────────────────────────────────────────
    if st.button("Run Full Pre-flight Check"):
        script = Path(__file__).parent.parent.parent / "scripts" / "pre_flight_check.py"
        with st.spinner("Running checks..."):
            try:
                result = subprocess.run(
                    [sys.executable, str(script)],
                    capture_output=True, text=True, timeout=30,
                )
                output = result.stdout + result.stderr
                if "GO —" in output and "NO-GO" not in output:
                    st.success("Pre-flight: GO ✅")
                else:
                    st.warning("Pre-flight issues found")
                st.code(output)
            except Exception as e:
                st.error(f"Check failed: {e}")

    st.markdown("---")

    # ── Pipeline log ──────────────────────────────────────────────────────────
    st.subheader("Pipeline Log (last 100 lines)")
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        last  = "\n".join(lines[-100:])
        st.code(last, language=None)
        if st.button("Clear Log"):
            LOG_FILE.write_text("")
            st.rerun()
    else:
        st.info("No pipeline.log found yet. Run the pipeline to generate logs.")
