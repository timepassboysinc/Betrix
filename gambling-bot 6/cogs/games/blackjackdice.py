import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, base_embed, error_embed, COLOR_PRIMARY


class BJDiceView(discord.ui.View):
    def __init__(self, ctx: commands.Context, bet: int):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.bet = bet
        self.player_rolls = [random.randint(1, 6), random.randint(1, 6)]
        self.dealer_rolls = [random.randint(1, 6), random.randint(1, 6)]
        self.done = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    def embed(self, reveal_dealer=False, footer=""):
        p_total = sum(self.player_rolls)
        d_shown = self.dealer_rolls if reveal_dealer else [self.dealer_rolls[0], "?"]
        d_total = sum(self.dealer_rolls) if reveal_dealer else "?"
        desc = (
            f"Your dice: {self.player_rolls} = **{p_total}**\n"
            f"Dealer dice: {d_shown} = **{d_total}**\n\n"
            f"Bet: {fmt(self.bet)}"
        )
        if footer:
            desc += f"\n\n{footer}"
        return base_embed("🎲 Blackjack Dice", desc, COLOR_PRIMARY)

    async def end_game(self, interaction: discord.Interaction):
        self.done = True
        for c in self.children:
            c.disabled = True

        p_total = sum(self.player_rolls)
        if p_total <= 21:
            while sum(self.dealer_rolls) < 15:
                self.dealer_rolls.append(random.randint(1, 6))
        d_total = sum(self.dealer_rolls)

        if p_total > 21:
            won, payout, note = False, 0, "You busted."
        elif d_total > 21:
            won, payout, note = True, self.bet * 2, "Dealer busted!"
        elif p_total > d_total:
            won, payout, note = True, self.bet * 2, "You beat the dealer!"
        elif p_total == d_total:
            won, payout, note = False, self.bet, "Push — bet returned."
        else:
            won, payout, note = False, 0, "Dealer wins."

        await db.record_result(self.ctx.author.id, payout, won)
        new_bal = await db.get_balance(self.ctx.author.id)
        embed = self.embed(reveal_dealer=True, footer=f"{note}\nBalance: {fmt(new_bal)}")
        if payout == self.bet and not won:
            embed.title = "🎲 Push"
        elif won:
            embed.title = "🎲 You Win!"
            embed.color = win_embed("x").color
        else:
            embed.title = "🎲 You Lose"
            embed.color = lose_embed("x").color
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="🎲")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_rolls.append(random.randint(1, 6))
        if sum(self.player_rolls) >= 21:
            await self.end_game(interaction)
        else:
            await interaction.response.edit_message(embed=self.embed())

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.end_game(interaction)

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True


class BlackjackDice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="blackjackdice", aliases=["bjdice"], description="Reach 21 (or beat the dealer) using dice 1-6.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def blackjackdice(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        view = BJDiceView(ctx, amount)
        await ctx.send(embed=view.embed(), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(BlackjackDice(bot))
