"""
Lead management commands for OutreachBot.
Commands: !lead !leads !messages !advance !skip !warmup !note !today !stats !search
"""
from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from discord_bot.utils.pipeline_bridge import (
    find_lead, filter_leads, advance_lead_stage, skip_lead,
    add_note, mark_warmup_done, search_leads, get_today_tasks, load_leads,
    load_pipeline_state,
)
from discord_bot.utils.formatters import (
    lead_embed, leads_list_embed, messages_embed, stats_embed,
)

STAGE_EMOJI = {
    "new":"🆕","warming_up":"🌡️","requested":"📤",
    "connected":"🤝","replied":"💬","meeting":"📅","done":"✅","skipped":"⏭️",
}
NEXT_STEPS = {
    "new":         ["☐ Day 1: View profile + follow company","☐ Day 2: Like 1-2 posts","☐ Day 3: Comment on a post","☐ Day 4: Send connection request"],
    "warming_up":  ["☐ Complete warm-up (Day 1-4)","☐ Day 4: Send connection request"],
    "requested":   ["☐ Wait for acceptance","☐ After accept → send first DM (Day 6)"],
    "connected":   ["☐ Send followup_day2 message","☐ Type !messages [name] 2 to see it"],
    "replied":     ["☐ Respond thoughtfully","☐ Ask for 15-min call"],
    "meeting":     ["☐ Prepare for call","☐ Send agenda 24h before"],
}


class LeadCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── !lead [name] ──
    @commands.command(name="lead")
    async def lead_detail(self, ctx: commands.Context, *, name: str):
        """Show full lead detail."""
        lead = find_lead(name)
        if not lead:
            await ctx.send(embed=discord.Embed(
                title=f"❌ Lead not found: '{name}'",
                description="Try `!search [query]` or `!leads` for full list.",
                color=discord.Color.red(),
            ))
            return
        await ctx.send(embed=lead_embed(lead))

    # ── !leads [filter] ──
    @commands.command(name="leads")
    async def leads_list(self, ctx: commands.Context, f: str = "all"):
        """List leads. Filters: all/ready/enriched/hot/strong/warm/warming/contacted/replied/meeting/done"""
        leads = filter_leads(f)
        label = f.replace("_"," ").title()
        await ctx.send(embed=leads_list_embed(leads, label))

    # ── !messages [name] [number] ──
    @commands.command(name="messages", aliases=["msgs"])
    async def lead_messages(self, ctx: commands.Context, name: str, msg_num: int = None):
        """Show messages for a lead. !messages arya 1 for specific message."""
        lead = find_lead(name)
        if not lead:
            await ctx.send(f"❌ Lead not found: `{name}`")
            return
        embeds = messages_embed(lead, msg_num)
        for e in embeds[:3]:      # Discord allows max 10 embeds per message but let's be safe
            await ctx.send(embed=e)
        if len(embeds) > 3:
            for e in embeds[3:]:
                await ctx.send(embed=e)

    # ── !advance [name] [stage] ──
    @commands.command(name="advance", aliases=["move"])
    async def advance_stage(self, ctx: commands.Context, name: str, stage: str = None):
        """Advance lead to next stage (or specific stage)."""
        lead, old, new = advance_lead_stage(name, stage)
        if not lead:
            await ctx.send(f"❌ Lead not found: `{name}`")
            return

        old_e = STAGE_EMOJI.get(old, "📋")
        new_e = STAGE_EMOJI.get(new, "📋")
        steps = NEXT_STEPS.get(new, [])

        embed = discord.Embed(
            title=f"🔄 Stage Change — {lead.get('name')}",
            color=discord.Color.green(),
        )
        embed.add_field(name="From", value=f"{old_e} `{old}`", inline=True)
        embed.add_field(name="→ To", value=f"{new_e} `{new}`", inline=True)
        if steps:
            embed.add_field(name="Next Steps", value="\n".join(steps), inline=False)
        if new == "connected":
            embed.add_field(
                name="📊 Feedback",
                value="Accept captured. Rate updated in pipeline_state.json",
                inline=False,
            )
            embed.set_footer(text="Type !messages [name] 2 to see the first DM to send.")
        await ctx.send(embed=embed)

    # ── !skip [name] [reason] ──
    @commands.command(name="skip")
    async def skip_lead_cmd(self, ctx: commands.Context, name: str, *, reason: str = ""):
        """Skip/reject a lead."""
        lead = skip_lead(name, reason)
        if not lead:
            await ctx.send(f"❌ Lead not found: `{name}`")
            return
        await ctx.send(embed=discord.Embed(
            title=f"⏭️ Skipped — {lead.get('name')} ({lead.get('company')})",
            description=f"Reason: {reason or 'not specified'}\nStage → `skipped`",
            color=discord.Color.greyple(),
        ))

    # ── !warmup [name] done [day] ──
    @commands.command(name="warmup")
    async def warmup_done(self, ctx: commands.Context, name: str, action: str = "done", day: int = 1):
        """Mark warm-up step complete. !warmup arya done 1"""
        if action.lower() != "done":
            await ctx.send("Usage: `!warmup [name] done [day_number]`")
            return
        lead = mark_warmup_done(name, day)
        if not lead:
            await ctx.send(f"❌ Lead not found: `{name}`")
            return

        WARMUP_STEPS = {
            1: "View profile + follow company",
            2: "Like 1-2 recent posts",
            3: "Leave thoughtful comment",
            4: "Send connection request",
        }
        completed = lead.get("warmup_completed", [])
        lines = []
        for d in range(1, 5):
            done = d in completed
            icon = "☑" if done else "☐"
            lines.append(f"{icon} Day {d}: {WARMUP_STEPS[d]}")

        embed = discord.Embed(
            title=f"✅ Warm-up Day {day} — {lead.get('name')}",
            description="\n".join(lines),
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Progress: {len(completed)}/4 steps done")
        await ctx.send(embed=embed)

    # ── !note [name] [text] ──
    @commands.command(name="note")
    async def add_note_cmd(self, ctx: commands.Context, name: str, *, text: str):
        """Add a note to a lead."""
        lead = add_note(name, text)
        if not lead:
            await ctx.send(f"❌ Lead not found: `{name}`")
            return
        await ctx.send(embed=discord.Embed(
            title=f"📝 Note added — {lead.get('name')} ({lead.get('company')})",
            description=f"```{text}```",
            color=discord.Color.blurple(),
        ))

    # ── !today ──
    @commands.command(name="today")
    async def today_tasks(self, ctx: commands.Context):
        """Show today's outreach tasks."""
        from datetime import datetime
        tasks = get_today_tasks()
        warmup  = tasks["warmup_needed"]
        ready   = tasks["ready_to_send"]
        followup= tasks["followup_due"]

        sent_today = len(filter_leads("contacted"))

        embed = discord.Embed(
            title=f"📋 Today's Tasks — {datetime.now().strftime('%B %d, %Y')}",
            color=discord.Color.blurple(),
        )

        if warmup:
            lines = [f"• **{l['name']}** — Day {l.get('_next_warmup_day','?')} ({l.get('_next_warmup_action','')})" for l in warmup[:5]]
            embed.add_field(name=f"🌡️ Warm-up needed ({len(warmup)})", value="\n".join(lines), inline=False)

        if ready:
            lines = [f"• **{l['name']}** ({l['company']}) — warm-up complete ✅" for l in ready[:5]]
            embed.add_field(name=f"🟢 Send connection request ({len(ready)})", value="\n".join(lines), inline=False)

        if followup:
            lines = [f"• **{l['name']}** — {l.get('outreach_stage','')}" for l in followup[:5]]
            embed.add_field(name=f"🔵 Follow-up due ({len(followup)})", value="\n".join(lines), inline=False)

        if not (warmup or ready or followup):
            embed.description = "Nothing scheduled for today. Type `!leads` to see all leads."

        embed.add_field(name="📤 Sent today", value=f"`{sent_today}/15`", inline=True)
        embed.set_footer(text="Type !advance [name] to update stage after action")
        await ctx.send(embed=embed)

    # ── !search [query] ──
    @commands.command(name="search")
    async def search_cmd(self, ctx: commands.Context, *, query: str):
        """Search across all leads."""
        results = search_leads(query)
        embed = discord.Embed(
            title=f"🔍 Search: \"{query}\" — {len(results)} result(s)",
            color=discord.Color.blurple(),
        )
        if not results:
            embed.description = "No leads found. Try a different query."
        else:
            lines = []
            for l in results[:10]:
                name    = l.get("name","—")
                company = l.get("company","—")
                score   = l.get("icp_priority_score","—")
                tier    = l.get("pm_demand_tier","WARM")
                stage   = l.get("outreach_stage","new")
                from discord_bot.utils.formatters import TIER_EMOJI
                t_emoji = TIER_EMOJI.get(tier.upper(),"📊")
                lines.append(f"{t_emoji} **{name}** · {company} · `{score}` · `{stage}`")
            embed.description = "\n".join(lines)
            if results:
                embed.set_footer(text=f"Type !lead [name] for details")
        await ctx.send(embed=embed)

    # ── !stats ──
    @commands.command(name="stats")
    async def crm_stats(self, ctx: commands.Context):
        """Quick CRM stats."""
        leads = load_leads()
        state = load_pipeline_state()
        await ctx.send(embed=stats_embed(leads, state))

    # ── /lead slash command ──
    @app_commands.command(name="lead", description="View lead details")
    async def slash_lead(self, interaction: discord.Interaction, name: str):
        lead = find_lead(name)
        if not lead:
            await interaction.response.send_message(f"❌ Lead not found: `{name}`", ephemeral=True)
            return
        await interaction.response.send_message(embed=lead_embed(lead))

    @app_commands.command(name="stats", description="Show CRM stats")
    async def slash_stats(self, interaction: discord.Interaction):
        leads = load_leads()
        state = load_pipeline_state()
        await interaction.response.send_message(embed=stats_embed(leads, state))

    @app_commands.command(name="today", description="Today's outreach tasks")
    async def slash_today(self, interaction: discord.Interaction):
        from datetime import datetime
        tasks = get_today_tasks()
        lines = []
        if tasks["warmup_needed"]:
            lines.append(f"🌡️ Warm-up: {len(tasks['warmup_needed'])} leads")
        if tasks["ready_to_send"]:
            lines.append(f"🟢 Ready to send: {len(tasks['ready_to_send'])} leads")
        if tasks["followup_due"]:
            lines.append(f"🔵 Follow-up due: {len(tasks['followup_due'])} leads")
        if not lines:
            lines = ["Nothing scheduled today."]
        embed = discord.Embed(
            title=f"📋 Today — {datetime.now().strftime('%B %d')}",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LeadCommands(bot))
