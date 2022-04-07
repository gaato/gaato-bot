import pathlib

from discord.ext import commands


BADE_DIR = pathlib.Path(__file__).parent.parent


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='privacy-policy')
    async def privacy_policy(self, ctx: commands.Context):
        with open(BADE_DIR / 'config' / 'privacy-policy.md', 'r') as f:
            await ctx.send(f.read())


def setup(bot):
    return bot.add_cog(Misc(bot))
