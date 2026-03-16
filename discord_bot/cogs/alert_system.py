"""
Real-time alert engine.
Watches enriched_leads.json and pipeline_state.json.
Posts alerts to #alerts channel automatically.
"""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime
import discord
from discord.ext import commands, tasks
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from discord_bot.utils.pipeline_bridge import (
    ENRICHED_JSON, PIPELINE_STATE_JSON, load_leads, load_pipeline_state,
)

WATCH_INTERVAL    = 15   # seconds
STATE_WATCH_INTERVAL = 30


class AlertSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._enriched_mtime  = 0.0
        self._state_mtime     = 0.0
        self._last_lead_count = 0
        self._last_apify_bal  = None
        self._alerts_channel: discord.TextChannel | None = None
        self._logs_channel:   discord.TextChannel | None = None
        self.watch_enriched.start()
        self.watch_pipeline_state.start()

    def cog_unload(self):
        self.watch_enriched.cancel()
        self.watch_pipeline_state.cancel()

    async def _get_alerts_channel(self) -> discord.TextChannel | None:
        if self._alerts_channel:
            return self._alerts_channel
        ch_id = os.getenv("DISCORD_ALERTS_CHANNEL_ID")
        if ch_id:
            ch = self.bot.get_channel(int(ch_id))
            if ch:
                self._alerts_channel = ch
                return ch
        return None

    async def _get_logs_channel(self) -> discord.TextChannel | None:
        if self._logs_channel:
            return self._logs_channel
        ch_id = os.getenv("DISCORD_LOGS_CHANNEL_ID")
        if ch_id:
            ch = self.bot.get_channel(int(ch_id))
            if ch:
                self._logs_channel = ch
                return ch
        return None

    @tasks.loop(seconds=WATCH_INTERVAL)
    async def watch_enriched(self):
        if not ENRICHED_JSON.exists():
            return
        try:
            mtime = ENRICHED_JSON.stat().st_mtime
            if mtime <= self._enriched_mtime:
                return

            new_leads = load_leads()
            new_count = len(new_leads)

            if self._enriched_mtime > 0 and new_count != self._last_lead_count:
                # Leads changed — build alert
                ch = await self._get_alerts_channel()
                if ch:
                    added = [l for l in new_leads if l.get("enriched_at","") != ""]
                    diff  = new_count - self._last_lead_count
                    title = f"🆕 {abs(diff)} leads {'added' if diff > 0 else 'updated'}"

                    lines = []
                    for lead in new_leads[-5:]:
                        name     = lead.get("name","?")
                        company  = lead.get("company","?")
                        readiness= str(lead.get("readiness","PARTIAL")).upper()
                        ready_icon = "●" if readiness == "READY" else "◑"
                        lines.append(f"• **{name}** ({company}) — {ready_icon} {readiness}")

                    desc = "\n".join(lines) + f"\n\nTotal enriched: `{new_count}`\nCRM updated automatically."
                    embed = discord.Embed(
                        title=title,
                        description=desc,
                        color=discord.Color.from_rgb(16, 185, 129),
                        timestamp=datetime.utcnow(),
                    )
                    embed.set_footer(text="OutreachBot · Alert System")
                    await ch.send(embed=embed)

            self._enriched_mtime  = mtime
            self._last_lead_count = new_count
        except Exception as e:
            print(f"[AlertSystem] watch_enriched error: {e}")

    @watch_enriched.before_loop
    async def before_watch_enriched(self):
        await self.bot.wait_until_ready()
        if ENRICHED_JSON.exists():
            self._enriched_mtime  = ENRICHED_JSON.stat().st_mtime
            self._last_lead_count = len(load_leads())

    @tasks.loop(seconds=STATE_WATCH_INTERVAL)
    async def watch_pipeline_state(self):
        if not PIPELINE_STATE_JSON.exists():
            return
        try:
            mtime = PIPELINE_STATE_JSON.stat().st_mtime
            if mtime <= self._state_mtime:
                return

            self._state_mtime = mtime
            state = load_pipeline_state()
            ch = await self._get_alerts_channel()
            if not ch:
                return

            # Credit warning
            enrichment  = state.get("enrichment", {})
            apify_bal   = enrichment.get("apify_credits", {}).get("balance", None)
            if apify_bal is not None:
                try:
                    bal = float(apify_bal)
                    if bal < 0.50 and self._last_apify_bal != apify_bal:
                        self._last_apify_bal = apify_bal
                        embed = discord.Embed(
                            title="⚠️ Low Apify Credits",
                            description=(
                                f"Balance: **${bal:.2f}** (< $0.50 threshold)\n"
                                "Enrichment paused automatically.\n\n"
                                "**Action:** Top up at apify.com or wait for monthly reset."
                            ),
                            color=discord.Color.orange(),
                            timestamp=datetime.utcnow(),
                        )
                        await ch.send(embed=embed)
                except (ValueError, TypeError):
                    pass

            # Error detection
            last_error = state.get("last_error")
            if last_error and last_error.get("ts") != getattr(self, "_last_error_ts", None):
                self._last_error_ts = last_error.get("ts")
                embed = discord.Embed(
                    title="❌ Pipeline Error",
                    description=(
                        f"**Script:** `{last_error.get('script','unknown')}`\n"
                        f"**Error:** {last_error.get('message','?')}\n"
                        f"**Leads affected:** {last_error.get('leads_affected', '?')}"
                    ),
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow(),
                )
                embed.set_footer(text="Check #logs for full traceback")
                await ch.send(embed=embed)

            # Validation failure
            failed = state.get("validation", {}).get("needs_review", [])
            last_review_count = getattr(self, "_last_review_count", 0)
            if isinstance(failed, list) and len(failed) > last_review_count:
                self._last_review_count = len(failed)
                new_fails = failed[last_review_count:]
                for fail in new_fails[:3]:
                    lead_name = fail.get("name","?") if isinstance(fail, dict) else str(fail)
                    embed = discord.Embed(
                        title="⚠️ Message Validation Failed",
                        description=(
                            f"**Lead:** {lead_name}\n"
                            f"Retries exhausted — needs manual review.\n"
                            f"Type `!messages {lead_name.split()[0].lower()}` to inspect."
                        ),
                        color=discord.Color.orange(),
                        timestamp=datetime.utcnow(),
                    )
                    await ch.send(embed=embed)

        except Exception as e:
            print(f"[AlertSystem] watch_pipeline_state error: {e}")

    @watch_pipeline_state.before_loop
    async def before_watch_state(self):
        await self.bot.wait_until_ready()
        if PIPELINE_STATE_JSON.exists():
            self._state_mtime = PIPELINE_STATE_JSON.stat().st_mtime

    # ── Manual alert command ──
    @commands.command(name="alert_test")
    async def test_alert(self, ctx: commands.Context):
        """Test the alert system."""
        ch = await self._get_alerts_channel()
        if not ch:
            await ctx.send("❌ DISCORD_ALERTS_CHANNEL_ID not set in .env")
            return
        embed = discord.Embed(
            title="🔔 Alert System Test",
            description="Alert system is working! This channel will receive real-time notifications.",
            color=discord.Color.green(),
            timestamp=datetime.utcnow(),
        )
        await ch.send(embed=embed)
        await ctx.send("✅ Test alert sent to alerts channel.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AlertSystem(bot))
