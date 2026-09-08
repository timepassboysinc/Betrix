"""
Free hosting tiers (Replit, Render's free Web Service, etc.) sleep an app
after a period of no incoming web traffic. This spins up a minimal web
server so an external pinger (like UptimeRobot, also free) can hit it every
few minutes and keep the host awake.

Only used when running on a hosted platform that needs it — main.py only
imports/calls this when it detects REPL_ID or RENDER in the environment, so
it's a no-op everywhere else (your own PC, a VPS, etc.).
"""
import os
from threading import Thread

from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "NeonVault is alive."


def _run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    Thread(target=_run, daemon=True).start()
