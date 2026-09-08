import random

import database as db

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠", "♥", "♦", "♣"]


class Card:
    __slots__ = ("rank", "suit")

    def __init__(self, rank: str, suit: str):
        self.rank = rank
        self.suit = suit

    def __str__(self):
        return f"{self.rank}{self.suit}"

    @property
    def value(self) -> int:
        if self.rank in ("J", "Q", "K"):
            return 10
        if self.rank == "A":
            return 11
        return int(self.rank)

    @property
    def rank_index(self) -> int:
        return RANKS.index(self.rank)


class Deck:
    def __init__(self):
        self.cards = [Card(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.cards)

    def draw(self, n: int = 1) -> list[Card]:
        drawn = self.cards[:n]
        self.cards = self.cards[n:]
        return drawn


def hand_str(cards: list[Card]) -> str:
    return " ".join(str(c) for c in cards)


def blackjack_value(cards: list[Card]) -> int:
    total = sum(c.value for c in cards)
    aces = sum(1 for c in cards if c.rank == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


class BetError(Exception):
    pass


async def resolve_bet(user_id: int, bet_str: str) -> int:
    """Parse a bet string ('500', 'all', 'half') against the user's balance.
    Raises BetError with a user-facing message on any problem."""
    balance = await db.get_balance(user_id)
    bet_str = bet_str.strip().lower()

    if bet_str in ("all", "allin", "max"):
        amount = balance
    elif bet_str == "half":
        amount = balance // 2
    else:
        cleaned = bet_str.replace(",", "")
        multiplier = 1
        if cleaned.endswith("k"):
            multiplier = 1_000
            cleaned = cleaned[:-1]
        elif cleaned.endswith("m"):
            multiplier = 1_000_000
            cleaned = cleaned[:-1]
        try:
            amount = int(float(cleaned) * multiplier)
        except ValueError:
            raise BetError(f"'{bet_str}' isn't a valid bet. Try a number, `half`, or `all`.")

    if amount <= 0:
        raise BetError("Bet must be greater than 0.")
    if amount > balance:
        raise BetError(f"You only have **{balance:,}** points — you can't bet that much.")
    return amount
