import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError, Deck
from animations import suspense
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

# rank -> multiplier (low cards pay small, face cards and aces pay big)
RANK_MULTIPLIER = {
    "2": 0.3, "3": 0.3, "4": 0.4, "5": 0.4, "6": 0.5, "7": 0.6, "8": 0.7,
    "9": 0.8, "10": 1.0, "J": 2.0, "Q": 3.0, "K": 4.0, "A": 8.0,
}


class Cards(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="cards", description="Draw a random card. Payout depends on the rank you pull.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def cards(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        msg = await ctx.send(embed=base_embed("🃏 Drawing...", "", COLOR_PRIMARY))
        await suspense(msg, "🃏 Drawing...", frames=5)

        card = Deck().draw(1)[0]
        multiplier = RANK_MULTIPLIER[card.rank]
        won = multiplier >= 1
        payout = int(amount * multiplier)
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        desc = f"You drew: **{card}**\nMultiplier: {multiplier}x\n\n"
        if won:
            e = win_embed("You Won!", desc + f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            if multiplier >= 4:
                e.color = COLOR_GOLD
        else:
            e = lose_embed("You Lost", desc + f"You ended with {fmt(payout)} (bet {fmt(amount)})\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Cards(bot))
