import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

ROWS = 8
# Symmetric payout table (medium risk feel), house edge baked in via the outer weighting.
MULTIPLIERS = [5.6, 2.1, 1.4, 1.1, 0.5, 1.1, 1.4, 2.1, 5.6]


def render_path(position: int, width: int) -> str:
    center = width // 2
    slot = center + position
    slot = max(0, min(width - 1, slot))
    line = ["·"] * width
    line[slot] = "🔴"
    return "".join(line)


class Plinko(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="plinko", aliases=["pl"], description="Drop a ball through the peg pyramid.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def plinko(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)

        width = ROWS * 2 + 1
        moves = [random.choice((-1, 1)) for _ in range(ROWS)]
        position = 0

        msg = await ctx.send(embed=base_embed("🔴 Dropping...", render_path(0, width), COLOR_PRIMARY))
        for m in moves:
            await asyncio.sleep(0.3)
            position += m
            await msg.edit(embed=base_embed("🔴 Dropping...", render_path(position, width), COLOR_PRIMARY))

        bin_index = (sum(moves) + ROWS) // 2  # 0..ROWS, count of "right" moves
        multiplier = MULTIPLIERS[bin_index]
        payout = int(amount * multiplier)
        won = payout > amount
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        row_display = " ".join(
            f"**[{m}x]**" if i == bin_index else f"{m}x" for i, m in enumerate(MULTIPLIERS)
        )
        desc = f"Landed in the **{multiplier}x** slot!\n{row_display}\n\n"
        if payout >= amount:
            e = win_embed("Nice Drop!", desc + f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            if multiplier >= 5:
                e.color = COLOR_GOLD
        else:
            e = lose_embed("Better luck next time", desc + f"You ended with **{fmt(payout)}** (bet {fmt(amount)})\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Plinko(bot))
