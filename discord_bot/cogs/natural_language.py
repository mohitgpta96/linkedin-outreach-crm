"""
Natural language command parser — Groq-powered.
Handles English + Hinglish (Hindi + English mix).
Mohit can type naturally in any channel, bot understands intent.
"""
from __future__ import annotations
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import discord
from discord.ext import commands

GROQ_API_KEY = os.getenv("GROQ_API_KEY","")

SYSTEM_PROMPT = """You are a command parser for a LinkedIn outreach CRM bot called OutreachBot.

The user (Mohit) speaks in English OR Hinglish (Hindi + English mix).
Parse the message into a structured JSON command.

Available commands:
- pipeline_run: {mode: full|enrich|discover|filter|signals|qualify, batch_size: int}
- pipeline_status: {}
- pipeline_credits: {}
- pipeline_stop: {}
- lead_view: {name: str}
- lead_messages: {name: str, msg_num: int|null}
- lead_advance: {name: str, target_stage: str|null}
- lead_skip: {name: str, reason: str}
- lead_search: {query: str}
- leads_list: {filter: all|new|ready|enriched|warming|contacted|replied|hot|strong|warm}
- today_tasks: {}
- stats: {}
- warmup_done: {name: str, day: int}
- add_note: {name: str, note: str}
- daily_summary: {}
- help: {}
- unknown: {}

Hinglish examples:
- "kitni leads hain?" → stats
- "kitni leads enriched hain?" → stats
- "arya ka message dikhao" → lead_messages with name=arya
- "5 leads enrich karo" → pipeline_run with mode=enrich, batch_size=5
- "aaj kya karna hai?" → today_tasks
- "etai ko connected mark karo" → lead_advance with name=etai, target_stage=connected
- "pipeline band karo" → pipeline_stop
- "status dikhao" → pipeline_status
- "arya ki details" → lead_view with name=arya

Return ONLY JSON, no explanation:
{"command": "...", "args": {...}}"""


NL_MODELS = [
    "llama-3.1-8b-instant",
    "llama3-groq-8b-8192-tool-use-preview",
    "llama3-groq-70b-8192-tool-use-preview",
    "llama-3.3-70b-versatile",
]


async def parse_with_groq(text: str) -> dict:
    """Call Groq API to parse natural language. Auto-cascades through models on 429."""
    if not GROQ_API_KEY:
        return {"command": "unknown", "args": {}}
    import aiohttp
    for model in NL_MODELS:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user",   "content": text},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 200,
                    },
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    if resp.status == 429:
                        print(f"[NL] {model} rate-limited, trying next...")
                        continue
                    if resp.status != 200:
                        return {"command": "unknown", "args": {}}
                    data = await resp.json()
                    raw = data["choices"][0]["message"]["content"].strip()
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    if match:
                        return json.loads(match.group())
        except Exception as e:
            print(f"[NL] {model} error: {e}")
            continue
    return {"command": "unknown", "args": {}}


# Rule-based fallback (no API needed for common patterns)
def parse_rule_based(text: str) -> dict | None:
    t = text.lower().strip()

    # Lead list filters
    if any(x in t for x in ["new leads","nayi leads","naye leads","show leads","dikhao leads","leads dikhao","all leads","saari leads"]):
        if any(x in t for x in ["new","nayi","naye"]) and "all" not in t and "saar" not in t:
            return {"command": "leads_list", "args": {"filter": "new"}}
        return {"command": "leads_list", "args": {"filter": "all"}}

    # Stats / counts
    if any(x in t for x in ["kitni leads","how many leads","stats","kitna","count"]):
        return {"command": "stats", "args": {}}

    # Today's tasks
    if any(x in t for x in ["aaj kya","today","kya karna","tasks"]):
        return {"command": "today_tasks", "args": {}}

    # Pipeline status
    if any(x in t for x in ["status","pipeline status","kya chal raha"]):
        return {"command": "pipeline_status", "args": {}}

    # Pipeline stop
    if any(x in t for x in ["band karo","stop pipeline","pipeline stop","ruk jao"]):
        return {"command": "pipeline_stop", "args": {}}

    # Credits
    if any(x in t for x in ["credits","credit","apify","kitne paise","balance"]):
        return {"command": "pipeline_credits", "args": {}}

    # Enrich N leads
    match = re.search(r'(\d+)\s*(leads?|log)?\s*(enrich|enrichment|karo)', t)
    if match or ("enrich" in t and any(c.isdigit() for c in t)):
        n = int(match.group(1)) if match else 5
        return {"command": "pipeline_run", "args": {"mode": "enrich", "batch_size": n}}

    # Stage advancement — "X ko Y mark karo"
    stage_map = {
        "connected":"connected","warming":"warming_up","warm up":"warming_up",
        "requested":"requested","replied":"replied","meeting":"meeting","done":"done",
    }
    for stage_kw, stage_val in stage_map.items():
        if stage_kw in t:
            # Try to extract name
            name_match = re.match(r'^(\w+)\s+ko', t) or re.match(r'^move\s+(\w+)', t)
            if name_match:
                return {"command": "lead_advance", "args": {"name": name_match.group(1), "target_stage": stage_val}}

    return None


# Hinglish response builder
def hinglish_header(cmd: str) -> str:
    messages = {
        "stats":           "📊 Ye raha summary:",
        "today_tasks":     "📋 Aaj ka kaam:",
        "pipeline_status": "📊 Pipeline status:",
        "pipeline_credits":"💰 Credits ka haal:",
        "pipeline_run":    "🚀 Pipeline chalu kar raha hoon...",
        "lead_view":       "👤 Lead details:",
        "lead_messages":   "💬 Messages ready hain:",
        "lead_advance":    "🔄 Stage change ho gaya:",
        "unknown":         "🤔 Samjha nahi — type `!help` for commands.",
    }
    return messages.get(cmd, "⚙️ Processing...")


class NaturalLanguage(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.content.startswith("!") or message.content.startswith("/"):
            return  # Let prefix commands handle it

        # Only respond in bot-commands or general channels
        allowed_channels = []
        for env_key in ("DISCORD_COMMANDS_CHANNEL_ID", "DISCORD_GENERAL_CHANNEL_ID"):
            ch_id = os.getenv(env_key)
            if ch_id:
                allowed_channels.append(int(ch_id))

        if allowed_channels and message.channel.id not in allowed_channels:
            return

        text = message.content.strip()
        if len(text) < 3:
            return

        # Try rule-based first (faster, no API)
        parsed = parse_rule_based(text)
        if not parsed and GROQ_API_KEY:
            async with message.channel.typing():
                parsed = await parse_with_groq(text)

        if not parsed or parsed.get("command") == "unknown":
            return  # Ignore unknown — don't spam

        cmd  = parsed["command"]
        args = parsed.get("args", {})

        # Dispatch to appropriate command function
        ctx = await self.bot.get_context(message)
        header = hinglish_header(cmd)

        try:
            if cmd == "stats":
                await message.channel.send(header)
                await ctx.invoke(self.bot.get_command("stats"))

            elif cmd == "today_tasks":
                await message.channel.send(header)
                await ctx.invoke(self.bot.get_command("today"))

            elif cmd == "pipeline_status":
                await message.channel.send(header)
                await ctx.invoke(self.bot.get_command("pipeline status"))

            elif cmd == "pipeline_credits":
                await message.channel.send(header)
                await ctx.invoke(self.bot.get_command("pipeline credits"))

            elif cmd == "pipeline_stop":
                await ctx.invoke(self.bot.get_command("pipeline stop"))

            elif cmd == "pipeline_run":
                mode       = args.get("mode","enrich")
                batch_size = int(args.get("batch_size", 5))
                await message.channel.send(f"🚀 Samjha: **{mode}** mode, **{batch_size}** leads. Chalu karta hoon...")
                pipeline_cog = self.bot.cogs.get("PipelineCommands")
                if pipeline_cog:
                    await pipeline_cog.pipeline_run(ctx, mode, batch_size)

            elif cmd == "lead_view":
                name = args.get("name","")
                if name:
                    await message.channel.send(header)
                    await ctx.invoke(self.bot.get_command("lead"), name=name)

            elif cmd == "lead_messages":
                name    = args.get("name","")
                msg_num = args.get("msg_num")
                if name:
                    await message.channel.send(header)
                    lead_cog = self.bot.cogs.get("LeadCommands")
                    if lead_cog:
                        await lead_cog.lead_messages(ctx, name, msg_num)

            elif cmd == "lead_advance":
                name  = args.get("name","")
                stage = args.get("target_stage")
                if name:
                    await ctx.invoke(self.bot.get_command("advance"), name=name, stage=stage or "")

            elif cmd == "leads_list":
                f = args.get("filter","all")
                await message.channel.send(header)
                await ctx.invoke(self.bot.get_command("leads"), f=f)

            elif cmd == "daily_summary":
                await ctx.invoke(self.bot.get_command("daily"))

        except Exception as e:
            print(f"[NL] Dispatch error for '{cmd}': {e}")

    @commands.command(name="nl_test")
    async def test_nl(self, ctx: commands.Context, *, text: str):
        """Test natural language parsing. !nl_test kitni leads enriched hain?"""
        parsed = parse_rule_based(text)
        if not parsed and GROQ_API_KEY:
            parsed = await parse_with_groq(text)
        await ctx.send(embed=discord.Embed(
            title=f"🧪 NL Parse: \"{text}\"",
            description=f"```json\n{json.dumps(parsed, indent=2)}\n```",
            color=discord.Color.blurple(),
        ))


async def setup(bot: commands.Bot):
    await bot.add_cog(NaturalLanguage(bot))
