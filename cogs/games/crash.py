import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, E_ROCKET, MIN_CASHOUT_MULTIPLIER

HOUSE_EDGE = 0.03


def generate_crash_point() -> float:
    """Provably-fair-style distribution: mostly low multipliers, rare huge ones."""
    r = random.random()
    if r < 0.02:
        return 1.0  # instant crash, ~2% of the time
    point = (1 - HOUSE_EDGE) / (1 - r)
    return round(min(point, 1000.0), 2)


class CrashView(discord.ui.View):
    def __init__(self, ctx: commands.Context, bet: int):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.bet = bet
        self.resolved = False
        self.current_mult = 1.0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.success, emoji="💰")
    async def cash_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved:
            return
        if self.current_mult < MIN_CASHOUT_MULTIPLIER:
            await interaction.response.send_message(
                f"You can cash out starting at {MIN_CASHOUT_MULTIPLIER}x — hang on just a moment longer!",
                ephemeral=True,
            )
            return

        self.resolved = True
        for c in self.children:
            c.disabled = True
        payout = int(self.bet * self.current_mult)
        await db.record_result(self.ctx.author.id, payout, True)
        new_bal = await db.get_balance(self.ctx.author.id)
        await interaction.response.edit_message(
            embed=win_embed(
                f"Cashed Out at {self.current_mult}x!",
                f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}",
            ),
            view=None,
        )
        self.stop()

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True


class Crash(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="crash", aliases=["cr"], description="Cash out before the rocket crashes!")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def crash(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        crash_point = generate_crash_point()

        view = CrashView(ctx, amount)
        msg = await ctx.send(
            embed=base_embed(f"{E_ROCKET} 1.00x", "Climbing... hit Cash Out any time!", COLOR_PRIMARY),
            view=view,
        )

        mult = 1.0
        while not view.resolved:
            await asyncio.sleep(0.7)
            if view.resolved:
                return  # cashed out mid-sleep — the button callback already handled everything

            mult = round(mult + max(0.05, mult * 0.12), 2)
            view.current_mult = mult

            if mult >= crash_point:
                view.resolved = True
                for c in view.children:
                    c.disabled = True
                await db.record_result(ctx.author.id, 0, False)
                new_bal = await db.get_balance(ctx.author.id)
                await msg.edit(
                    embed=lose_embed(
                        f"💥 Crashed at {crash_point}x!",
                        f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}",
                    ),
                    view=view,
                )
                view.stop()
                return

            await msg.edit(embed=base_embed(f"{E_ROCKET} {mult}x", "Climbing... hit Cash Out any time!", COLOR_PRIMARY), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Crash(bot))
