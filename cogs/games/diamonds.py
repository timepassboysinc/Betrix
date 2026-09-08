import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

SYMBOLS = ["💎", "⬜", "⬜", "⬜"]  # 25% diamond per reel
PAYOUTS = {1: 0.4, 2: 2.0, 3: 15.0}  # number of diamonds -> multiplier


class Diamonds(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="diamonds", description="Spin the slots to match diamonds and win!")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def diamonds(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        msg = await ctx.send(embed=base_embed("💎 Spinning...", "┃ 💎 ┃ 💎 ┃ 💎 ┃", COLOR_PRIMARY))
        for _ in range(4):
            await asyncio.sleep(0.3)
            reels = [random.choice(SYMBOLS) for _ in range(3)]
            await msg.edit(embed=base_embed("💎 Spinning...", f"┃ {reels[0]} ┃ {reels[1]} ┃ {reels[2]} ┃", COLOR_PRIMARY))

        final = [random.choice(SYMBOLS) for _ in range(3)]
        diamond_count = final.count("💎")
        multiplier = PAYOUTS.get(diamond_count, 0.0)
        won = multiplier > 0
        payout = int(amount * multiplier)
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        board = f"┃ {final[0]} ┃ {final[1]} ┃ {final[2]} ┃"
        desc = f"{board}\n\n{diamond_count} diamond(s) — {multiplier}x\n\n"
        if won:
            e = win_embed("You Won!", desc + f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            if diamond_count == 3:
                e.color = COLOR_GOLD
        else:
            e = lose_embed("You Lost", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Diamonds(bot))
