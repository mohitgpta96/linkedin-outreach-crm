"""
Daily summary digest — posts to #daily-summary at 8:00 AM IST (2:30 UTC).
"""
from __future__ import annotations
import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timezone, timedelta
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from discord_bot.utils.pipeline_bridge import (
    load_leads, load_pipeline_state, get_today_tasks, filter_leads,
)
from discord_bot.utils.formatters import TIER_EMOJI

# 8:00 AM IST = 2:30 AM UTC
DAILY_TIME = time(hour=2, minute=30, tzinfo=timezone.utc)

TIPS = [
    "Connection requests with post references get 35-40% accept rate vs 15-20% without. Check recent posts before sending.",
    "Follow up adds value in each message — never send 'just checking in'. Use a new observation or question.",
    "Best time to send connection requests: Tuesday–Thursday, 10 AM–12 PM local time.",
    "Voice notes get 3x more replies than text DMs on LinkedIn. Consider for Day 6 follow-up.",
    "Founders at YC companies typically check LinkedIn on Tuesday–Wednesday mornings.",
    "Personalisation = 1 specific observation + 1 genuine question. Keep it under 40 words for connections.",
    "'What does sprint planning look like at [company]?' is the highest-performing opener for PM outreach.",
    "Accept rate of 30%+ means your ICP targeting is correct. Below 20% — review your connection note.",
]


def build_summary_embed() -> discord.Embed:
    from random import choice
    leads       = load_leads()
    state       = load_pipeline_state()
    tasks_data  = get_today_tasks()
    today_str   = datetime.now().strftime("%B %d, %Y")

    # Stage counts
    stage_counts = {}
    tier_counts  = {}
    for l in leads:
        s = l.get("outreach_stage","new")
        t = str(l.get("pm_demand_tier","WARM")).upper()
        stage_counts[s] = stage_counts.get(s, 0) + 1
        tier_counts[t]  = tier_counts.get(t, 0) + 1

    enrichment  = state.get("enrichment", {})
    apify_bal   = enrichment.get("apify_credits", {}).get("balance","?")
    groq_tok    = enrichment.get("groq_tokens_today", 0)
    feedback    = state.get("feedback", {})
    accept_rate = feedback.get("accept_rate", 0)
    reply_rate  = feedback.get("reply_rate", 0)

    warmup_count  = len(tasks_data["warmup_needed"])
    ready_count   = len(tasks_data["ready_to_send"])
    followup_count= len(tasks_data["followup_due"])

    # Pick top lead (highest score, new stage)
    new_leads = [l for l in leads if l.get("outreach_stage","new") == "new"]
    top_lead  = sorted(new_leads, key=lambda l: l.get("icp_priority_score",0), reverse=True)
    top_lead  = top_lead[0] if top_lead else None

    embed = discord.Embed(
        title=f"☀️ Daily Digest — {today_str}",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow(),
    )

    # Pipeline section
    embed.add_field(
        name="📈 Pipeline",
        value=(
            f"Total leads: `{len(leads)}`\n"
            f"Enriched: `{len(leads)}`\n"
            f"Ready to send: `{stage_counts.get('new',0)}`\n"
            f"Warming up: `{stage_counts.get('warming_up',0)}`\n"
            f"Connected: `{stage_counts.get('connected',0)}`\n"
            f"Credits: Apify `${apify_bal}` · Groq `{groq_tok:,}/100k`"
        ),
        inline=True,
    )

    # Outreach section
    sent_total = feedback.get("total_sent", 0)
    embed.add_field(
        name="📤 Outreach",
        value=(
            f"Total sent: `{sent_total}`\n"
            f"Accept rate: `{accept_rate:.0%}`\n"
            f"Reply rate: `{reply_rate:.0%}`\n"
            f"Meetings: `{stage_counts.get('meeting',0)}`\n"
            f"Replied: `{stage_counts.get('replied',0)}`"
        ),
        inline=True,
    )

    # Today's tasks
    task_lines = []
    if warmup_count:  task_lines.append(f"🌡️ `{warmup_count}` leads need warm-up")
    if ready_count:   task_lines.append(f"🟢 `{ready_count}` ready to send connection request")
    if followup_count:task_lines.append(f"🔵 `{followup_count}` follow-ups due")
    if not task_lines: task_lines = ["Nothing scheduled — enrich more leads with `!pipeline run enrich 5`"]

    embed.add_field(
        name="📋 Today's Tasks",
        value="\n".join(task_lines),
        inline=False,
    )

    # Top lead suggestion
    if top_lead:
        t_name = top_lead.get("name","?")
        t_comp = top_lead.get("company","?")
        t_score= top_lead.get("icp_priority_score","?")
        t_tier = str(top_lead.get("pm_demand_tier","WARM")).upper()
        t_src  = top_lead.get("source","?")
        t_emoji= TIER_EMOJI.get(t_tier,"📊")
        embed.add_field(
            name="🎯 Suggested Focus",
            value=(
                f"**{t_name}** ({t_comp})\n"
                f"Score: `{t_score}` · {t_emoji} {t_tier} · {t_src}\n"
                f"Reason: Highest ICP score, ready to send\n"
                f"Type `!lead {t_name.split()[0].lower()}` to review"
            ),
            inline=False,
        )

    embed.add_field(
        name="💡 Tip of the Day",
        value=choice(TIPS),
        inline=False,
    )
    embed.set_footer(text="Type !today in #bot-commands for detailed task list")
    return embed


class DailySummary(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._channel: discord.TextChannel | None = None
        self.daily_post.start()

    def cog_unload(self):
        self.daily_post.cancel()

    async def _get_channel(self) -> discord.TextChannel | None:
        if self._channel:
            return self._channel
        ch_id = os.getenv("DISCORD_DAILY_SUMMARY_CHANNEL_ID")
        if ch_id:
            ch = self.bot.get_channel(int(ch_id))
            if ch:
                self._channel = ch
                return ch
        return None

    @tasks.loop(time=DAILY_TIME)
    async def daily_post(self):
        ch = await self._get_channel()
        if not ch:
            print("[DailySummary] No channel configured — set DISCORD_DAILY_SUMMARY_CHANNEL_ID")
            return
        try:
            embed = build_summary_embed()
            await ch.send(embed=embed)
        except Exception as e:
            print(f"[DailySummary] Error posting: {e}")

    @daily_post.before_loop
    async def before_daily(self):
        await self.bot.wait_until_ready()

    # Manual trigger for testing
    @commands.command(name="daily")
    async def trigger_daily(self, ctx: commands.Context):
        """Manually trigger the daily summary (for testing)."""
        embed = build_summary_embed()
        await ctx.send(embed=embed)

        # Also post to the actual channel if configured
        ch = await self._get_channel()
        if ch and ch != ctx.channel:
            await ch.send(embed=build_summary_embed())
            await ctx.send(f"✅ Also posted to {ch.mention}")


async def setup(bot: commands.Bot):
    await bot.add_cog(DailySummary(bot))
