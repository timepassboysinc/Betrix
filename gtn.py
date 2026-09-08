import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from animations import suspense
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

MAX_NUMBER = 20


class GTN(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="gtn", description=f"Guess a number 1-{MAX_NUMBER}. Exact match pays big.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')", guess=f"Your guess (1-{MAX_NUMBER})")
    async def gtn(self, ctx: commands.Context, bet: str, guess: int):
        if not (1 <= guess <= MAX_NUMBER):
            await ctx.send(embed=error_embed(f"Guess must be between 1 and {MAX_NUMBER}."))
            return
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        msg = await ctx.send(embed=base_embed("🔢 Picking a number...", "", COLOR_PRIMARY))
        await suspense(msg, "🔢 Picking a number...")

        secret = random.randint(1, MAX_NUMBER)
        distance = abs(secret - guess)

        if distance == 0:
            multiplier = MAX_NUMBER * 0.9
        elif distance == 1:
            multiplier = 3.0
        elif distance == 2:
            multiplier = 1.5
        else:
            multiplier = 0.0

        won = multiplier > 0
        payout = int(amount * multiplier)
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        desc = f"Your guess: **{guess}**\nSecret number: **{secret}**\n\n"
        if won:
            e = win_embed("Close Enough!", desc + f"You won **{fmt(payout)}** ({multiplier}x)\nBalance: {fmt(new_bal)}")
            if distance == 0:
                e.color = COLOR_GOLD
                e.title = "🎯 Exact Match!"
        else:
            e = lose_embed("Not Close Enough", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(GTN(bot))
