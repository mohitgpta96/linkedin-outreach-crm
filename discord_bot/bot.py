"""
OutreachBot — LinkedIn Pipeline Command Center
Main bot entry point.
"""
import asyncio
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states     = True
intents.members          = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    description="OutreachBot — LinkedIn Pipeline Command Center",
    help_command=commands.DefaultHelpCommand(no_category="Commands"),
)

COGS = [
    "discord_bot.cogs.pipeline_commands",
    "discord_bot.cogs.lead_commands",
    "discord_bot.cogs.alert_system",
    "discord_bot.cogs.daily_summary",
    "discord_bot.cogs.natural_language",
    "discord_bot.cogs.voice_controller",
]


ENV_PATH = Path(__file__).parent.parent / ".env"

# Channels to auto-create: (env_key, channel_name, is_voice)
CHANNELS_SPEC = [
    ("DISCORD_ALERTS_CHANNEL_ID",        "alerts",         False),
    ("DISCORD_DAILY_SUMMARY_CHANNEL_ID", "daily-summary",  False),
    ("DISCORD_LEAD_UPDATES_CHANNEL_ID",  "lead-updates",   False),
    ("DISCORD_LOGS_CHANNEL_ID",          "logs",           False),
    ("DISCORD_COMMANDS_CHANNEL_ID",      "bot-commands",   False),
    ("DISCORD_VOICE_CHANNEL_ID",         "voice-control",  True),
]


async def _setup_channels(guild: discord.Guild):
    """Create missing bot channels and write IDs to .env."""
    env_text = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    updated = False

    existing_text = {ch.name for ch in guild.channels}

    for env_key, ch_name, is_voice in CHANNELS_SPEC:
        # Skip if already configured with a valid channel ID (numeric)
        existing_val = os.getenv(env_key, "").strip()
        if existing_val and existing_val.isdigit():
            continue
        # Find or create channel
        existing = discord.utils.get(guild.channels, name=ch_name)
        if existing is None:
            if is_voice:
                existing = await guild.create_voice_channel(ch_name)
            else:
                existing = await guild.create_text_channel(ch_name)
            print(f"  ✓ Created #{ch_name} ({existing.id})")
        else:
            print(f"  ✓ Found #{ch_name} ({existing.id})")

        # Update .env in memory
        ch_id = str(existing.id)
        # Replace the placeholder line
        env_text = env_text.replace(
            f"{env_key}=", f"{env_key}={ch_id}"
        )
        os.environ[env_key] = ch_id
        updated = True

    if updated and ENV_PATH.exists():
        ENV_PATH.write_text(env_text)
        print("  ✓ Channel IDs saved to .env")


@bot.event
async def on_ready():
    print(f"\n{'='*50}")
    print(f"✅ OutreachBot online: {bot.user} (ID: {bot.user.id})")

    # Auto-setup channels in guild
    guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
    if guild_id:
        guild = bot.get_guild(int(guild_id))
        if guild:
            print(f"  Guild: {guild.name}")
            await _setup_channels(guild)
        else:
            print("  ✗ Guild not found — bot may not be in the server yet")

    # Load all cogs
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"  ✓ Loaded: {cog.split('.')[-1]}")
        except Exception as e:
            print(f"  ✗ Failed to load {cog}: {e}")

    # Sync slash commands
    try:
        if guild_id:
            guild_obj = discord.Object(id=int(guild_id))
            synced = await bot.tree.sync(guild=guild_obj)
            print(f"  ✓ Synced {len(synced)} slash commands to guild")
        else:
            synced = await bot.tree.sync()
            print(f"  ✓ Synced {len(synced)} slash commands globally")
    except Exception as e:
        print(f"  ✗ Slash command sync failed: {e}")

    print(f"{'='*50}")
    print(f"  Prefix: !")
    print(f"  Channels configured: {_check_channels()}")
    print(f"  Groq: {'✓ Configured' if os.getenv('GROQ_API_KEY') else '✗ Not set (NL + voice disabled)'}")
    print(f"  Alerts: {'✓ Active' if os.getenv('DISCORD_ALERTS_CHANNEL_ID') else '✗ No channel set'}")
    print(f"{'='*50}\n")
    print("OutreachBot is ready. Type !help in OutreachBot HQ.")


def _check_channels() -> str:
    keys = [
        "DISCORD_ALERTS_CHANNEL_ID",
        "DISCORD_DAILY_SUMMARY_CHANNEL_ID",
        "DISCORD_COMMANDS_CHANNEL_ID",
    ]
    found = sum(1 for k in keys if os.getenv(k))
    return f"{found}/{len(keys)}"


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        # Let NL handler deal with it — don't show error
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`\nType `!help {ctx.command}` for usage.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Bad argument: {error}")
        return
    print(f"[Bot] Command error in {ctx.command}: {error}")


@bot.command(name="help_crm", aliases=["h"])
async def help_crm(ctx: commands.Context):
    """Full command reference."""
    embed = discord.Embed(
        title="⚡ OutreachBot — Command Reference",
        description="Mohit's LinkedIn Outreach Command Center",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="⚙️ Pipeline",
        value=(
            "`!pipeline run [mode] [n]` — run pipeline\n"
            "`!pipeline status` — pipeline state\n"
            "`!pipeline credits` — credit check\n"
            "`!pipeline stop` — emergency stop\n"
            "`!pipeline dry-run` — simulate\n"
            "Modes: full · enrich · filter · qualify · signals"
        ),
        inline=False,
    )
    embed.add_field(
        name="👤 Leads",
        value=(
            "`!lead [name]` — full lead detail\n"
            "`!leads [filter]` — list leads\n"
            "`!messages [name] [num]` — view messages\n"
            "`!advance [name] [stage]` — move stage\n"
            "`!skip [name] [reason]` — skip lead\n"
            "`!warmup [name] done [day]` — mark step done\n"
            "`!note [name] [text]` — add note\n"
            "`!search [query]` — search leads\n"
            "`!today` — today's tasks\n"
            "`!stats` — CRM overview"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔔 Alerts & Reports",
        value=(
            "`!daily` — trigger daily summary\n"
            "`!alert_test` — test alert system\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="🎤 Voice",
        value=(
            "`!join` — bot joins your voice channel\n"
            "`!listen [seconds]` — record voice command\n"
            "`!leave` — bot leaves voice channel\n"
            "`!voice_test [text]` — simulate voice command"
        ),
        inline=False,
    )
    embed.add_field(
        name="🧪 Testing",
        value=(
            "`!nl_test [text]` — test NL parser\n"
            "`!voice_test [text]` — test voice → NL → command"
        ),
        inline=False,
    )
    embed.add_field(
        name="💬 Natural Language",
        value=(
            "Type naturally in any channel:\n"
            "• `kitni leads enriched hain?`\n"
            "• `arya ka message dikhao`\n"
            "• `5 leads enrich karo`\n"
            "• `etai ko connected mark karo`\n"
            "• `aaj kya karna hai?`"
        ),
        inline=False,
    )
    embed.set_footer(text="OutreachBot · Private server · Mohit only")
    await ctx.send(embed=embed)


def run():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ DISCORD_BOT_TOKEN not set in .env")
        print("   Follow discord_bot/setup_guide.md to get your token.")
        sys.exit(1)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    run()
