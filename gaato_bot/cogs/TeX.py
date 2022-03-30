import base64
import io
from typing import Optional

import aiohttp
import discord
from discord.ext import commands


class TeX(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def response(self, ctx: commands.Context, code: str, file_type: str, plain: Optional[bool], spoiler: bool):

        async with ctx.channel.typing():

            button = discord.ui.Button(label='削除')
            async def button_callback(interaction: discord.Interaction):
                if interaction.user.id == interaction.message.reference.cached_message.author.id:
                    await interaction.message.delete()
            button.callback = button_callback
            view = discord.ui.View(button)

            code = code.replace('```tex', '').replace('```', '').strip()

            url = f'https://gaato.net/api/tex'
            params = {
                'type': file_type,
                'plain': plain,
                'code': code,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=params) as r:
                    if r.status == 200:
                        result = await r.json()
                    else:
                        embed = discord.Embed(
                            title='Connection Error',
                            description=f'{r.status}',
                            color=0xff0000,
                        )
                        return await ctx.reply(embed=embed, view=view)

            match result['status']:
                case 0:
                    embed = discord.Embed(color=0x008000)
                    embed.set_author(
                        name=ctx.author.name,
                        icon_url=ctx.author.display_avatar.url,
                    )
                    if file_type == 'png':
                        embed.set_image(url='attachment://tex.png')
                    return await ctx.reply(
                        file=discord.File(
                            io.BytesIO(base64.b64decode(result['result'])),
                            filename='tex.pdf' if file_type == 'pdf' else 'tex.png',
                            spoiler=spoiler,
                        ),
                        embed=embed,
                        view=view,
                    )
                case 1:
                    embed = discord.Embed(
                        title='Rendering Error',
                        description=f'```\n{result["error"]}\n```',
                        color=0xff0000,
                    )
                    embed.set_author(
                        name=ctx.author.name,
                        icon_url=ctx.author.display_avatar.url,
                    )
                    return await ctx.reply(embed=embed, view=view)
                case 2:
                    embed = discord.Embed(
                        title='Timed Out',
                        color=0xff0000,
                    )
                    embed.set_author(
                        name=ctx.author.name,
                        icon_url=ctx.author.display_avatar,
                    )
                    return await ctx.reply(embed=embed, view=view)
                case _:
                    embed = discord.Embed(
                        title='Unhandled Error',
                        color=0xff0000,
                    )
                    embed.set_author(
                        name=ctx.author.name,
                        icon_url=ctx.author.display_avatar.url,
                    )
                    return await ctx.reply(embed=embed, view=view)

    @commands.command()
    async def tex(self, ctx: commands.Context, *, code: str):
        """TeX を画像化（数式モード内）"""
        await self.response(ctx, code, 'png', False, False)

    @commands.command()
    async def texp(self, ctx: commands.Context, *, code: str):
        """TeX を画像化（数式モード外）"""
        await self.response(ctx, code, 'png', True, False)

    @commands.command()
    async def stex(self, ctx: commands.Context, *, code: str):
        """TeX をスポイラー画像化（数式モード内）"""
        await self.response(ctx, code, 'png', False, True)

    @commands.command()
    async def stexp(self, ctx: commands.Context, *, code: str):
        """TeX をスポイラー画像化（数式モード外）"""
        await self.response(ctx, code, 'png', True, True)

    @commands.command()
    async def texpdf(self, ctx: commands.Context, *, code: str):
        """TeX を PDF 化（プリアンブルから）"""
        await self.response(ctx, code, 'pdf', None, False)


def setup(bot):
    return bot.add_cog(TeX(bot))
