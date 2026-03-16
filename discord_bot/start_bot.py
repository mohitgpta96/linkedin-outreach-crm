"""Entry point for OutreachBot. Run: python3 discord_bot/start_bot.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from discord_bot.bot import run
run()
