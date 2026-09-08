import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY

MAX_ATTEMPTS = 3
STEP_MULTIPLIER = 1.55  # per safe reveal


class RatButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=index // 3)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        await self.view.reveal(interaction, self.index, self)


class RatView(discord.ui.View):
    def __init__(self, ctx: commands.Context, bet: int):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.bet = bet
        self.rat_index = random.randint(0, 8)
        self.attempts = 0
        self.multiplier = 1.0
        self.over = False
        for i in range(9):
            self.add_item(RatButton(i))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    def embed(self, footer: str = ""):
        desc = (
            f"Attempts: **{self.attempts}/{MAX_ATTEMPTS}**\n"
            f"Multiplier: **{round(self.multiplier, 2)}x**\n"
            f"Bet: {fmt(self.bet)}"
        )
        if footer:
            desc += f"\n\n{footer}"
        return base_embed("🐀 Find the Rat", desc, COLOR_PRIMARY)

    def reveal_all(self):
        for btn in self.children:
            btn.disabled = True
            if btn.index == self.rat_index:
                btn.style = discord.ButtonStyle.danger
                btn.emoji = "🐀"
            elif getattr(btn, "revealed", False):
                btn.style = discord.ButtonStyle.success
                btn.emoji = "✅"

    async def reveal(self, interaction: discord.Interaction, index: int, btn: RatButton):
        if self.over or btn.disabled:
            await interaction.response.defer()
            return

        if index == self.rat_index:
            self.over = True
            self.reveal_all()
            await db.record_result(self.ctx.author.id, 0, False)
            new_bal = await db.get_balance(self.ctx.author.id)
            await interaction.response.edit_message(
                embed=lose_embed("🐀 Found the Rat!", f"You lost **{fmt(self.bet)}**\nBalance: {fmt(new_bal)}"),
                view=self,
            )
            self.stop()
            return

        btn.revealed = True
        btn.disabled = True
        btn.style = discord.ButtonStyle.success
        btn.emoji = "✅"
        self.attempts += 1
        self.multiplier *= STEP_MULTIPLIER

        if self.attempts >= MAX_ATTEMPTS:
            self.over = True
            self.reveal_all()
            payout = int(self.bet * self.multiplier)
            await db.record_result(self.ctx.author.id, payout, True)
            new_bal = await db.get_balance(self.ctx.author.id)
            await interaction.response.edit_message(
                embed=win_embed(
                    "Safe! You Win!",
                    f"Made it through {MAX_ATTEMPTS} tiles without finding the rat.\n"
                    f"You won **{fmt(payout)}** ({round(self.multiplier, 2)}x)\nBalance: {fmt(new_bal)}",
                ),
                view=self,
            )
            self.stop()
            return

        await interaction.response.edit_message(embed=self.embed())

    async def on_timeout(self):
        if not self.over:
            self.reveal_all()


class Rat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="rat", description="Find the hidden rat in a 3x3 grid — you get 3 attempts.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def rat(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        view = RatView(ctx, amount)
        await ctx.send(embed=view.embed(), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Rat(bot))
