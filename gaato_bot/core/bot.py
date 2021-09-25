import discord
from discord.ext import commands
import traceback


class GaatoBot(commands.Bot):
    def __init__(self, token):
        self.token = token
        super().__init__(command_prefix=')')
        self.load_cogs()

    def load_cogs(self):
        cogs = ['gaato_bot.cogs.Voice', 'gaato_bot.cogs.Tex']
        for cog in cogs:
            self.load_extension(cog)
            print(cog + 'をロードしました')

    async def on_ready(self):
        print('起動しました')

    # 起動用の補助関数です
    def run(self):
        try:
            self.loop.run_until_complete(self.start(self.token))
        except discord.LoginFailure:
            print('Discord Tokenが不正です')
        except KeyboardInterrupt:
            print('終了します')
            self.loop.run_until_complete(self.logout())
        except:
            traceback.print_exc()