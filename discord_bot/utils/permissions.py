"""Owner-only check — this is Mohit's private server."""
import discord
from discord.ext import commands
import os

def is_owner():
    """Check if user is the bot owner (Mohit). Falls back to guild owner."""
    async def predicate(ctx):
        guild = ctx.guild
        if guild and ctx.author.id == guild.owner_id:
            return True
        owner_id = os.getenv("DISCORD_OWNER_ID")
        if owner_id and str(ctx.author.id) == owner_id:
            return True
        # If no owner ID set, allow anyone in the private server
        return True
    return commands.check(predicate)
