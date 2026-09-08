import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from animations import suspense
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

# multiplier: weight
TILE_POOL = {0.5: 30, 1: 24, 1.5: 18, 2: 14, 3: 8, 5: 4, 10: 2}
WEIGHTED = [v for v, w in TILE_POOL.items() for _ in range(w)]


class Match(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="match", description="Reveal 9 multipliers — match 3 of the same to win that multiplier.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def match(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        msg = await ctx.send(embed=base_embed("🎯 Revealing tiles...", "", COLOR_PRIMARY))
        await suspense(msg, "🎯 Revealing tiles...")

        tiles = [random.choice(WEIGHTED) for _ in range(9)]
        counts = {}
        for t in tiles:
            counts[t] = counts.get(t, 0) + 1
        matched = [v for v, c in counts.items() if c >= 3]
        multiplier = max(matched) if matched else 0.0

        won = multiplier > 0
        payout = int(amount * multiplier)
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        grid = "\n".join(" | ".join(f"{tiles[r*3+c]}x" for c in range(3)) for r in range(3))
        desc = f"```\n{grid}\n```\n"
        if won:
            e = win_embed("Match 3!", desc + f"You matched **{multiplier}x** — won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            if multiplier >= 5:
                e.color = COLOR_GOLD
        else:
            e = lose_embed("No Match", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Match(bot))
