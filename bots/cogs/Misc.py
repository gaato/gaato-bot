import pathlib

import discord
from discord.ext import commands
from sudachipy import tokenizer, dictionary

from .. import DeleteButton


BASE_DIR = pathlib.Path(__file__).parent.parent


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tokenizer_obj = dictionary.Dictionary().create()

    @discord.slash_command(
        name='sudachi',
        description='形態素解析',
    )
    async def sudachi(self, ctx: discord.ApplicationContext, text: str):
        """形態素解析"""
        mode = tokenizer.Tokenizer.SplitMode.C
        tokens = self.tokenizer_obj.tokenize(text, mode)
        outputs = [f'{text}']
        for t in tokens:
            outputs.append(f'{t.surface()}\t{",".join(t.part_of_speech())}\t{t.reading_form()}\t{t.normalized_form()}')
        view = discord.ui.View(DeleteButton(ctx.author), timeout=None)
        await ctx.respond(f'```\n' + '\n'.join(outputs) + '\n```', view=view)


def setup(bot: commands.Bot):
    return bot.add_cog(Misc(bot))