import argparse
import os

from dotenv import load_dotenv

from bots.core.bot import Bot

load_dotenv(verbose=True)

CODERUNBOT_TOKEN = os.environ.get('CODERUNBOT_TOKEN')
GAATO_BOT_TOKEN = os.environ.get('GAATO_BOT_TOKEN')

CODERUNBOT_COGS = ['bots.cogs.TeX', 'bots.cogs.Code', 'bots.cogs.Privacy']
GAATO_BOT_COGS = ['bots.cogs.TeX', 'bots.cogs.Code', 'bots.cogs.Privacy', 'bots.cogs.Wolfram', 'bots.cogs.Misc', 'bots.cogs.Translate', 'bots.cogs.ShuYoJo']

parser = argparse.ArgumentParser()
parser.add_argument('-g', '--gaato-bot',
                    help='run gaato-bot',
                    action='store_true')
args = parser.parse_args()


if args.gaato_bot:
    Bot(GAATO_BOT_TOKEN, GAATO_BOT_COGS, ')').run()
else:
    Bot(CODERUNBOT_TOKEN, CODERUNBOT_COGS, ']').run()
