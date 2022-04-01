import argparse
import os

from dotenv import load_dotenv

from bots.core.bot import Bot

load_dotenv(verbose=True)

CODERUNBOT_TOKEN = os.environ.get('CODERUNBOT_TOKEN')
GAATO_BOT_TOKEN = os.environ.get('GAATO_BOT_TOKEN')

coderunbot_cogs = ['bots.cogs.TeX', 'bots.cogs.Code']
gaato_bot_cogs = ['bots.cogs.Voice', 'bots.cogs.TeX', 'bots.cogs.Code']

parser = argparse.ArgumentParser()
parser.add_argument('-g', '--gaato-bot',
                    help='run gaato-bot',
                    action='store_true')
args = parser.parse_args()


if args.gaato_bot:
    Bot(GAATO_BOT_TOKEN, gaato_bot_cogs, ')').run()
else:
    Bot(CODERUNBOT_TOKEN, coderunbot_cogs, ']').run()
