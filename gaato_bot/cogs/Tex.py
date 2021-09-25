import base64
import io
import urllib

import discord
import aiohttp
from discord.ext import commands
from gaato_bot.core.bot import GaatoBot

async def response(ctx: commands.Context, arg: str, command: str, spoiler: bool):

    arg = arg.replace('```tex', '').replace('```', '')

    url = f'http://localhost/{command}/' + urllib.parse.quote(arg, safe='')
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            if r.status == 200:
                result = await r.json()
            else:
                embed = discord.Embed(
                    title='接続エラー',
                    description=f'{r.status}',
                    color=0xff0000,
                )
                return await ctx.send(embed=embed)

    if result['status'] == 0:
        embed = discord.Embed(color=0x008000)
        embed.set_author(
            name=ctx.author.name,
            icon_url=ctx.author.display_avatar.url,
        )
        if command != 'texpdf':
            embed.set_image(url='attachment://tex.png')
        return await ctx.send(
            file=discord.File(
                io.BytesIO(base64.b64decode(result['result'])),
                filename='tex.pdf' if command == 'texpdf' else 'tex.png',
                spoiler=spoiler,
            ),
            embed=embed,
        )
    elif result['status'] == 1:
        embed = discord.Embed(
            title='レンダリングエラー',
            description=f'```\n{result["error"]}\n```',
            color=0xff0000,
        )
        embed.set_author(
            name=ctx.author.name,
            icon_url=ctx.author.display_avatar.url,
        )
        return await ctx.send(embed=embed)
    elif result['status'] == 2:
        embed = discord.Embed(
            title='タイムアウト',
            color=0xff0000,
        )
        embed.set_author(
            name=ctx.author.name,
            icon_url=ctx.author.display_avatar,
        )
        return await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title='未知のエラー',
            color=0xff0000,
        )
        embed.set_author(
            name=ctx.author.name,
            icon_url=ctx.author.display_avatar.url,
        )
        return await ctx.send(embed=embed)


class Tex(commands.Cog):

    def __init__(self, bot: GaatoBot):
        self.bot = bot

    @commands.command()
    async def tex(self, ctx: commands.Context, *, arg: str):
        await response(ctx, arg, 'tex', False)

    @commands.command()
    async def stex(self, ctx: commands.Context, *, arg: str):
        await response(ctx, arg, 'tex', True)

    @commands.command()
    async def texp(self, ctx: commands.Context, *, arg: str):
        await response(ctx, arg, 'texp', False)

    @commands.command()
    async def stexp(self, ctx: commands.Context, *, arg: str):
        await response(ctx, arg, 'texp', True)

    @commands.command()
    async def texpdf(self, ctx: commands.Context, *, arg: str):
        await response(ctx, arg, 'texpdf', False)


def setup(bot):
    return bot.add_cog(Tex(bot))
