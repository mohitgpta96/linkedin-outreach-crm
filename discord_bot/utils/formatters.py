"""Discord embed builders for OutreachBot."""
import discord
from typing import Optional

TIER_COLORS = {
    "HOT":    discord.Color.from_rgb(220, 38, 38),
    "STRONG": discord.Color.from_rgb(245, 158, 11),
    "WARM":   discord.Color.from_rgb(59, 130, 246),
    "WEAK":   discord.Color.from_rgb(148, 163, 184),
}
TIER_EMOJI = {"HOT": "🔥", "STRONG": "⚡", "WARM": "🔵", "WEAK": "⬜"}
STAGE_EMOJI = {
    "new": "🆕", "warming_up": "🌡️", "requested": "📤",
    "connected": "🤝", "replied": "💬", "meeting": "📅", "done": "✅",
}


def lead_embed(lead: dict) -> discord.Embed:
    name    = lead.get("name", "Unknown")
    company = lead.get("company", "—")
    title   = lead.get("title", "—")
    size    = lead.get("company_size", "?")
    source  = lead.get("source", "")
    score   = lead.get("icp_priority_score", lead.get("pm_demand_score", "—"))
    tier    = str(lead.get("pm_demand_tier", "WARM")).upper()
    p_stage = lead.get("pipeline_stage", "enriched")
    o_stage = lead.get("outreach_stage", "new")
    url     = lead.get("profile_url", "")
    pain    = lead.get("pain_point", "")
    hook    = lead.get("personalization_hook", "")
    conn    = lead.get("connection_request", lead.get("msg_connection_note", ""))

    color  = TIER_COLORS.get(tier, discord.Color.blurple())
    t_emoji = TIER_EMOJI.get(tier, "📊")
    s_emoji = STAGE_EMOJI.get(o_stage, "📋")

    embed = discord.Embed(
        title=f"👤 {name}",
        description=f"🏢 **{company}** · {size} people · {source}",
        color=color,
    )
    embed.add_field(name="📊 Score", value=f"`{score}`", inline=True)
    embed.add_field(name="💡 Tier",  value=f"{t_emoji} {tier}", inline=True)
    embed.add_field(name="🔵 Stage", value=f"{s_emoji} {o_stage.replace('_',' ').title()}", inline=True)
    embed.add_field(name="🎯 Title", value=title, inline=True)

    if pain:
        embed.add_field(name="📝 Pain Point", value=pain[:200], inline=False)
    if hook:
        embed.add_field(name="🎣 Hook", value=hook[:200], inline=False)
    if conn:
        wc = len(str(conn).split())
        embed.add_field(
            name=f"💬 Connection Request ({len(conn)} chars · {wc} words)",
            value=f"```{str(conn)[:300]}```",
            inline=False,
        )
    if url:
        embed.add_field(name="🔗 LinkedIn", value=f"[View Profile]({url})", inline=True)

    embed.set_footer(text="!messages [name] for all 7 messages · !advance [name] to move stage")
    return embed


def leads_list_embed(leads: list, filter_label: str = "All") -> discord.Embed:
    embed = discord.Embed(
        title=f"📋 {filter_label} Leads ({len(leads)})",
        color=discord.Color.blurple(),
    )
    lines = []
    for i, lead in enumerate(leads[:20], 1):
        name    = lead.get("name", "—")
        company = lead.get("company", "—")
        score   = lead.get("icp_priority_score", "—")
        tier    = str(lead.get("pm_demand_tier", "WARM")).upper()
        source  = lead.get("source", "")
        t_emoji = TIER_EMOJI.get(tier, "📊")
        lines.append(f"`{i:2d}.` {t_emoji} **{name}** · {company} · `{score}` · {source}")
    if not lines:
        lines.append("No leads found for this filter.")
    embed.description = "\n".join(lines)
    if len(leads) > 20:
        embed.set_footer(text=f"+{len(leads)-20} more · Use !search [query] to narrow down")
    else:
        embed.set_footer(text="Type !lead [name] for full details")
    return embed


def messages_embed(lead: dict, msg_num: Optional[int] = None) -> list[discord.Embed]:
    name    = lead.get("name", "?")
    company = lead.get("company", "?")

    MESSAGE_MAP = [
        ("connection_request",  "1️⃣ Connection Request",  "Day 4 · < 300 chars"),
        ("followup_day2",       "2️⃣ Follow-up DM",        "Day 6 (after accept)"),
        ("followup_day4",       "3️⃣ Follow-up 2",         "Day 10"),
        ("followup_day7",       "4️⃣ Follow-up 3",         "Day 17"),
        ("followup_day14",      "5️⃣ Follow-up 4",         "Day 25"),
        ("followup_day21",      "6️⃣ Follow-up 5",         "Day 32"),
        ("followup_final",      "7️⃣ Breakup",             "Day 40"),
    ]

    if msg_num is not None:
        key, label, day = MESSAGE_MAP[msg_num - 1] if 1 <= msg_num <= 7 else MESSAGE_MAP[0]
        text = lead.get(key, "")
        e = discord.Embed(
            title=f"💬 {label} — {name} ({company})",
            description=f"*{day}*\n\n```{text}```" if text else "*No message generated*",
            color=discord.Color.blurple(),
        )
        e.set_footer(text=f"{len(str(text).split())} words · {len(str(text))} chars")
        return [e]

    # All messages — one embed per message for readability
    embeds = []
    header = discord.Embed(
        title=f"💬 All Messages — {name} ({company})",
        description="7 messages ready. Click copy icon on each code block.",
        color=discord.Color.blurple(),
    )
    embeds.append(header)

    for key, label, day in MESSAGE_MAP:
        text = lead.get(key, "")
        if not text:
            continue
        wc = len(str(text).split())
        e = discord.Embed(
            title=f"{label}",
            description=f"*{day}*\n\n```{text}```",
            color=discord.Color.from_rgb(59, 130, 246),
        )
        e.set_footer(text=f"{wc} words · {len(str(text))} chars")
        embeds.append(e)

    return embeds


def pipeline_status_embed(state: dict) -> discord.Embed:
    embed = discord.Embed(title="📊 Pipeline Status", color=discord.Color.blue())

    enrichment  = state.get("enrichment", {})
    validation  = state.get("validation", {})
    feedback    = state.get("feedback", {})
    dedup       = state.get("dedup", {})
    last_run    = state.get("last_scrape", {}).get("timestamp", "Never")
    apify_bal   = enrichment.get("apify_credits", {}).get("balance", "?")
    groq_tok    = enrichment.get("groq_tokens_today", 0)

    # Pipeline section
    embed.add_field(
        name="⚙️ Pipeline",
        value=(
            f"Last run: `{last_run}`\n"
            f"Leads scraped: `{state.get('last_scrape', {}).get('total', '—')}`\n"
            f"Filtered: `{state.get('last_filter', {}).get('passed', '—')}`\n"
            f"Qualified: `{state.get('last_qualification', {}).get('passed', '—')}`\n"
            f"Enriched: `{validation.get('passed', '—')}`\n"
            f"Dupes caught: `{dedup.get('total_caught', 0)}`"
        ),
        inline=True,
    )
    embed.add_field(
        name="💰 Credits",
        value=(
            f"Apify: `${apify_bal}`\n"
            f"Groq: `{groq_tok:,}/100,000` tokens\n"
            f"Daily spend: `${state.get('daily_spend', 0):.2f}/$2.00`"
        ),
        inline=True,
    )
    embed.add_field(
        name="📈 Outreach",
        value=(
            f"Total sent: `{feedback.get('total_sent', 0)}`\n"
            f"Accept rate: `{feedback.get('accept_rate', 0):.0%}`\n"
            f"Reply rate: `{feedback.get('reply_rate', 0):.0%}`"
        ),
        inline=True,
    )
    embed.set_footer(text="!pipeline credits for quick credit check")
    return embed


def alert_embed(title: str, description: str, alert_type: str = "info") -> discord.Embed:
    colors = {
        "success": discord.Color.green(),
        "warning": discord.Color.orange(),
        "error":   discord.Color.red(),
        "info":    discord.Color.blurple(),
        "new":     discord.Color.from_rgb(16, 185, 129),
    }
    color = colors.get(alert_type, discord.Color.blurple())
    embed = discord.Embed(title=title, description=description, color=color)
    return embed


def stats_embed(leads: list, state: dict = None) -> discord.Embed:
    stage_counts = {}
    tier_counts  = {}
    for l in leads:
        s = l.get("outreach_stage", "new")
        t = str(l.get("pm_demand_tier", "WARM")).upper()
        stage_counts[s] = stage_counts.get(s, 0) + 1
        tier_counts[t]  = tier_counts.get(t, 0) + 1

    embed = discord.Embed(title="📊 CRM Stats", color=discord.Color.blue())
    embed.add_field(
        name="Pipeline",
        value=(
            f"Total leads: `{len(leads)}`\n"
            f"Enriched: `{len(leads)}`\n"
            f"Ready: `{stage_counts.get('new', 0)}`\n"
            f"Warming up: `{stage_counts.get('warming_up', 0)}`\n"
            f"Requested: `{stage_counts.get('requested', 0)}`\n"
            f"Connected: `{stage_counts.get('connected', 0)}`\n"
            f"Replied: `{stage_counts.get('replied', 0)}`\n"
            f"Meeting: `{stage_counts.get('meeting', 0)}`"
        ),
        inline=True,
    )
    embed.add_field(
        name="Signal Tiers",
        value=(
            f"🔥 HOT: `{tier_counts.get('HOT', 0)}`\n"
            f"⚡ STRONG: `{tier_counts.get('STRONG', 0)}`\n"
            f"🔵 WARM: `{tier_counts.get('WARM', 0)}`\n"
            f"⬜ WEAK: `{tier_counts.get('WEAK', 0)}`"
        ),
        inline=True,
    )
    sent_today = stage_counts.get("requested", 0)
    embed.add_field(
        name="Today",
        value=f"📤 Sent: `{sent_today}/15`",
        inline=True,
    )
    return embed
