import io
import json
import pathlib
import re
from collections import OrderedDict
from typing import Optional, Union, Tuple, List

import aiohttp
import discord
from discord.interactions import Interaction
import requests
from discord.ext import commands, tasks
from discord.commands import message_command, slash_command

from .. import SUPPORT_SERVER_LINK, DeleteButton, LimitedSizeDict


URL = 'https://wandbox.org/api/'
BASE_DIR = pathlib.Path(__file__).parent.parent


def get_autocomplete_languages() -> List[str]:
    with requests.get(URL + 'list.json') as r:
        r.raise_for_status()
        result = r.json()
        language_names = set(map(lambda data: data['language'].lower().replace(' ', ''), result))
        print(list(language_names))
        return list(language_names)

autocomplete_languages = get_autocomplete_languages()

def auto_complete_language(ctx: discord.AutocompleteContext) -> List[str]:
    return list(
        filter(
            lambda language_code: language_code.startswith(ctx.value.lower()),
            autocomplete_languages,
        )
    )


async def get_languages() -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(URL + 'list.json') as r:
            if r.status == 200:
                result = await r.json()
                language_names = set(
                    map(lambda data: data['language'], result))
                languages_dict = {}
                for language_name in language_names:
                    language_information = next(filter(
                        lambda language_information: language_information['language'] == language_name, result))
                    languages_dict[language_name.lower().replace(
                        ' ', '')] = language_information['name']
    return languages_dict


async def run_core(
        ctx: Union[discord.ApplicationContext, commands.Context],
        language: str, code: str,
        stdin: str = '',
) -> Tuple[discord.Embed, Optional[discord.File]]:
    language_dict = await get_languages()
    language = language.lower() \
        .replace('pp', '++').replace('sharp', '#') \
        .replace('clisp', 'lisp')
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
        return embed, None
    if language == 'nim':
        compiler_option = '--hint[Processing]:off\n' \
            '--hint[Conf]:off\n' \
            '--hint[Link]:off\n' \
            '--hint[SuccessX]:off'
    else:
        compiler_option = ''
    url = URL + 'compile.json'
    params = {
        'compiler': language_dict[language],
        'code': code,
        'stdin': stdin,
        'compiler-option-raw': compiler_option,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=params) as r:
            if r.status == 200:
                result = await r.json()
            else:
                embed = discord.Embed(
                    title='Connection Error',
                    description=f'{r.status}',
                    color=0xff0000
                )
                embed.set_author(
                    name=ctx.author.name,
                    icon_url=ctx.author.display_avatar.url
                )
                return embed, None
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
    return embed, files


class RunModal(discord.ui.Modal):
    def __init__(self, ctx: commands.Context, language: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ctx = ctx
        self.language = language
        self.add_item(discord.ui.InputText(
            label='Code',
            placeholder='Write code here',
            style=discord.InputTextStyle.long,
        ))
        self.add_item(discord.ui.InputText(
            label='Standard Input',
            required=False,
            style=discord.InputTextStyle.long,
        ))

    async def callback(self, interaction: Interaction):
        await interaction.response.defer(invisible=False)
        embed, files = await run_core(self.ctx, self.language, self.children[0].value, self.children[1].value)
        await interaction.followup.send(embed=embed, files=files)


class Code(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_message_id_to_bot_message = LimitedSizeDict(size_limit=100)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.content != after.content:
            if before.id in self.user_message_id_to_bot_message:
                await self.user_message_id_to_bot_message[before.id].delete()

    @commands.command()
    async def run(self, ctx: commands.Context, language: str, *, code: str):
        """Run code"""
        view = discord.ui.View(DeleteButton(self.bot))
        embed, files = await run_core(ctx, language, code)
        m = await ctx.reply(embed=embed, files=files, view=view)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @message_command()
    async def escape(self, ctx: discord.ApplicationContext, message: discord.Message):
        await ctx.respond(discord.utils.escape_markdown(discord.utils.escape_mentions(message.content)), ephemeral=True)

    @discord.slash_command(
        name='run',
        description='Run code',
        options=[discord.Option(
            name='language',
            description='Language',
            required=True,
            autocomplete=auto_complete_language,
        )]
    )
    async def run_slash(self, ctx: discord.ApplicationContext, language: str):
        await ctx.send_modal(RunModal(ctx, language, title='RUn code'))


def setup(bot):
    return bot.add_cog(Code(bot))
