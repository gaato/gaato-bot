import os

from dotenv import load_dotenv

from gaato_bot.core.bot import GaatoBot

load_dotenv(verbose=True)
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
GaatoBot(DISCORD_TOKEN).run()
