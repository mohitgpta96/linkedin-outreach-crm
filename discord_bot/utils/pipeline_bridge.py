"""
Bridge between Discord commands and the LinkedIn pipeline scripts.
Primary source: leads/messages/enriched_leads.json (local dev)
Cloud fallback:  Neon Postgres via data_store.get_leads() (Railway/cloud)
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
import re
from pathlib import Path
from typing import Callable, Optional

# Make project root importable (for data_store)
_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

ENRICHED_JSON = Path(_ROOT / "leads/messages/enriched_leads.json")
PIPELINE_STATE_JSON = Path(_ROOT / "pipeline_state.json")

OUTREACH_STAGES = ["new", "warming_up", "requested", "connected", "replied", "meeting", "done", "skipped"]

_USE_DB: bool | None = None  # cached after first check


def _should_use_db() -> bool:
    """True when JSON file is missing — use Neon/SQLite DB instead."""
    global _USE_DB
    if _USE_DB is None:
        _USE_DB = not ENRICHED_JSON.exists()
    return _USE_DB


# ── Data access ───────────────────────────────────────────────────────────────

def load_leads() -> list[dict]:
    if not _should_use_db():
        try:
            return json.loads(ENRICHED_JSON.read_text())
        except Exception:
            pass
    # Cloud / DB path
    try:
        import data_store
        return data_store.get_leads()
    except Exception:
        return []


def save_leads(leads: list[dict]) -> None:
    """Write to JSON if accessible, always try DB update too."""
    if ENRICHED_JSON.exists():
        try:
            ENRICHED_JSON.write_text(json.dumps(leads, indent=2, ensure_ascii=False))
        except Exception:
            pass
    # Sync mutations to DB
    try:
        import data_store
        for lead in leads:
            url = lead.get("profile_url", "")
            stage = lead.get("outreach_stage", "")
            if url and stage:
                data_store.set_outreach_stage(url, stage)
    except Exception:
        pass


def load_pipeline_state() -> dict:
    if not PIPELINE_STATE_JSON.exists():
        return {}
    try:
        return json.loads(PIPELINE_STATE_JSON.read_text())
    except Exception:
        return {}


def save_pipeline_state(state: dict) -> None:
    PIPELINE_STATE_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ── Lead helpers ──────────────────────────────────────────────────────────────

def find_lead(name: str) -> Optional[dict]:
    """Case-insensitive partial match on name or company."""
    leads = load_leads()
    q = name.lower().strip()
    # Exact first name match
    for lead in leads:
        if lead.get("name","").lower().split()[0] == q:
            return lead
    # Partial name match
    for lead in leads:
        if q in lead.get("name","").lower() or q in lead.get("company","").lower():
            return lead
    return None


def filter_leads(f: str) -> list[dict]:
    """Filter leads by keyword: ready/enriched/hot/strong/warm/warming/contacted/replied/meeting/done/all"""
    leads = load_leads()
    f = f.lower()
    if f in ("all", ""):
        return leads
    if f == "hot":
        return [l for l in leads if str(l.get("pm_demand_tier","")).upper() == "HOT"]
    if f == "strong":
        return [l for l in leads if str(l.get("pm_demand_tier","")).upper() == "STRONG"]
    if f == "warm":
        return [l for l in leads if str(l.get("pm_demand_tier","")).upper() == "WARM"]
    if f in ("ready", "enriched", "new"):
        return [l for l in leads if l.get("outreach_stage", "") == "new"]
    if f == "warming":
        return [l for l in leads if l.get("outreach_stage","") == "warming_up"]
    if f == "contacted":
        return [l for l in leads if l.get("outreach_stage","") == "requested"]
    if f == "replied":
        return [l for l in leads if l.get("outreach_stage","") == "replied"]
    if f == "meeting":
        return [l for l in leads if l.get("outreach_stage","") == "meeting"]
    if f == "done":
        return [l for l in leads if l.get("outreach_stage","") == "done"]
    # Stage name direct match
    return [l for l in leads if l.get("outreach_stage","") == f]


def advance_lead_stage(name: str, target_stage: Optional[str] = None) -> tuple[Optional[dict], str, str]:
    """
    Advance or jump a lead's outreach_stage.
    Returns (updated_lead, old_stage, new_stage).
    """
    leads = load_leads()
    lead = find_lead(name)
    if not lead:
        return None, "", ""

    old_stage = lead.get("outreach_stage", "new")
    if target_stage:
        new_stage = target_stage
    else:
        idx = OUTREACH_STAGES.index(old_stage) if old_stage in OUTREACH_STAGES else 0
        new_stage = OUTREACH_STAGES[min(idx + 1, len(OUTREACH_STAGES) - 2)]  # -2 to not auto-skip

    # Update in list
    for i, l in enumerate(leads):
        if l.get("name") == lead.get("name"):
            leads[i]["outreach_stage"] = new_stage
            lead = leads[i]
            break

    save_leads(leads)

    # Try updating DB if available
    try:
        import data_store
        url = lead.get("profile_url", "")
        if url:
            data_store.set_outreach_stage(url, new_stage)
    except Exception:
        pass

    return lead, old_stage, new_stage


def skip_lead(name: str, reason: str = "") -> Optional[dict]:
    leads = load_leads()
    lead = find_lead(name)
    if not lead:
        return None
    for i, l in enumerate(leads):
        if l.get("name") == lead.get("name"):
            leads[i]["outreach_stage"] = "skipped"
            leads[i]["skip_reason"] = reason
            lead = leads[i]
            break
    save_leads(leads)
    return lead


def add_note(name: str, note: str) -> Optional[dict]:
    leads = load_leads()
    lead = find_lead(name)
    if not lead:
        return None
    for i, l in enumerate(leads):
        if l.get("name") == lead.get("name"):
            existing = leads[i].get("notes", "")
            from datetime import datetime
            ts = datetime.now().strftime("%b %d %H:%M")
            leads[i]["notes"] = f"{existing}\n[{ts}] {note}".strip()
            lead = leads[i]
            break
    save_leads(leads)
    return lead


def mark_warmup_done(name: str, day: int) -> Optional[dict]:
    leads = load_leads()
    lead = find_lead(name)
    if not lead:
        return None
    for i, l in enumerate(leads):
        if l.get("name") == lead.get("name"):
            completed = leads[i].get("warmup_completed", [])
            if day not in completed:
                completed.append(day)
            leads[i]["warmup_completed"] = sorted(completed)
            lead = leads[i]
            break
    save_leads(leads)
    return lead


def search_leads(query: str) -> list[dict]:
    leads = load_leads()
    q = query.lower()
    return [
        l for l in leads
        if q in l.get("name","").lower()
        or q in l.get("company","").lower()
        or q in l.get("title","").lower()
        or q in str(l.get("source","")).lower()
    ]


def get_today_tasks() -> dict:
    """Returns bucketed tasks for today's outreach."""
    leads = load_leads()
    warmup_needed  = []
    ready_to_send  = []
    followup_due   = []

    WARMUP_SCHEDULE = {1: "View profile + follow company", 2: "Like 1-2 recent posts",
                       3: "Comment on a post", 4: "Send connection request"}

    for lead in leads:
        stage     = lead.get("outreach_stage", "new")
        completed = lead.get("warmup_completed", [])

        if stage == "new":
            ready_to_send.append(lead)
        elif stage == "warming_up":
            next_day  = max(completed) + 1 if completed else 1
            if next_day <= 4:
                lead["_next_warmup_day"]    = next_day
                lead["_next_warmup_action"] = WARMUP_SCHEDULE.get(next_day, "")
                warmup_needed.append(lead)
        elif stage in ("connected", "replied"):
            followup_due.append(lead)

    return {
        "warmup_needed":  warmup_needed,
        "ready_to_send":  ready_to_send,
        "followup_due":   followup_due,
    }


# ── Pipeline subprocess runner ────────────────────────────────────────────────

async def run_pipeline_command(
    mode: str,
    batch_size: int = 5,
    dry_run: bool = False,
    callback: Optional[Callable] = None,
) -> int:
    """
    Runs pipeline/run_pipeline.py as subprocess.
    Streams each stdout line to callback(line: str).
    Returns exit code.
    """
    cmd = ["python3", "pipeline/run_pipeline.py", "--mode", mode]
    if mode in ("enrich_only", "full"):
        cmd += ["--batch", str(batch_size)]
    if dry_run:
        cmd.append("--dry-run")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(Path(__file__).parent.parent.parent),
        )
        async for raw_line in process.stdout:
            line = raw_line.decode(errors="replace").rstrip()
            if callback and line:
                await callback(line)
        await process.wait()
        return process.returncode
    except FileNotFoundError:
        if callback:
            await callback("⚠️ pipeline/run_pipeline.py not found — run from project root")
        return 1
    except Exception as e:
        if callback:
            await callback(f"❌ Error: {e}")
        return 1


async def get_credit_info() -> dict:
    """Read credit info from pipeline_state.json."""
    state = load_pipeline_state()
    enrichment = state.get("enrichment", {})
    apify_credits = enrichment.get("apify_credits", {})
    return {
        "apify_balance":   apify_credits.get("balance", "?"),
        "groq_tokens":     enrichment.get("groq_tokens_today", 0),
        "daily_spend":     state.get("daily_spend", 0),
        "can_enrich":      int(float(apify_credits.get("balance", 0)) / 0.08) if apify_credits.get("balance") else 0,
    }
