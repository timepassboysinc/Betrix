import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, base_embed, error_embed, COLOR_PRIMARY, COLOR_GOLD

# (name, weight, payout multiplier)
ITEMS = [
    ("Scrap", 40, 0.2),
    ("Common Crate", 28, 0.5),
    ("Uncommon Stash", 18, 1.2),
    ("Rare Chest", 9, 3.0),
    ("Epic Vault", 4, 8.0),
    ("Legendary Hoard", 1, 30.0),
]
POOL = [item for item, weight, _ in ITEMS for _ in range(weight)]
LOOKUP = {name: mult for name, _, mult in ITEMS}


class CaseBattle(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="case", aliases=["casebattle"], description="Open a case and receive a random item.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def case(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)

        msg = await ctx.send(embed=base_embed("📦 Opening case...", "...", COLOR_PRIMARY))
        for _ in range(4):
            await asyncio.sleep(0.35)
            await msg.edit(embed=base_embed("📦 Opening case...", f"🎲 {random.choice(POOL)}", COLOR_PRIMARY))

        item = random.choice(POOL)
        multiplier = LOOKUP[item]
        payout = int(amount * multiplier)
        won = multiplier >= 1
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        table = " | ".join(f"{n} {m}x" for n, _, m in ITEMS)
        desc = f"You got: **{item}** ({multiplier}x)\n\n_{table}_\n\n"
        if won:
            e = win_embed("Nice Pull!", desc + f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            if multiplier >= 8:
                e.color = COLOR_GOLD
        else:
            e = lose_embed("Bad Pull", desc + f"You got back {fmt(payout)} (bet {fmt(amount)})\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(CaseBattle(bot))
