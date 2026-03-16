"""
OutreachBot Intelligent Agent — Groq-powered agentic loop.

Claude decides what tools to call, executes them autonomously,
streams results back to Discord.
Supports English + Hinglish. Remembers conversation context per channel.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict, deque

import discord
from discord.ext import commands

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from discord_bot.utils.pipeline_bridge import (
    filter_leads, find_lead, advance_lead_stage, skip_lead,
    add_note, mark_warmup_done, search_leads, get_today_tasks, load_leads,
)
from discord_bot.utils.formatters import (
    lead_embed, leads_list_embed, messages_embed, stats_embed,
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Cascade: if a model hits its daily/minute limit, bot auto-retries with the next one.
# All models below support tool calling on Groq free tier.
MODELS = [
    "llama-3.1-8b-instant",                  # 500k TPD — primary, fastest
    "llama3-groq-8b-8192-tool-use-preview",   # separate quota, optimised for tools
    "llama3-groq-70b-8192-tool-use-preview",  # separate quota, smarter fallback
    "llama-3.3-70b-versatile",               # last resort
]

SYSTEM_PROMPT = """You are OutreachBot — an intelligent LinkedIn outreach assistant for Mohit.

Mohit is a freelance Project Manager targeting founders/CEOs of YC-backed startups that need PM help.
He has 33 enriched leads with personalized connection requests ready to send.

You understand English AND Hinglish (Hindi + English mix). Reply in the same language Mohit uses.

Outreach warm-up strategy (Mohit does manually):
- Day 1: View profile + follow company
- Day 2: Like 1-2 posts
- Day 3: Comment on a post
- Day 4: Send connection request
- Day 6+: DMs after acceptance

Lead stages: new → warming_up → requested → connected → replied → meeting → done

Rules:
- Immediately call tools to get things done — never ask for confirmation first
- If Mohit says "usko" / "us lead ko" / "yeh wala" — use the last lead mentioned
- Chain multiple tools if needed to fully complete a task
- Keep text responses SHORT — this is Discord, not a report
- Always confirm what action you took

Examples:
- "arya ka message dikhao" → get_messages(name="arya")
- "etai ko connected mark karo" → advance_stage(name="etai", stage="connected")
- "aaj kya karna hai" → get_today_tasks()
- "kitni leads hain" → get_stats()
- "arya skip karo, not relevant" → skip_lead(name="arya", reason="not relevant")
- "andrew ko note add karo: called him today" → add_note(name="andrew", note="called him today")
- "show me new leads" → list_leads(filter="new")
"""

# Tools in OpenAI/Groq format
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_leads",
            "description": "List leads by stage. filter: 'new'=enriched+ready to send, 'all'=every lead, 'warming'=warming up, 'contacted'=request sent, 'replied', 'meeting', 'done'",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "one of: all, new, warming, contacted, replied, meeting, done",
                        "default": "all"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_lead",
            "description": "Get full profile details for a specific lead by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Lead's first or full name"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_messages",
            "description": "Get personalized outreach messages for a lead (connection request + 6 follow-ups)",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "msg_num": {"type": "integer", "description": "Specific message 1-7, omit for all"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "advance_stage",
            "description": "Move a lead to next or specific stage",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "stage": {
                        "type": "string",
                        "description": "Target stage: warming_up, requested, connected, replied, meeting, done. Omit to auto-advance."
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "skip_lead",
            "description": "Skip or reject a lead with a reason",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "reason": {"type": "string", "default": ""}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": "Add a note to a lead (timestamped automatically)",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "note": {"type": "string"}
                },
                "required": ["name", "note"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "Get overall CRM statistics: total leads, breakdown by stage",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_tasks",
            "description": "Get today's outreach tasks: warm-up actions needed, leads ready to connect, follow-ups due",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_leads",
            "description": "Search leads by name, company, title, or any keyword",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "warmup_done",
            "description": "Mark a warm-up step as completed for a lead",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "day": {"type": "integer", "description": "Day number 1-4"}
                },
                "required": ["name", "day"]
            }
        }
    }
]


# ── Tool execution ─────────────────────────────────────────────────────────────

async def _execute_tool(name: str, args: dict, channel: discord.TextChannel) -> str:
    """Run a tool, send embeds to Discord, return text summary for the model."""
    try:
        if name == "list_leads":
            f = args.get("filter", "all")
            leads = filter_leads(f)
            label = f.replace("_", " ").title()
            await channel.send(embed=leads_list_embed(leads, label))
            return f"Showing {len(leads)} {label} leads."

        elif name == "get_lead":
            lead = find_lead(args["name"])
            if not lead:
                return f"Lead '{args['name']}' not found."
            await channel.send(embed=lead_embed(lead))
            return f"Showing {lead.get('name')} at {lead.get('company')}."

        elif name == "get_messages":
            lead = find_lead(args["name"])
            if not lead:
                return f"Lead '{args['name']}' not found."
            embeds = messages_embed(lead, args.get("msg_num"))
            for e in embeds:
                await channel.send(embed=e)
            return f"Messages for {lead.get('name')} shown ({len(embeds)} messages)."

        elif name == "advance_stage":
            lead, old, new = advance_lead_stage(args["name"], args.get("stage"))
            if not lead:
                return f"Lead '{args['name']}' not found."
            await channel.send(embed=discord.Embed(
                title=f"✅ Stage Updated — {lead.get('name')}",
                description=f"`{old}` → `{new}`\n🏢 {lead.get('company', '—')}",
                color=discord.Color.green(),
            ))
            return f"{lead.get('name')} moved: {old} → {new}."

        elif name == "skip_lead":
            lead = skip_lead(args["name"], args.get("reason", ""))
            if not lead:
                return f"Lead '{args['name']}' not found."
            await channel.send(embed=discord.Embed(
                title=f"⏭️ Skipped — {lead.get('name')} @ {lead.get('company')}",
                description=f"Reason: {args.get('reason') or 'not specified'}",
                color=discord.Color.greyple(),
            ))
            return f"Skipped {lead.get('name')}."

        elif name == "add_note":
            lead = add_note(args["name"], args["note"])
            if not lead:
                return f"Lead '{args['name']}' not found."
            await channel.send(f"📝 Note added to **{lead.get('name')}**: *{args['note']}*")
            return f"Note added to {lead.get('name')}."

        elif name == "get_stats":
            from collections import Counter
            leads = load_leads()
            stages = Counter(l.get("outreach_stage", "new") for l in leads)
            await channel.send(embed=stats_embed(leads))
            return f"Total {len(leads)} leads. Stages: {dict(stages)}"

        elif name == "get_today_tasks":
            tasks    = get_today_tasks()
            warmup   = tasks.get("warmup_needed", [])
            ready    = tasks.get("ready_to_send", [])
            followup = tasks.get("followup_due", [])

            lines = []
            if ready:
                lines.append(f"🆕 **{len(ready)} leads ready to connect**")
                for l in ready[:5]:
                    lines.append(f"  → {l.get('name')} @ {l.get('company')}")
            if warmup:
                lines.append(f"🌡️ **{len(warmup)} warm-up actions needed**")
                for l in warmup[:5]:
                    lines.append(f"  → {l.get('name')}: Day {l.get('_next_warmup_day')} — {l.get('_next_warmup_action','')}")
            if followup:
                lines.append(f"💬 **{len(followup)} follow-ups due**")
                for l in followup[:5]:
                    lines.append(f"  → {l.get('name')} @ {l.get('company')}")
            if not lines:
                lines.append("Aaj koi task nahi — sab clear! ✅")

            await channel.send(embed=discord.Embed(
                title="📋 Aaj Ka Kaam",
                description="\n".join(lines),
                color=discord.Color.green(),
            ))
            return f"{len(ready)} ready, {len(warmup)} warmup, {len(followup)} followup."

        elif name == "search_leads":
            results = search_leads(args["query"])
            await channel.send(embed=leads_list_embed(results, f"🔍 '{args['query']}'"))
            return f"Found {len(results)} results for '{args['query']}'."

        elif name == "warmup_done":
            lead = mark_warmup_done(args["name"], args["day"])
            if not lead:
                return f"Lead '{args['name']}' not found."
            completed = lead.get("warmup_completed", [])
            remaining = [d for d in [1, 2, 3, 4] if d not in completed]
            msg = f"✅ **{lead.get('name')}** — Day {args['day']} warm-up done!"
            if remaining:
                msg += f" Next: Day {remaining[0]}."
            else:
                msg += " 🎉 All 4 days done — send connection request!"
            await channel.send(msg)
            return f"Warmup day {args['day']} done for {lead.get('name')}. Completed: {completed}."

        return f"Unknown tool: {name}"

    except Exception as e:
        return f"Tool '{name}' error: {e}"


# ── Agent Cog ─────────────────────────────────────────────────────────────────

class IntelligentAgent(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Per-channel conversation history (last 20 messages = 10 rounds)
        self.history: dict[int, deque] = defaultdict(lambda: deque(maxlen=20))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.content.startswith("!") or message.content.startswith("/"):
            return

        # Only respond in allowed channels
        allowed = []
        for key in ("DISCORD_COMMANDS_CHANNEL_ID", "DISCORD_GENERAL_CHANNEL_ID"):
            val = os.getenv(key)
            if val:
                allowed.append(int(val))
        if allowed and message.channel.id not in allowed:
            return

        text = message.content.strip()
        if len(text) < 2:
            return

        if not GROQ_API_KEY:
            await message.channel.send("⚠️ GROQ_API_KEY not set — agent disabled.")
            return

        async with message.channel.typing():
            self.history[message.channel.id].append({
                "role": "user",
                "content": text,
            })
            await self._run_agent(message.channel)

    async def _run_agent(self, channel: discord.TextChannel):
        """Agentic loop — model plans, calls tools, responds autonomously.
        Auto-cascades through MODELS on rate-limit (429) errors."""
        from groq import AsyncGroq
        client = AsyncGroq(api_key=GROQ_API_KEY)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(self.history[channel.id])

        # Pick the first model that isn't rate-limited
        active_model = MODELS[0]
        for candidate in MODELS:
            try:
                await client.chat.completions.create(
                    model=candidate,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                )
                active_model = candidate
                break
            except Exception as probe_err:
                if "429" in str(probe_err) or "rate_limit" in str(probe_err).lower():
                    continue   # try next model
                active_model = candidate  # non-rate-limit error — use this model anyway
                break

        MAX_ITERATIONS = 5
        for _ in range(MAX_ITERATIONS):
            try:
                response = await client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    max_tokens=1024,
                    temperature=0.2,
                )
            except Exception as e:
                err = str(e)
                if ("429" in err or "rate_limit" in err.lower()) and active_model != MODELS[-1]:
                    # Current model hit limit mid-conversation — cascade to next
                    idx = MODELS.index(active_model)
                    active_model = MODELS[idx + 1]
                    continue
                await channel.send(f"❌ Agent error: {e}")
                return

            msg        = response.choices[0].message
            finish     = response.choices[0].finish_reason
            tool_calls = msg.tool_calls or []

            # Send any text response
            if msg.content and msg.content.strip():
                text = msg.content.strip()
                for i in range(0, len(text), 1900):
                    await channel.send(text[i:i + 1900])

            # No tool calls — done
            if not tool_calls or finish == "stop":
                self.history[channel.id].append({
                    "role": "assistant",
                    "content": msg.content or "Done.",
                })
                break

            # Execute each tool call
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": tool_calls})

            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except Exception:
                    args = {}
                result = await _execute_tool(tc.function.name, args, channel)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

    @commands.command(name="clear_memory")
    async def clear_memory(self, ctx: commands.Context):
        """Clear conversation history for this channel. !clear_memory"""
        self.history[ctx.channel.id].clear()
        await ctx.send("🧹 Memory cleared — fresh start!")


async def setup(bot: commands.Bot):
    await bot.add_cog(IntelligentAgent(bot))
