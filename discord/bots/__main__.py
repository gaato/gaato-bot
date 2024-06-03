import os

from bots.core.bot import Bot
from dotenv import load_dotenv

load_dotenv(verbose=True)

CODERUNBOT_TOKEN = os.environ.get("CODERUNBOT_TOKEN")
GAATO_BOT_TOKEN = os.environ.get("GAATO_BOT_TOKEN")

CODERUNBOT_COGS = ["bots.cogs.TeX", "bots.cogs.Code", "bots.cogs.Privacy"]
GAATO_BOT_COGS = [
    "bots.cogs.TeX",
    "bots.cogs.Code",
    "bots.cogs.Privacy",
    "bots.cogs.Wolfram",
    "bots.cogs.Misc",
    "bots.cogs.Translate",
]

if os.environ.get("GAATO_BOT"):
    Bot(GAATO_BOT_TOKEN, GAATO_BOT_COGS, ")").run()
else:
    Bot(CODERUNBOT_TOKEN, CODERUNBOT_COGS, "]").run()
