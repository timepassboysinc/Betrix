import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from animations import suspense
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

HOUSE_POOL = 2000  # simulated "everyone else's" contribution to the wheel


class JackpotWheel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="jackpotwheel", aliases=["jw"], description="The more you bet, the bigger your slice of the wheel.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def jackpotwheel(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        total_pool = amount + HOUSE_POOL
        win_chance = amount / total_pool

        msg = await ctx.send(embed=base_embed(
            "🎡 Spinning the jackpot wheel...",
            f"Your slice: **{win_chance * 100:.1f}%** of the wheel\nPool: {fmt(total_pool)}",
            COLOR_PRIMARY,
        ))
        await suspense(msg, "🎡 Spinning the jackpot wheel...", f"Your slice: **{win_chance * 100:.1f}%** of the wheel\nPool: {fmt(total_pool)}", frames=8)

        won = random.random() < win_chance
        payout = int(total_pool * 0.95) if won else 0  # house takes a 5% cut of the pool on a win
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        if won:
            e = win_embed("🎉 JACKPOT!", f"You won the wheel!\nYou won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            e.color = COLOR_GOLD
        else:
            e = lose_embed("So Close", f"The wheel landed elsewhere.\nYou lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(JackpotWheel(bot))
