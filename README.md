# NeonVault — Discord Casino Bot (Virtual Currency)

A full-featured, **play-money-only** casino bot built with discord.py. Every
game uses "Shards" — an in-server points currency with no real-world value.
There is no deposit/withdraw system and no conversion to any real currency.

## Games included
Coinflip, Dice (1-100), Slots, Blackjack, Crash, Limbo, Mines, Roulette
(American), Plinko, Keno, Video Poker (Jacks or Better), Rock-Paper-Scissors,
Connect 4, and Tic-Tac-Toe (the last three are PvP, wagered against another
member).

## Economy & Admin
- `balance`, `daily`, `leaderboard`, `stats`, `tip`
- Admin-only (Administrator permission, or a role named `Casino Admin`):
  `give`, `remove`, `setbalance`, `tipall`, `resetbalance`

Commands work as both slash commands (`/balance`) and prefix commands
(`!balance`) since everything is a `hybrid_command`.

## Setup

1. Create a Discord application + bot at https://discord.com/developers/applications
   - Under **Bot**, enable the **Server Members Intent** and
     **Message Content Intent**.
   - Copy the bot token.
2. Install dependencies (Pillow is used to render the balance card and
   blackjack table as images):
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and paste your token:
   ```
   cp .env.example .env
   ```
4. Invite the bot to your server with the `bot` and `applications.commands`
   scopes, and at least these permissions: Send Messages, Embed Links,
   Attach Files, Use External Emojis, Read Message History, Use Application
   Commands.
5. Run it:
   ```
   python main.py
   ```

Optional: drop `Inter-Bold.ttf` / `Inter-Regular.ttf` (or any TTF you like,
just rename them) into a `fonts/` folder in the project root for nicer
typography on the image cards. Without them, Pillow's built-in font is used
and everything still works fine.

Slash commands can take up to an hour to appear globally the first time;
for instant testing, sync them to a single guild (ask me if you want a
guild-sync snippet added to `main.py`).

Every command also has a short prefix alias (e.g. `.b` for balance, `.bj`
for blackjack, `.g` for the admin give command) — see `.help` for the full
list, or `cogs/help.py`.

## Admin-only help

Non-admins never see the Admin category in `.help` — it's filtered out of
both the main menu and the category dropdown, and re-checked server-side
if someone tries to select it anyway.

## Project layout
```
main.py                 bot entrypoint, loads all cogs
config.py                colors, emojis, embed helpers — edit this to reskin the bot
database.py              async SQLite persistence (casino.db, created on first run)
utils.py                 bet parsing ("500", "half", "all"), card deck
cogs/economy.py           balance / daily / leaderboard / stats / tip
cogs/admin.py             give / remove / setbalance / tipall / resetbalance
cogs/help.py              dropdown help menu
cogs/games/*.py           one file per game
```

## Extending
Every game is a self-contained cog in `cogs/games/`. To add a new one, copy
the closest existing game as a template, then add its module path to
`INITIAL_EXTENSIONS` in `main.py`.

## Note on scope
This intentionally does not include deposit/withdraw, real-currency
conversion, VIP/rakeback loyalty tiers, or an affiliate/referral system.
Those are the pieces that turn a fun points bot into a real-money gambling
operation, which requires gambling licensing in most places — outside what
this project is for.

## Running 24/7

`python main.py` only stays up as long as your terminal/computer does — closing
the laptop or losing power kills it. The code now auto-restarts itself on an
internal crash (`run_forever()` in `main.py`, with backoff), but that's not
the same as keeping the *process* running when your machine sleeps, restarts,
or you close the terminal. That part depends on where you run it:

**Option A — Your own computer, always on**
Use a process manager so it survives terminal close/reboot:
- macOS/Linux: `pm2 start main.py --name neonvault --interpreter venv/bin/python3` (install pm2 via `npm install -g pm2`, then `pm2 save` + `pm2 startup` to survive reboots)
- Linux server: use the included `neonvault-bot.service` — edit the paths inside it, then:
  ```
  sudo cp neonvault-bot.service /etc/systemd/system/
  sudo systemctl enable --now neonvault-bot
  ```

**Option B — A cheap VPS** (DigitalOcean, Linode, Hetzner, ~$4-6/mo)
SSH in, clone/upload the project, follow the systemd steps above. This is the
standard way to run a Discord bot 24/7 without keeping your own PC on.

**Option C — A PaaS** (Railway, Render, Fly.io)
The included `Procfile` (`worker: python main.py`) is ready for these. Push
the repo, set `DISCORD_TOKEN` as an environment variable in their dashboard
instead of a `.env` file, and they handle uptime/restarts for you. Free tiers
often sleep on inactivity — check current pricing before relying on one.

Whichever you choose, logs also now write to `bot.log` in the project folder
(as well as the terminal), which helps when you're not watching it live.

## Rain commands

- `.rain <amount>` — splits the amount across everyone who's posted in the
  channel in the last 15 minutes (excluding you and bots).
- `.rainwheel <amount>` — opens a 20-second join lobby; one random joiner
  takes the entire pot. Refunds you if nobody joins.

## Animations

Most games that previously just showed a static "..." for a second now run
through `animations.py`'s shared progress-bar suspense sequence before
revealing the result. Slots/roulette/plinko/horse/crash keep their own
custom frame-by-frame animations since those benefit from showing the
actual reels/wheel/track mid-spin rather than a generic bar.

## Running on Replit (free, no card, with UptimeRobot)

Files already included for this: `.replit`, `start.sh`, `keep_alive.py`.

1. Create a free Replit account (no card required) and make a new Python repl.
2. Upload every file from this project into it (or import the zip).
3. In the repl's **Secrets** tab (padlock icon in the sidebar), add a secret
   named `DISCORD_TOKEN` with your bot token as the value. Do **not** use a
   `.env` file on Replit — Secrets are the safe way to store it there.
4. Click **Run**. `start.sh` installs dependencies and starts the bot.
   `keep_alive.py` automatically spins up a small web server (only on
   Replit — it's a no-op anywhere else) so the repl has something to answer
   pings on.
5. Copy the webview URL Replit shows you (looks like
   `https://your-repl-name.your-username.repl.co`).
6. Create a free UptimeRobot account (uptimerobot.com, no card), add a new
   **HTTP(s) monitor** pointing at that URL, checking every 5 minutes.
   UptimeRobot pinging it is what keeps Replit from putting it to sleep.

This is less reliable than owning always-on hardware — expect occasional
gaps if Replit restarts the repl or changes free-tier behavior — but it
costs nothing and needs no payment method anywhere in the chain.

## Running on Render (free, no card, alternative to Replit)

Render tends to be more reliable than Replit for keeping a background
process alive. Free tier, no card required for signup.

1. Push this project to a GitHub repo (see steps below if you don't already
   use git/GitHub — you can do the whole thing through the website, no
   command line needed).
2. Create a free Render account at render.com (sign in with GitHub is
   easiest — no card needed).
3. Dashboard → **New** → **Web Service** → connect the GitHub repo you just
   made.
4. Set:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python3 main.py`
5. Add an environment variable: `DISCORD_TOKEN` = your bot token (Render's
   dashboard has an "Environment" tab for this — same idea as Replit
   Secrets, don't use a `.env` file here either).
6. Deploy. Once it's live, Render gives you a URL
   (`https://your-service.onrender.com`) — the `keep_alive.py` server
   already included answers on that automatically once `RENDER=true` is
   detected in the environment (Render sets this for you, nothing to
   configure).
7. Same as before: add that URL to a free UptimeRobot HTTP monitor, 5-minute
   interval, to stop Render's free tier from spinning the service down on
   inactivity.

### Getting the code onto GitHub without using git commands

1. Create a free GitHub account at github.com (no card).
2. Click the **+** in the top right → **New repository** → give it a name
   → **Create repository**.
3. On the new repo's page, click **Add file → Upload files**, then drag the
   entire unzipped `gambling-bot` folder's contents in. GitHub's web
   uploader handles this fine for a project this size.
4. Commit the upload. That's the repo Render connects to in step 3 above.
