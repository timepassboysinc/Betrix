import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from animations import suspense
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY

POOL_SIZE = 40
DRAWN_COUNT = 10
MAX_PICKS = 10

# payout_table[picks][matches] = multiplier
PAYOUT_TABLE = {
    1: {0: 0, 1: 3.5},
    2: {0: 0, 1: 1, 2: 5},
    3: {0: 0, 1: 0, 2: 2, 3: 12},
    4: {0: 0, 1: 0, 2: 1.5, 3: 5, 4: 25},
    5: {0: 0, 1: 0, 2: 1, 3: 3, 4: 10, 5: 50},
    6: {0: 0, 1: 0, 2: 0, 3: 2, 4: 6, 5: 20, 6: 75},
    7: {0: 0, 1: 0, 2: 0, 3: 1.5, 4: 4, 5: 12, 6: 40, 7: 100},
    8: {0: 0, 1: 0, 2: 0, 3: 1, 4: 3, 5: 8, 6: 25, 7: 60, 8: 150},
    9: {0: 0, 1: 0, 2: 0, 3: 0.5, 4: 2, 5: 6, 6: 18, 7: 40, 8: 90, 9: 250},
    10: {0: 0, 1: 0, 2: 0, 3: 0, 4: 1.5, 5: 4, 6: 12, 7: 30, 8: 70, 9: 150, 10: 500},
}


class Keno(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="keno", aliases=["kn"], description=f"Pick 1-{MAX_PICKS} numbers (1-{POOL_SIZE}) and match the draw.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')", numbers="Your numbers, space or comma separated")
    async def keno(self, ctx: commands.Context, bet: str, numbers: str):
        try:
            picks = sorted({int(n) for n in numbers.replace(",", " ").split()})
        except ValueError:
            await ctx.send(embed=error_embed("Numbers must be integers, e.g. `3 14 22`."))
            return
        if not (1 <= len(picks) <= MAX_PICKS):
            await ctx.send(embed=error_embed(f"Pick between 1 and {MAX_PICKS} numbers."))
            return
        if any(not (1 <= n <= POOL_SIZE) for n in picks):
            await ctx.send(embed=error_embed(f"Numbers must be between 1 and {POOL_SIZE}."))
            return

        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)

        msg = await ctx.send(embed=base_embed("🎱 Drawing numbers...", f"Your picks: {picks}", COLOR_PRIMARY))
        await suspense(msg, "🎱 Drawing numbers...", f"Your picks: {picks}")

        drawn = sorted(random.sample(range(1, POOL_SIZE + 1), DRAWN_COUNT))
        matches = sorted(set(picks) & set(drawn))
        multiplier = PAYOUT_TABLE[len(picks)].get(len(matches), 0)
        payout = int(amount * multiplier)
        won = payout > 0
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        desc = (
            f"Your picks: {picks}\n"
            f"Drawn: {drawn}\n"
            f"Matches: {matches} ({len(matches)}/{len(picks)})\n\n"
        )
        if won:
            e = win_embed("You Won!", desc + f"Multiplier: {multiplier}x\nYou won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
        else:
            e = lose_embed("No Match", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Keno(bot))
