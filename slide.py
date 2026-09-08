import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from animations import suspense
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY

HOUSE_EDGE = 0.03


def generate_result() -> float:
    r = random.random()
    if r < 0.02:
        return 1.0
    point = (1 - HOUSE_EDGE) / (1 - r)
    return round(min(point, 1_000_000.0), 2)


class Slide(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="slide", description="Pick a target multiplier — win if the slider lands on or above it.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')", target="Target multiplier, e.g. 2.0")
    async def slide(self, ctx: commands.Context, bet: str, target: float):
        if target < 1.01:
            await ctx.send(embed=error_embed("Target must be at least 1.01x."))
            return
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        msg = await ctx.send(embed=base_embed("🛝 Sliding...", f"Target: {target}x", COLOR_PRIMARY))
        await suspense(msg, "🛝 Sliding...", f"Target: {target}x")

        result = generate_result()
        won = result >= target
        payout = int(amount * target) if won else 0
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        desc = f"Slider landed on **{result}x** (needed {target}x)\n"
        if won:
            e = win_embed("You Won!", desc + f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
        else:
            e = lose_embed("You Lost", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Slide(bot))
