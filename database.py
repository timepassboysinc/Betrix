"""
Async SQLite persistence layer. One connection pool shared across the bot.
Everything here is virtual points only — no real-world currency value.
"""
import aiosqlite
import time
from config import STARTING_BALANCE

DB_PATH = "casino.db"

_conn: aiosqlite.Connection | None = None


async def init_db():
    global _conn
    _conn = await aiosqlite.connect(DB_PATH)
    await _conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0,
            last_daily REAL NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            wagered INTEGER NOT NULL DEFAULT 0,
            net_profit INTEGER NOT NULL DEFAULT 0
        )
    """)
    await _conn.execute("""
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER
        )
    """)
    await _conn.commit()


async def _ensure_user(user_id: int):
    await _conn.execute(
        "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, ?)",
        (user_id, STARTING_BALANCE),
    )
    await _conn.commit()


async def get_balance(user_id: int) -> int:
    await _ensure_user(user_id)
    async with _conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
        return row[0] if row else 0


async def add_balance(user_id: int, amount: int):
    """amount can be negative"""
    await _ensure_user(user_id)
    await _conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id)
    )
    await _conn.commit()


async def set_balance(user_id: int, amount: int):
    await _ensure_user(user_id)
    await _conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
    await _conn.commit()


async def try_take(user_id: int, amount: int) -> bool:
    """Atomically deduct `amount` if the user can afford it. Returns False if insufficient funds."""
    await _ensure_user(user_id)
    async with _conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    if not row or row[0] < amount:
        return False
    await _conn.execute(
        "UPDATE users SET balance = balance - ?, wagered = wagered + ? WHERE user_id = ?",
        (amount, amount, user_id),
    )
    await _conn.commit()
    return True


async def record_result(user_id: int, payout: int, won: bool):
    """payout = amount credited back (0 if total loss). won = whether it counts as a win stat."""
    await _ensure_user(user_id)
    if payout:
        await _conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?", (payout, user_id)
        )
    await _conn.execute(
        "UPDATE users SET wins = wins + ?, losses = losses + ?, net_profit = net_profit + ? WHERE user_id = ?",
        (1 if won else 0, 0 if won else 1, payout, user_id),
    )
    await _conn.commit()


async def get_last_daily(user_id: int) -> float:
    await _ensure_user(user_id)
    async with _conn.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
        return row[0] if row else 0.0


async def set_last_daily(user_id: int, ts: float | None = None):
    await _ensure_user(user_id)
    ts = ts if ts is not None else time.time()
    await _conn.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (ts, user_id))
    await _conn.commit()


async def get_stats(user_id: int) -> dict:
    await _ensure_user(user_id)
    async with _conn.execute(
        "SELECT balance, wins, losses, wagered, net_profit FROM users WHERE user_id = ?",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    return {
        "balance": row[0],
        "wins": row[1],
        "losses": row[2],
        "wagered": row[3],
        "net_profit": row[4],
    }


async def get_leaderboard(limit: int = 10) -> list[tuple[int, int]]:
    async with _conn.execute(
        "SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)
    ) as cur:
        return await cur.fetchall()


async def get_all_user_ids() -> list[int]:
    async with _conn.execute("SELECT user_id FROM users") as cur:
        rows = await cur.fetchall()
        return [r[0] for r in rows]
