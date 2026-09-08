import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from animations import suspense
from config import fmt, win_embed, lose_embed, error_embed, base_embed, info_embed, COLOR_PRIMARY

PAYOUT = 1.92


class DiceWar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="dicewar", description="Roll a die against the bot. Higher roll wins.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def dicewar(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        msg = await ctx.send(embed=base_embed("🎲 Rolling...", "You vs the house!", COLOR_PRIMARY))
        await suspense(msg, "🎲 Rolling...", "You vs the house!")

        player_roll = random.randint(1, 6)
        bot_roll = random.randint(1, 6)
        desc = f"You rolled **{player_roll}**\nHouse rolled **{bot_roll}**\n\n"

        if player_roll > bot_roll:
            payout = int(amount * PAYOUT)
            await db.record_result(ctx.author.id, payout, True)
            new_bal = await db.get_balance(ctx.author.id)
            e = win_embed("You Won!", desc + f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
        elif player_roll == bot_roll:
            await db.record_result(ctx.author.id, amount, False)
            new_bal = await db.get_balance(ctx.author.id)
            e = info_embed("Tie — Push", desc + f"Bet refunded.\nBalance: {fmt(new_bal)}")
        else:
            await db.record_result(ctx.author.id, 0, False)
            new_bal = await db.get_balance(ctx.author.id)
            e = lose_embed("You Lost", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(DiceWar(bot))
