import io

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError, Deck, blackjack_value
from imaging import render_blackjack_table
from config import fmt, win_embed, lose_embed, base_embed, error_embed, COLOR_PRIMARY


def _card_str(card) -> str:
    return f"{card.rank}{card.suit}"


class BlackjackView(discord.ui.View):
    def __init__(self, ctx: commands.Context, deck: Deck, player: list, dealer: list, bet: int):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.deck = deck
        self.player = player
        self.dealer = dealer
        self.bet = bet
        self.finished = False
        if blackjack_value(player) == 21:
            self.stand.disabled = True
            self.hit.disabled = True
            self.double.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    def build(self, reveal_dealer: bool = False, footer: str = ""):
        p_val = str(blackjack_value(self.player))
        d_val = str(blackjack_value(self.dealer)) if reveal_dealer else "?"
        img_bytes = render_blackjack_table(
            [_card_str(c) for c in self.player],
            [_card_str(c) for c in self.dealer],
            hide_dealer_second=not reveal_dealer,
            player_val=p_val,
            dealer_val=d_val,
        )
        file = discord.File(io.BytesIO(img_bytes), filename="blackjack.png")
        desc = f"Bet: {fmt(self.bet)}"
        if footer:
            desc += f"\n\n{footer}"
        embed = base_embed("🃏 Blackjack", desc, COLOR_PRIMARY)
        embed.set_image(url="attachment://blackjack.png")
        return embed, file

    async def end_game(self, interaction: discord.Interaction | None):
        self.finished = True
        for c in self.children:
            c.disabled = True

        p_val = blackjack_value(self.player)
        if p_val <= 21:
            while blackjack_value(self.dealer) < 17:
                self.dealer.extend(self.deck.draw(1))

        d_val = blackjack_value(self.dealer)
        player_natural = p_val == 21 and len(self.player) == 2
        dealer_natural = d_val == 21 and len(self.dealer) == 2

        if p_val > 21:
            won, payout, note = False, 0, "You busted."
        elif player_natural and not dealer_natural:
            won, payout, note = True, int(self.bet * 2.5), "Blackjack!"
        elif dealer_natural and not player_natural:
            won, payout, note = False, 0, "Dealer has blackjack."
        elif d_val > 21:
            won, payout, note = True, self.bet * 2, "Dealer busted!"
        elif p_val > d_val:
            won, payout, note = True, self.bet * 2, "You beat the dealer!"
        elif p_val == d_val:
            won, payout, note = False, self.bet, "Push — bet returned."
        else:
            won, payout, note = False, 0, "Dealer wins."

        await db.record_result(self.ctx.author.id, payout, won)
        new_bal = await db.get_balance(self.ctx.author.id)
        footer = f"{note}\nBalance: {fmt(new_bal)}"
        embed, file = self.build(reveal_dealer=True, footer=footer)

        if payout == self.bet and not won:
            embed.title = "🃏 Blackjack — Push"
        elif won:
            embed.title = "🃏 Blackjack — You Win!"
            embed.color = win_embed("x").color
        else:
            embed.title = "🃏 Blackjack — You Lose"
            embed.color = lose_embed("x").color

        if interaction is not None:
            await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
        else:
            await self.message.edit(embed=embed, view=self, attachments=[file])
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.extend(self.deck.draw(1))
        if blackjack_value(self.player) >= 21:
            await self.end_game(interaction)
        else:
            embed, file = self.build()
            await interaction.response.edit_message(embed=embed, attachments=[file])

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.end_game(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.danger, emoji="⏫")
    async def double(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok = await db.try_take(self.ctx.author.id, self.bet)
        if not ok:
            await interaction.response.send_message("You don't have enough balance to double down.", ephemeral=True)
            return
        self.bet *= 2
        self.player.extend(self.deck.draw(1))
        await self.end_game(interaction)

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True


class Blackjack(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="blackjack", aliases=["bj"], description="Play blackjack against the dealer.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def blackjack(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)

        deck = Deck()
        player = deck.draw(2)
        dealer = deck.draw(2)

        view = BlackjackView(ctx, deck, player, dealer, amount)
        embed, file = view.build()
        msg = await ctx.send(embed=embed, file=file, view=view)
        view.message = msg

        if blackjack_value(player) == 21:
            await view.end_game(None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Blackjack(bot))
