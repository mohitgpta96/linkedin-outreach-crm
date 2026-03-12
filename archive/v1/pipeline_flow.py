#!/usr/bin/env python3
"""
pipeline_flow.py — End-to-end OutreachIQ V2 pipeline
Steps: Discovery → ICP Gate → Enrichment → Messages → Save

Usage:
    python3 pipeline_flow.py               # full run
    python3 pipeline_flow.py --skip-discovery   # skip discovery, use existing ICP candidates
    python3 pipeline_flow.py --enrich-limit 10  # enrich only N leads
    python3 pipeline_flow.py --dry-run          # discovery only, no enrichment/messages
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_store import get_leads, upsert_lead

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/pipeline.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

ICP_GATE_MIN      = 5   # abort if fewer ICP candidates
ENRICH_GATE_MIN   = 70  # only enrich leads with icp_score >= this


@dataclass
class PipelineState:
    raw_count:     int          = 0
    icp_count:     int          = 0
    enriched:      list[dict]   = field(default_factory=list)
    with_messages: list[dict]   = field(default_factory=list)
    errors:        list[str]    = field(default_factory=list)


# ── Step 1: Discovery ────────────────────────────────────────────────────────

def step_discovery(state: PipelineState) -> PipelineState:
    logger.info("[Pipeline] Step 1: Discovery")
    from discovery.run_all import run_yc, run_hn, run_github
    from discovery.dedup   import deduplicate_and_score

    existing = get_leads()
    existing_urls = {
        str(l.get("profile_url") or "").strip().lower()
        for l in existing if l.get("profile_url")
    }

    raw: list[dict] = []
    for source_fn in (run_yc, run_hn, run_github):
        try:
            raw.extend(source_fn())
        except Exception as e:
            logger.error(f"  Source {source_fn.__name__} failed: {e}")
            state.errors.append(str(e))

    new_leads = deduplicate_and_score(raw, existing_urls)
    state.raw_count = len(new_leads)

    if len(new_leads) < 3:
        raise ValueError(f"[Pipeline] Aborting — only {len(new_leads)} new leads discovered")

    for lead in new_leads:
        lead.setdefault("pipeline_stage", "ICP Candidate")
        lead.setdefault("enrichment_status", "pending")
        upsert_lead(lead)

    logger.info(f"  Saved {len(new_leads)} new leads")
    return state


# ── ICP Gate ─────────────────────────────────────────────────────────────────

def check_icp_gate(state: PipelineState) -> str:
    candidates = get_leads({"pipeline_stage": "ICP Candidate"})
    state.icp_count = len(candidates)
    logger.info(f"[Pipeline] ICP Gate: {state.icp_count} candidates")
    if state.icp_count < ICP_GATE_MIN:
        logger.error(f"  GATE FAIL — {state.icp_count} < {ICP_GATE_MIN} minimum")
        return "abort"
    return "ok"


# ── Step 2: Enrichment ───────────────────────────────────────────────────────

async def step_enrichment(state: PipelineState, limit: int) -> PipelineState:
    logger.info("[Pipeline] Step 2: Enrichment (Scrapin.io)")

    import importlib
    try:
        scrapin_mod = importlib.import_module("scripts.scrapin_enrich")
    except ImportError:
        # Path fallback
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "scrapin_enrich",
            Path(__file__).parent / "scripts" / "scrapin_enrich.py",
        )
        scrapin_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scrapin_mod)

    candidates = get_leads({"pipeline_stage": "ICP Candidate"})
    # Prefer Signal A leads and higher icp_score
    candidates.sort(
        key=lambda l: (
            0 if l.get("icp_signal_type") == "A" else 1,
            -(l.get("icp_score") or 0),
        )
    )
    batch = candidates[:limit]

    loop = asyncio.get_event_loop()
    results = await scrapin_mod.run_enrichment(batch, loop)
    state.enriched = [r for r in results if isinstance(r, dict)]
    logger.info(f"  Enriched {len(state.enriched)} leads")
    return state


# ── Step 3: Messages ─────────────────────────────────────────────────────────

def step_messages(state: PipelineState) -> PipelineState:
    logger.info("[Pipeline] Step 3: Message generation")
    from enrichment.messages import generate_messages

    for lead in state.enriched:
        name = lead.get("founder_name") or lead.get("name") or "-"
        try:
            msgs = generate_messages(lead)
            lead.update(msgs)
            lead["pipeline_stage"]    = "Ready"
            lead["enrichment_status"] = "ready"
            upsert_lead(lead)
            state.with_messages.append(lead)
            logger.info(f"  ✅ Messages generated for {name}")
        except Exception as e:
            logger.error(f"  ❌ Message gen failed for {name}: {e}")
            state.errors.append(f"{name}: {e}")

    return state


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-discovery", action="store_true")
    parser.add_argument("--enrich-limit",   type=int, default=10)
    parser.add_argument("--dry-run",        action="store_true")
    args = parser.parse_args()

    t0    = time.time()
    state = PipelineState()

    print("\n" + "="*60)
    print("OutreachIQ V2 — Pipeline")
    print("="*60)

    # Step 1: Discovery
    if not args.skip_discovery:
        state = step_discovery(state)
        print(f"  Discovery: {state.raw_count} new leads")
    else:
        print("  Discovery: skipped (using existing ICP candidates)")

    # ICP Gate
    result = check_icp_gate(state)
    if result == "abort":
        print(f"\n⛔ ICP Gate: only {state.icp_count} candidates — minimum {ICP_GATE_MIN} required")
        sys.exit(2)
    print(f"  ICP Gate: {state.icp_count} candidates ✅")

    if args.dry_run:
        print("\n[DRY RUN] Stopping before enrichment.")
        return

    # Step 2: Enrichment
    loop  = asyncio.get_event_loop()
    state = loop.run_until_complete(step_enrichment(state, limit=args.enrich_limit))
    print(f"  Enrichment: {len(state.enriched)} leads enriched")

    # Step 3: Messages
    state = step_messages(state)
    print(f"  Messages: {len(state.with_messages)} leads ready")

    elapsed = time.time() - t0

    print("\n" + "="*60)
    print("Pipeline Complete")
    print("="*60)
    print(f"  New leads discovered : {state.raw_count}")
    print(f"  ICP candidates       : {state.icp_count}")
    print(f"  Enriched             : {len(state.enriched)}")
    print(f"  Ready (with messages): {len(state.with_messages)}")
    print(f"  Errors               : {len(state.errors)}")
    print(f"  Time                 : {elapsed:.1f}s")

    if state.errors:
        print("\nErrors:")
        for e in state.errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
