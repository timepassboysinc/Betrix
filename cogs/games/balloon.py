import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD, MIN_CASHOUT_MULTIPLIER

POP_CHANCE_START = 0.04
POP_CHANCE_STEP = 0.025
MULTIPLIER_STEP = 0.22


class BalloonView(discord.ui.View):
    def __init__(self, ctx: commands.Context, bet: int):
        super().__init__(timeout=45)
        self.ctx = ctx
        self.bet = bet
        self.multiplier = 1.0
        self.pumps = 0
        self.cash_out.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    def embed(self, footer: str = ""):
        size = "🎈" if self.pumps < 8 else "🎈💨"
        desc = f"{size}\nPumps: **{self.pumps}**\nMultiplier: **{round(self.multiplier, 2)}x**\nBet: {fmt(self.bet)}"
        if footer:
            desc += f"\n\n{footer}"
        return base_embed("🎈 Balloon", desc, COLOR_PRIMARY)

    @discord.ui.button(label="Pump", emoji="🎈", style=discord.ButtonStyle.primary)
    async def pump(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pumps += 1
        pop_chance = POP_CHANCE_START + POP_CHANCE_STEP * (self.pumps - 1)
        if random.random() < pop_chance:
            for c in self.children:
                c.disabled = True
            await db.record_result(self.ctx.author.id, 0, False)
            new_bal = await db.get_balance(self.ctx.author.id)
            await interaction.response.edit_message(
                embed=lose_embed("💥 POP!", f"The balloon popped after {self.pumps} pumps.\nYou lost **{fmt(self.bet)}**\nBalance: {fmt(new_bal)}"),
                view=self,
            )
            self.stop()
            return

        self.multiplier += MULTIPLIER_STEP
        self.cash_out.disabled = False
        await interaction.response.edit_message(embed=self.embed())

    @discord.ui.button(label="Cash Out", emoji="💰", style=discord.ButtonStyle.success)
    async def cash_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.multiplier < MIN_CASHOUT_MULTIPLIER:
            await interaction.response.send_message(
                f"You need at least {MIN_CASHOUT_MULTIPLIER}x to cash out — one more pump!",
                ephemeral=True,
            )
            return
        for c in self.children:
            c.disabled = True
        payout = int(self.bet * self.multiplier)
        await db.record_result(self.ctx.author.id, payout, True)
        new_bal = await db.get_balance(self.ctx.author.id)
        e = win_embed(f"Cashed Out at {round(self.multiplier, 2)}x!", f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
        if self.multiplier >= 3:
            e.color = COLOR_GOLD
        await interaction.response.edit_message(embed=e, view=self)
        self.stop()

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True


class Balloon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="balloon", description="Pump the balloon to increase your multiplier — cash out before it pops!")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def balloon(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        view = BalloonView(ctx, amount)
        await ctx.send(embed=view.embed(), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Balloon(bot))
