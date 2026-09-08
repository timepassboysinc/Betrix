import asyncio
import io
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from imaging import render_coinflip
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY

PAYOUT = 1.92  # matches "1.92x" style payout, ~4% house edge on a 50/50


class Coinflip(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="coinflip", aliases=["cf"], description="Flip a coin for 1.92x your bet.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')", side="heads or tails")
    @app_commands.choices(side=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails"),
    ])
    async def coinflip(self, ctx: commands.Context, bet: str, side: str):
        side = side.lower()
        if side not in ("heads", "tails"):
            await ctx.send(embed=error_embed("Pick `heads` or `tails`."))
            return
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)

        msg = await ctx.send(embed=base_embed("🪙 Flipping...", "The coin is in the air...", COLOR_PRIMARY))
        for _ in range(4):
            await asyncio.sleep(0.4)

        result = random.choice(["heads", "tails"])
        won = result == side
        payout = int(amount * PAYOUT) if won else 0

        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        img_bytes = render_coinflip(result, won)
        file = discord.File(io.BytesIO(img_bytes), filename="coinflip.png")

        if won:
            e = win_embed(
                "You Won!",
                f"You won **{fmt(payout)}** ({PAYOUT}x)\nBalance: {fmt(new_bal)}",
            )
        else:
            e = lose_embed(
                "You Lost",
                f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}",
            )
        e.set_thumbnail(url="attachment://coinflip.png")
        await msg.edit(embed=e, attachments=[file])


async def setup(bot: commands.Bot):
    await bot.add_cog(Coinflip(bot))
