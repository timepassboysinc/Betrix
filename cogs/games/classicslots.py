import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

SYMBOLS = {
    "🍋": (35, 1.5),
    "🍒": (30, 2),
    "🔔": (18, 4),
    "BAR": (12, 8),
    "7️⃣": (5, 40),
}
PAIR_MULT = 0.5
POOL = [s for s, (w, _) in SYMBOLS.items() for _ in range(w)]


def render(reels):
    return f"┃ {reels[0]} ┃ {reels[1]} ┃ {reels[2]} ┃"


class ClassicSlots(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="classicslots", aliases=["cslots"], description="Play the classic 3-disc slots.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def classicslots(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        msg = await ctx.send(embed=base_embed("🎰 Spinning...", render([random.choice(POOL) for _ in range(3)]), COLOR_PRIMARY))
        for _ in range(4):
            await asyncio.sleep(0.3)
            await msg.edit(embed=base_embed("🎰 Spinning...", render([random.choice(POOL) for _ in range(3)]), COLOR_PRIMARY))

        final = [random.choice(POOL) for _ in range(3)]
        multiplier = 0.0
        result_text = "No match."
        if final[0] == final[1] == final[2]:
            multiplier = SYMBOLS[final[0]][1]
            result_text = f"JACKPOT! Triple {final[0]}"
        elif final[0] == final[1] or final[1] == final[2] or final[0] == final[2]:
            matched = final[1] if final[0] == final[1] or final[1] == final[2] else final[0]
            multiplier = SYMBOLS[matched][1] * PAIR_MULT
            result_text = f"Pair of {matched}"

        won = multiplier > 0
        payout = int(amount * multiplier)
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        board = render(final)
        if won:
            e = win_embed("Winner!", f"{board}\n\n{result_text} ({multiplier}x)\nYou won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            if multiplier >= 20:
                e.color = COLOR_GOLD
        else:
            e = lose_embed("No Luck", f"{board}\n\n{result_text}\nYou lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(ClassicSlots(bot))
