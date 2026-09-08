import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError, Deck, hand_str, blackjack_value
from config import fmt, win_embed, lose_embed, error_embed, base_embed, info_embed, COLOR_PRIMARY


# ---------------------------------------------------------------------------
# Shared challenge flow: challenger picks an opponent + bet, opponent accepts.
# Both amounts are escrowed (taken from balance) the moment the challenge is
# accepted; the loser doesn't get anything back, the winner gets the full pot.
# ---------------------------------------------------------------------------

class ChallengeView(discord.ui.View):
    def __init__(self, ctx: commands.Context, opponent: discord.Member, bet: int, start_game):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.opponent = opponent
        self.bet = bet
        self.start_game = start_game  # async callback(interaction) to launch the actual game

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This challenge isn't for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        challenger_ok = await db.try_take(self.ctx.author.id, self.bet)
        opponent_ok = await db.try_take(self.opponent.id, self.bet) if challenger_ok else False
        if not challenger_ok or not opponent_ok:
            if challenger_ok:
                await db.add_balance(self.ctx.author.id, self.bet)  # refund
            await interaction.response.edit_message(
                embed=error_embed("One of you no longer has enough balance for this bet."), view=None
            )
            return
        for c in self.children:
            c.disabled = True
        await self.start_game(interaction)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=info_embed("Challenge declined."), view=None)
        self.stop()


async def payout_winner(winner_id: int, loser_id: int, pot: int):
    await db.record_result(winner_id, pot, True)
    await db.record_result(loser_id, 0, False)


async def refund_draw(a_id: int, b_id: int, bet: int):
    await db.record_result(a_id, bet, False)
    await db.record_result(b_id, bet, False)


# ---------------------------------------------------------------------------
# Rock Paper Scissors
# ---------------------------------------------------------------------------

BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


class RPSView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, bet: int):
        super().__init__(timeout=60)
        self.p1, self.p2, self.bet = p1, p2, bet
        self.choices: dict[int, str] = {}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in (self.p1.id, self.p2.id):
            await interaction.response.send_message("This isn't your game.", ephemeral=True)
            return False
        if interaction.user.id in self.choices:
            await interaction.response.send_message("You already chose.", ephemeral=True)
            return False
        return True

    async def _pick(self, interaction: discord.Interaction, choice: str):
        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"You picked **{choice}**.", ephemeral=True)
        if len(self.choices) == 2:
            await self.resolve(interaction)

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.secondary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._pick(interaction, "rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.secondary)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._pick(interaction, "paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.secondary)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._pick(interaction, "scissors")

    async def resolve(self, interaction: discord.Interaction):
        for c in self.children:
            c.disabled = True
        c1, c2 = self.choices[self.p1.id], self.choices[self.p2.id]
        pot = self.bet * 2
        if c1 == c2:
            await refund_draw(self.p1.id, self.p2.id, self.bet)
            desc = f"{self.p1.mention} chose **{c1}**, {self.p2.mention} chose **{c2}**.\nIt's a draw — bets refunded."
            e = info_embed("🤝 Draw!", desc)
        else:
            winner, loser = (self.p1, self.p2) if BEATS[c1] == c2 else (self.p2, self.p1)
            await payout_winner(winner.id, loser.id, pot)
            desc = (
                f"{self.p1.mention} chose **{c1}**, {self.p2.mention} chose **{c2}**.\n"
                f"🏆 {winner.mention} wins **{fmt(pot)}**!"
            )
            e = win_embed("Rock Paper Scissors", desc)
        await interaction.message.edit(embed=e, view=self)
        self.stop()


# ---------------------------------------------------------------------------
# Tic-Tac-Toe
# ---------------------------------------------------------------------------

class TTTButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=index // 3)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        await self.view.play(interaction, self.index, self)


class TTTView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, bet: int):
        super().__init__(timeout=120)
        self.players = [p1, p2]
        self.bet = bet
        self.turn = 0  # index into self.players
        self.board = [None] * 9
        for i in range(9):
            self.add_item(TTTButton(i))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        current = self.players[self.turn]
        if interaction.user.id != current.id:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return False
        return True

    def winner(self):
        lines = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
        for a, b, c in lines:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    async def play(self, interaction: discord.Interaction, index: int, btn: TTTButton):
        if self.board[index] is not None:
            await interaction.response.defer()
            return
        symbol = "❌" if self.turn == 0 else "⭕"
        self.board[index] = symbol
        btn.label = symbol
        btn.disabled = True
        btn.style = discord.ButtonStyle.danger if symbol == "❌" else discord.ButtonStyle.primary

        win_symbol = self.winner()
        pot = self.bet * 2
        if win_symbol:
            winner = self.players[0] if win_symbol == "❌" else self.players[1]
            loser = self.players[1] if win_symbol == "❌" else self.players[0]
            await payout_winner(winner.id, loser.id, pot)
            for c in self.children:
                c.disabled = True
            e = win_embed("Tic-Tac-Toe", f"🏆 {winner.mention} wins **{fmt(pot)}**!")
            await interaction.response.edit_message(embed=e, view=self)
            self.stop()
            return

        if all(cell is not None for cell in self.board):
            await refund_draw(self.players[0].id, self.players[1].id, self.bet)
            for c in self.children:
                c.disabled = True
            e = info_embed("🤝 Draw!", "Board full — bets refunded.")
            await interaction.response.edit_message(embed=e, view=self)
            self.stop()
            return

        self.turn = 1 - self.turn
        e = base_embed(
            "❌⭕ Tic-Tac-Toe",
            f"{self.players[0].mention} (❌) vs {self.players[1].mention} (⭕)\nPot: {fmt(pot)}\n\n"
            f"Now up: {self.players[self.turn].mention}",
            COLOR_PRIMARY,
        )
        await interaction.response.edit_message(embed=e, view=self)


# ---------------------------------------------------------------------------
# Connect 4
# ---------------------------------------------------------------------------

C4_ROWS, C4_COLS = 6, 7


class C4ColumnSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=f"Column {c + 1}", value=str(c)) for c in range(C4_COLS)]
        super().__init__(placeholder="Drop a piece in...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        await self.view.drop(interaction, int(self.values[0]))


class ConnectFourView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, bet: int):
        super().__init__(timeout=180)
        self.players = [p1, p2]
        self.symbols = ["🔴", "🟡"]
        self.bet = bet
        self.turn = 0
        self.grid = [[None] * C4_COLS for _ in range(C4_ROWS)]  # grid[row][col], row 0 = top
        self.select = C4ColumnSelect()
        self.add_item(self.select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.players[self.turn].id:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return False
        return True

    def render_board(self) -> str:
        rows = []
        for r in range(C4_ROWS):
            rows.append("".join(cell or "⚪" for cell in self.grid[r]))
        return "\n".join(rows)

    def check_winner(self, symbol: str) -> bool:
        g = self.grid
        for r in range(C4_ROWS):
            for c in range(C4_COLS):
                if g[r][c] != symbol:
                    continue
                for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
                    count = 0
                    rr, cc = r, c
                    while 0 <= rr < C4_ROWS and 0 <= cc < C4_COLS and g[rr][cc] == symbol:
                        count += 1
                        rr += dr
                        cc += dc
                    if count >= 4:
                        return True
        return False

    async def drop(self, interaction: discord.Interaction, col: int):
        target_row = None
        for r in range(C4_ROWS - 1, -1, -1):
            if self.grid[r][col] is None:
                target_row = r
                break
        if target_row is None:
            await interaction.response.send_message("That column is full.", ephemeral=True)
            return

        symbol = self.symbols[self.turn]
        self.grid[target_row][col] = symbol
        # remove any columns that are now full from the dropdown
        self.select.options = [
            o for o in self.select.options if self.grid[0][int(o.value)] is None
        ]
        if not self.select.options:
            self.select.disabled = True

        pot = self.bet * 2
        if self.check_winner(symbol):
            winner = self.players[self.turn]
            loser = self.players[1 - self.turn]
            await payout_winner(winner.id, loser.id, pot)
            for c in self.children:
                c.disabled = True
            e = win_embed("Connect 4", f"{self.render_board()}\n\n🏆 {winner.mention} wins **{fmt(pot)}**!")
            await interaction.response.edit_message(embed=e, view=self)
            self.stop()
            return

        if all(self.grid[0][c] is not None for c in range(C4_COLS)):
            await refund_draw(self.players[0].id, self.players[1].id, self.bet)
            for c in self.children:
                c.disabled = True
            e = info_embed("🤝 Draw!", f"{self.render_board()}\n\nBoard full — bets refunded.")
            await interaction.response.edit_message(embed=e, view=self)
            self.stop()
            return

        self.turn = 1 - self.turn
        e = base_embed(
            "🔴🟡 Connect 4",
            f"{self.players[0].mention} 🔴 vs {self.players[1].mention} 🟡\nPot: {fmt(pot)}\n\n"
            f"{self.render_board()}\n\nNow up: {self.players[self.turn].mention}",
            COLOR_PRIMARY,
        )
        await interaction.response.edit_message(embed=e, view=self)


# ---------------------------------------------------------------------------
# Blackjack PvP — no dealer, both players play their own hand vs each other
# ---------------------------------------------------------------------------

class BJPvPView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, bet: int, deck: Deck):
        super().__init__(timeout=90)
        self.players = [p1, p2]
        self.hands = [deck.draw(2), deck.draw(2)]
        self.standing = [False, False]
        self.bet = bet
        self.deck = deck
        self.turn = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.players[self.turn].id:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return False
        return True

    def embed(self, footer: str = ""):
        p1, p2 = self.players
        h1, h2 = self.hands
        desc = (
            f"{p1.mention}: {hand_str(h1)} (**{blackjack_value(h1)}**)\n"
            f"{p2.mention}: {hand_str(h2)} (**{blackjack_value(h2)}**)\n\n"
            f"Pot: {fmt(self.bet * 2)}\n"
            f"Now up: {self.players[self.turn].mention}"
        )
        if footer:
            desc += f"\n\n{footer}"
        return base_embed("🃏 Blackjack PvP", desc, COLOR_PRIMARY)

    def _advance_turn(self):
        self.turn = 1 - self.turn
        # skip a player who's already standing/busted
        if self.standing[self.turn]:
            return False  # both done
        return True

    async def _resolve(self, interaction: discord.Interaction):
        for c in self.children:
            c.disabled = True
        v1, v2 = blackjack_value(self.hands[0]), blackjack_value(self.hands[1])
        bust1, bust2 = v1 > 21, v2 > 21
        pot = self.bet * 2

        if bust1 and bust2:
            await refund_draw(self.players[0].id, self.players[1].id, self.bet)
            e = info_embed("🤝 Both Bust — Draw", self.embed().description)
        elif bust1 or (not bust2 and v2 > v1):
            winner, loser = self.players[1], self.players[0]
            await payout_winner(winner.id, loser.id, pot)
            e = win_embed("Blackjack PvP", f"{self.embed().description}\n\n🏆 {winner.mention} wins **{fmt(pot)}**!")
        elif bust2 or v1 > v2:
            winner, loser = self.players[0], self.players[1]
            await payout_winner(winner.id, loser.id, pot)
            e = win_embed("Blackjack PvP", f"{self.embed().description}\n\n🏆 {winner.mention} wins **{fmt(pot)}**!")
        else:
            await refund_draw(self.players[0].id, self.players[1].id, self.bet)
            e = info_embed("🤝 Push — Draw", self.embed().description)

        if interaction is not None:
            await interaction.response.edit_message(embed=e, view=self)
        else:
            await self.message.edit(embed=e, view=self)
        self.stop()

    async def _next_or_resolve(self, interaction: discord.Interaction):
        if all(self.standing):
            await self._resolve(interaction)
            return
        moved = self._advance_turn()
        if not moved:
            await self._resolve(interaction)
            return
        await interaction.response.edit_message(embed=self.embed())

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.hands[self.turn].extend(self.deck.draw(1))
        if blackjack_value(self.hands[self.turn]) >= 21:
            self.standing[self.turn] = True
            await self._next_or_resolve(interaction)
        else:
            await interaction.response.edit_message(embed=self.embed())

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.standing[self.turn] = True
        await self._next_or_resolve(interaction)

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class PvP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _validate_challenge(self, ctx: commands.Context, opponent: discord.Member, bet: str):
        """Common checks. Returns the resolved bet amount, or None (and sends an error) on failure."""
        if opponent.bot or opponent.id == ctx.author.id:
            await ctx.send(embed=error_embed("Pick a real opponent (not yourself or a bot)."))
            return None
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return None
        opp_balance = await db.get_balance(opponent.id)
        if opp_balance < amount:
            await ctx.send(embed=error_embed(f"{opponent.display_name} doesn't have enough balance for this bet."))
            return None
        return amount

    async def _send_challenge(self, ctx: commands.Context, opponent: discord.Member, amount: int, game_name: str, launch):
        view = ChallengeView(ctx, opponent, amount, launch)
        await ctx.send(
            embed=info_embed(
                f"⚔️ {game_name} Challenge",
                f"{opponent.mention}, {ctx.author.mention} challenges you to **{game_name}** for {fmt(amount)}!\nAccept?",
            ),
            view=view,
        )

    @commands.hybrid_command(name="rps", description="Rock-paper-scissors against another user for points.")
    @app_commands.describe(opponent="Who to challenge", bet="Amount to bet")
    async def rps(self, ctx: commands.Context, opponent: discord.Member, bet: str):
        amount = await self._validate_challenge(ctx, opponent, bet)
        if amount is None:
            return

        async def launch(interaction: discord.Interaction):
            view = RPSView(ctx.author, opponent, amount)
            e = info_embed(
                "🪨📄✂️ Rock Paper Scissors",
                f"{ctx.author.mention} vs {opponent.mention} — pot: {fmt(amount * 2)}\n"
                f"Both players: pick your move below (your choice is private).",
            )
            await interaction.response.edit_message(embed=e, view=view)

        await self._send_challenge(ctx, opponent, amount, "Rock Paper Scissors", launch)

    @commands.hybrid_command(name="connect4", aliases=["c4"], description="Connect 4 against another user.")
    @app_commands.describe(opponent="Who to challenge", bet="Amount to bet")
    async def connect4(self, ctx: commands.Context, opponent: discord.Member, bet: str):
        amount = await self._validate_challenge(ctx, opponent, bet)
        if amount is None:
            return

        async def launch(interaction: discord.Interaction):
            view = ConnectFourView(ctx.author, opponent, amount)
            e = base_embed(
                "🔴🟡 Connect 4",
                f"{ctx.author.mention} 🔴 vs {opponent.mention} 🟡\nPot: {fmt(amount * 2)}\n\n"
                f"{view.render_board()}\n\nNow up: {ctx.author.mention}",
                COLOR_PRIMARY,
            )
            await interaction.response.edit_message(embed=e, view=view)

        await self._send_challenge(ctx, opponent, amount, "Connect 4", launch)

    @commands.hybrid_command(name="ttt", description="Tic-tac-toe against another user.")
    @app_commands.describe(opponent="Who to challenge", bet="Amount to bet")
    async def ttt(self, ctx: commands.Context, opponent: discord.Member, bet: str):
        amount = await self._validate_challenge(ctx, opponent, bet)
        if amount is None:
            return

        async def launch(interaction: discord.Interaction):
            view = TTTView(ctx.author, opponent, amount)
            e = base_embed(
                "❌⭕ Tic-Tac-Toe",
                f"{ctx.author.mention} (❌) vs {opponent.mention} (⭕)\nPot: {fmt(amount * 2)}\n\n"
                f"Now up: {ctx.author.mention}",
                COLOR_PRIMARY,
            )
            await interaction.response.edit_message(embed=e, view=view)

        await self._send_challenge(ctx, opponent, amount, "Tic-Tac-Toe", launch)

    @commands.hybrid_command(name="blackjackpvp", aliases=["bjpvp"], description="Play Blackjack against another user. Winner takes the pot.")
    @app_commands.describe(opponent="Who to challenge", bet="Amount to bet")
    async def blackjackpvp(self, ctx: commands.Context, opponent: discord.Member, bet: str):
        amount = await self._validate_challenge(ctx, opponent, bet)
        if amount is None:
            return

        async def launch(interaction: discord.Interaction):
            deck = Deck()
            view = BJPvPView(ctx.author, opponent, amount, deck)
            await interaction.response.edit_message(embed=view.embed(), view=view)

        await self._send_challenge(ctx, opponent, amount, "Blackjack PvP", launch)

    @commands.hybrid_command(name="fight", description="Fight another user (or the house) in a PvP battle.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')", opponent="Who to fight (omit to fight the house)")
    async def fight(self, ctx: commands.Context, bet: str, opponent: discord.Member = None):
        if opponent is None or opponent.id == self.bot.user.id:
            try:
                amount = await resolve_bet(ctx.author.id, bet)
            except BetError as e:
                await ctx.send(embed=error_embed(str(e)))
                return
            await db.try_take(ctx.author.id, amount)
            won = random.random() < 0.48
            payout = int(amount * 1.92) if won else 0
            await db.record_result(ctx.author.id, payout, won)
            new_bal = await db.get_balance(ctx.author.id)
            if won:
                e = win_embed("⚔️ You Won the Fight!", f"You beat the house and won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            else:
                e = lose_embed("⚔️ You Lost the Fight", f"The house wins this one.\nYou lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
            await ctx.send(embed=e)
            return

        amount = await self._validate_challenge(ctx, opponent, bet)
        if amount is None:
            return

        async def launch(interaction: discord.Interaction):
            pot = amount * 2
            winner, loser = (ctx.author, opponent) if random.random() < 0.5 else (opponent, ctx.author)
            await payout_winner(winner.id, loser.id, pot)
            e = win_embed("⚔️ Fight!", f"{ctx.author.mention} vs {opponent.mention}\n\n🏆 {winner.mention} wins **{fmt(pot)}**!")
            await interaction.response.edit_message(embed=e, view=None)

        await self._send_challenge(ctx, opponent, amount, "Fight", launch)


async def setup(bot: commands.Bot):
    await bot.add_cog(PvP(bot))
