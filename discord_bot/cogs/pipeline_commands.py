"""
Pipeline control commands for OutreachBot.
Commands: !pipeline run/status/credits/stop/dry-run/filter/qualify
"""
from __future__ import annotations
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from discord_bot.utils.pipeline_bridge import (
    run_pipeline_command, get_credit_info, load_pipeline_state, load_leads,
)
from discord_bot.utils.formatters import pipeline_status_embed, alert_embed

_running_process: asyncio.subprocess.Process | None = None


class PipelineCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._stop_flag = False

    @commands.group(name="pipeline", invoke_without_command=True)
    async def pipeline(self, ctx: commands.Context):
        """Pipeline command group. Use !pipeline run/status/credits/stop"""
        await ctx.send(embed=discord.Embed(
            title="⚙️ Pipeline Commands",
            description=(
                "`!pipeline run [mode] [batch]` — run pipeline\n"
                "`!pipeline status` — show current state\n"
                "`!pipeline credits` — quick credit check\n"
                "`!pipeline stop` — emergency stop\n"
                "`!pipeline dry-run` — simulate (no API calls)\n"
                "`!pipeline filter` — ICP filter only\n"
                "`!pipeline qualify` — qualification only\n\n"
                "**Modes:** full · enrich · discover · filter · signals · qualify"
            ),
            color=discord.Color.blue(),
        ))

    @pipeline.command(name="run")
    async def pipeline_run(self, ctx: commands.Context, mode: str = "enrich", batch: int = 5):
        """Run pipeline. !pipeline run [mode] [batch_size]"""
        mode_map = {
            "enrich":   "enrich_only",
            "full":     "full",
            "discover": "discover_only",
            "filter":   "filter_only",
            "signals":  "signals_only",
            "qualify":  "qualify_only",
        }
        mode_key = mode_map.get(mode.lower(), mode.lower())

        self._stop_flag = False

        embed = discord.Embed(
            title=f"🚀 Pipeline Started — {mode.title()} mode ({batch} leads)",
            color=discord.Color.green(),
        )
        embed.add_field(name="Mode", value=f"`{mode_key}`", inline=True)
        embed.add_field(name="Batch", value=f"`{batch}`", inline=True)
        status_msg = await ctx.send(embed=embed)

        lines_collected = []

        async def stream_to_discord(line: str):
            if self._stop_flag:
                return
            lines_collected.append(line)
            # Update embed with last 8 lines
            display = "\n".join(lines_collected[-8:])
            if len(display) > 1000:
                display = "...\n" + "\n".join(lines_collected[-5:])
            try:
                up_embed = discord.Embed(
                    title=f"🚀 Running — {mode.title()} ({batch} leads)",
                    description=f"```{display}```",
                    color=discord.Color.blue(),
                )
                await status_msg.edit(embed=up_embed)
            except discord.HTTPException:
                pass

        returncode = await run_pipeline_command(mode_key, batch, callback=stream_to_discord)

        # Final embed
        if self._stop_flag:
            final = discord.Embed(title="⏹️ Pipeline stopped.", color=discord.Color.red())
        elif returncode == 0:
            leads = load_leads()
            final = discord.Embed(
                title="✅ Pipeline Complete",
                description=f"Mode: `{mode_key}` | Batch: `{batch}`\nTotal enriched: `{len(leads)}`",
                color=discord.Color.green(),
            )
            final.set_footer(text="CRM updated automatically. !stats to see summary.")
        else:
            final = discord.Embed(
                title="❌ Pipeline Error",
                description=f"Exit code: `{returncode}`\nCheck #logs for details.",
                color=discord.Color.red(),
            )
            final.add_field(name="Last output", value=f"```{'  '.join(lines_collected[-3:])}```", inline=False)

        await status_msg.edit(embed=final)

    @pipeline.command(name="status")
    async def pipeline_status(self, ctx: commands.Context):
        """Show current pipeline state."""
        state = load_pipeline_state()
        if not state:
            await ctx.send(embed=discord.Embed(
                title="📊 Pipeline Status",
                description="No pipeline_state.json found. Run the pipeline first.",
                color=discord.Color.orange(),
            ))
            return
        await ctx.send(embed=pipeline_status_embed(state))

    @pipeline.command(name="credits")
    async def pipeline_credits(self, ctx: commands.Context):
        """Quick credit check."""
        info = await get_credit_info()
        embed = discord.Embed(title="💰 Credits", color=discord.Color.gold())
        embed.add_field(name="Apify",        value=f"`${info['apify_balance']}`",         inline=True)
        embed.add_field(name="Groq tokens",  value=f"`{info['groq_tokens']:,}/100,000`",  inline=True)
        embed.add_field(name="Daily spend",  value=f"`${info['daily_spend']:.2f}/$2.00`", inline=True)
        embed.add_field(name="Can enrich",   value=f"~`{info['can_enrich']}` more leads @ $0.08/lead", inline=False)
        await ctx.send(embed=embed)

    @pipeline.command(name="stop")
    async def pipeline_stop(self, ctx: commands.Context):
        """Emergency stop."""
        self._stop_flag = True
        # Also kill any running subprocess
        try:
            import subprocess
            subprocess.run(["pkill", "-f", "run_pipeline.py"], check=False)
        except Exception:
            pass
        await ctx.send(embed=discord.Embed(
            title="⏹️ Pipeline Stopped",
            description="Stop flag set. Any running process will terminate after current step.",
            color=discord.Color.red(),
        ))

    @pipeline.command(name="dry-run")
    async def pipeline_dry_run(self, ctx: commands.Context, mode: str = "full"):
        """Dry run — no API calls, no cost."""
        await ctx.send(embed=discord.Embed(
            title="🧪 Dry Run Starting...",
            description=f"Mode: `{mode}` | No API calls will be made.",
            color=discord.Color.blue(),
        ))
        lines = []
        async def cb(line): lines.append(line)
        returncode = await run_pipeline_command(mode, dry_run=True, callback=cb)
        await ctx.send(embed=discord.Embed(
            title="🧪 Dry Run Complete",
            description=f"```{'  '.join(lines[-10:])}```" if lines else "No output",
            color=discord.Color.green() if returncode == 0 else discord.Color.red(),
        ))

    @pipeline.command(name="filter")
    async def pipeline_filter(self, ctx: commands.Context):
        """Run ICP filter only."""
        msg = await ctx.send(embed=discord.Embed(title="🔍 Running ICP filter...", color=discord.Color.blue()))
        lines = []
        async def cb(line): lines.append(line)
        rc = await run_pipeline_command("filter_only", callback=cb)
        await msg.edit(embed=discord.Embed(
            title="✅ Filter complete" if rc == 0 else "❌ Filter failed",
            description=f"```{'  '.join(lines[-6:])}```" if lines else "",
            color=discord.Color.green() if rc == 0 else discord.Color.red(),
        ))

    @pipeline.command(name="qualify")
    async def pipeline_qualify(self, ctx: commands.Context):
        """Run qualification step only."""
        msg = await ctx.send(embed=discord.Embed(title="🎯 Running qualification...", color=discord.Color.blue()))
        lines = []
        async def cb(line): lines.append(line)
        rc = await run_pipeline_command("qualify_only", callback=cb)
        await msg.edit(embed=discord.Embed(
            title="✅ Qualification complete" if rc == 0 else "❌ Failed",
            description=f"```{'  '.join(lines[-6:])}```" if lines else "",
            color=discord.Color.green() if rc == 0 else discord.Color.red(),
        ))

    # ── Slash command versions ──

    @app_commands.command(name="pipeline_status", description="Show pipeline status")
    async def slash_status(self, interaction: discord.Interaction):
        state = load_pipeline_state()
        await interaction.response.send_message(embed=pipeline_status_embed(state) if state else discord.Embed(
            title="No state found", description="Run the pipeline first.", color=discord.Color.orange()
        ))

    @app_commands.command(name="pipeline_credits", description="Quick credit check")
    async def slash_credits(self, interaction: discord.Interaction):
        info = await get_credit_info()
        embed = discord.Embed(title="💰 Credits", color=discord.Color.gold())
        embed.add_field(name="Apify",       value=f"`${info['apify_balance']}`",        inline=True)
        embed.add_field(name="Groq tokens", value=f"`{info['groq_tokens']:,}/100,000`", inline=True)
        embed.add_field(name="Can enrich",  value=f"~`{info['can_enrich']}` leads",     inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PipelineCommands(bot))
