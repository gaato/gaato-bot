import io
import json
import pathlib
import re

import aiohttp
import discord
from discord.ext import commands


URL = 'https://wandbox.org/api/compile.json'
BASE_DIR = pathlib.Path(__file__).parent.parent


class LimitedSizeDict(dict):

    def __init__(self, size_limit=None, *args, **kwds):
        self.size_limit = size_limit
        super().__init__(*args, **kwds)
        self._check_size_limit()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._check_size_limit()

    def _check_size_limit(self):
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                self.popitem(last=False)


class DeleteButton(discord.ui.Button):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__(label='Delete')

    async def callback(self, interaction: discord.Interaction):
        if (message := interaction.message.reference.cached_message) is None:
            channel = await self.bot.fetch_channel(interaction.message.reference.channel_id)
            message = await channel.fetch_message(interaction.message.reference.message_id)
        if interaction.user.id == message.author.id:
            await interaction.message.delete()


class Code(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_message_id_to_bot_message = LimitedSizeDict(size_limit=100)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.content != after.content:
            if before.id in self.user_message_id_to_bot_message:
                await self.user_message_id_to_bot_message[before.id].delete()

    async def _run(self, ctx: commands.Context, language: str, code: str):

        view = discord.ui.View(DeleteButton(self.bot))

        with open(BASE_DIR / 'config' / 'languages.json', 'r') as f:
            language_dict = json.load(f)
        code = re.sub(r'```[A-z\-\+]*\n', '', code).replace('```', '')
        stdin = ''
        language = language.lower() \
            .replace('pp', '++').replace('sharp', '#') \
            .replace('clisp', 'lisp').replace('lisp', 'clisp')
        if language not in language_dict.keys():
            embed = discord.Embed(
                title='The following languages are supported',
                description=', '.join(language_dict.keys()),
                color=0xff0000
            )
            embed.set_author(
                name=ctx.author.name,
                icon_url=ctx.author.display_avatar.url
            )
            return await ctx.reply(embed=embed, view=view)
        if language == 'nim':
            compiler_option = '--hint[Processing]:off\n' \
                '--hint[Conf]:off\n' \
                '--hint[Link]:off\n' \
                '--hint[SuccessX]:off'
        else:
            compiler_option = ''
        params = {
            'compiler': language_dict[language],
            'code': code,
            'stdin': stdin,
            'compiler-option-raw': compiler_option,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(URL, json=params) as r:
                if r.status == 200:
                    result = await r.json()
                else:
                    embed = discord.Embed(
                        title='Connection Error',
                        description=f'{r.status}',
                        color=0xff0000
                    )
                    return await ctx.reply(embed=embed, view=view)

        embed = discord.Embed(title='Result')
        embed_color = 0xff0000
        files = []
        for k, v in result.items():
            if k in ('program_message', 'compiler_message'):
                continue
            if v == '':
                continue
            if k == 'status' and v == '0':
                embed_color = 0x007000
            if language == 'nim' and k == 'compiler_error':
                v = re.sub(r'CC: \S+\n', '', v)
                if v == '':
                    continue
            if len(v) > 1000 or len(v.split('\n')) > 100:
                files.append(
                    discord.File(
                        io.StringIO(v),
                        k + '.txt'
                    )
                )
            else:
                embed.add_field(
                    name=k,
                    value='```\n' + v + '\n```',
                )
        embed.color = embed_color
        embed.set_author(
            name=ctx.author.name,
            icon_url=ctx.author.display_avatar.url
        )
        return await ctx.reply(embed=embed, files=files, view=view)

    @commands.command()
    async def run(self, ctx: commands.Context, language: str, *, code: str):
        """Run code"""
        m = await self._run(ctx, language, code)
        self.user_message_id_to_bot_message[ctx.message.id] = m


def setup(bot):
    return bot.add_cog(Code(bot))
