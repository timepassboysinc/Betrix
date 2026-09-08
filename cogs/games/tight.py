import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from animations import suspense
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

# (multiplier, weight) — expected value tuned to ~0.96 (96% RTP)
OUTCOMES = [(0, 40), (0.5, 25), (1, 15), (1.5, 10), (2, 6), (5, 3), (20, 1)]
POOL = [m for m, w in OUTCOMES for _ in range(w)]


class Tight(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="tight", description="Get a random multiplier — always 96% RTP.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def tight(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        msg = await ctx.send(embed=base_embed("🎲 Rolling...", "", COLOR_PRIMARY))
        await suspense(msg, "🎲 Rolling...", frames=5)

        multiplier = random.choice(POOL)
        won = multiplier > 0
        payout = int(amount * multiplier)
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        if won:
            e = win_embed(f"Landed {multiplier}x!", f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            if multiplier >= 5:
                e.color = COLOR_GOLD
        else:
            e = lose_embed("0x", f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tight(bot))
