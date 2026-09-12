import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError, Deck
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD, MIN_CASHOUT_MULTIPLIER

STEP_MULTIPLIER = 1.9  # applied per correct guess


class HiloView(discord.ui.View):
    def __init__(self, ctx: commands.Context, deck: Deck, bet: int):
        super().__init__(timeout=45)
        self.ctx = ctx
        self.deck = deck
        self.bet = bet
        self.current = deck.draw(1)[0]
        self.multiplier = 1.0
        self.cash_out_btn.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    def embed(self, footer: str = ""):
        desc = (
            f"Current card: **{self.current}**\n"
            f"Multiplier so far: **{round(self.multiplier, 2)}x**\n"
            f"Bet: {fmt(self.bet)}"
        )
        if footer:
            desc += f"\n\n{footer}"
        return base_embed("🔺🔻 Hi-Lo", desc, COLOR_PRIMARY)

    async def _guess(self, interaction: discord.Interaction, direction: str):
        if not self.deck.cards:
            self.deck.cards = Deck().cards  # reshuffle if we run out
        new_card = self.deck.draw(1)[0]

        if new_card.rank_index == self.current.rank_index:
            # push — redraw, nothing changes
            self.current = new_card
            await interaction.response.edit_message(embed=self.embed("Push (same rank) — guess again."))
            return

        went_up = new_card.rank_index > self.current.rank_index
        correct = (direction == "higher" and went_up) or (direction == "lower" and not went_up)
        self.current = new_card

        if not correct:
            for c in self.children:
                c.disabled = True
            await db.record_result(self.ctx.author.id, 0, False)
            new_bal = await db.get_balance(self.ctx.author.id)
            await interaction.response.edit_message(
                embed=lose_embed("Wrong!", f"Landed on **{new_card}**.\nYou lost **{fmt(self.bet)}**\nBalance: {fmt(new_bal)}"),
                view=self,
            )
            self.stop()
            return

        self.multiplier *= STEP_MULTIPLIER
        self.cash_out_btn.disabled = False
        await interaction.response.edit_message(embed=self.embed())

    @discord.ui.button(label="Higher", emoji="🔺", style=discord.ButtonStyle.success)
    async def higher(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._guess(interaction, "higher")

    @discord.ui.button(label="Lower", emoji="🔻", style=discord.ButtonStyle.danger)
    async def lower(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._guess(interaction, "lower")

    @discord.ui.button(label="Cash Out", emoji="💰", style=discord.ButtonStyle.success, row=1)
    async def cash_out_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.multiplier < MIN_CASHOUT_MULTIPLIER:
            await interaction.response.send_message(
                f"You need at least {MIN_CASHOUT_MULTIPLIER}x to cash out — guess correctly first!",
                ephemeral=True,
            )
            return
        for c in self.children:
            c.disabled = True
        payout = int(self.bet * self.multiplier)
        await db.record_result(self.ctx.author.id, payout, True)
        new_bal = await db.get_balance(self.ctx.author.id)
        e = win_embed(f"Cashed Out at {round(self.multiplier, 2)}x!", f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
        if self.multiplier >= 10:
            e.color = COLOR_GOLD
        await interaction.response.edit_message(embed=e, view=self)
        self.stop()

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True


class Hilo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="hilo", description="Guess if the next card is higher or lower to build a multiplier.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def hilo(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        deck = Deck()
        view = HiloView(ctx, deck, amount)
        await ctx.send(embed=view.embed(), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Hilo(bot))
