import os

import discord
import dotenv
import openai
from discord.ext import commands

from .. import DeleteButton

dotenv.load_dotenv(verbose=True)
openai.api_key = os.getenv("OPENAI_API_KEY")


class Translate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.slash_command(
        name="translate",
        description="Translate text",
        description_localizaitons={
            "ja_JP": "テキストを翻訳します",
        },
        options=[
            discord.Option(
                name="text",
                description="Text to translate",
                description_localizaitons={
                    "ja_JP": "翻訳するテキスト",
                },
                required=True,
            ),
            discord.Option(
                name="to",
                description="Language to translate to",
                description_localizaitons={
                    "ja_JP": "翻訳先の言語",
                },
                required=True,
            ),
            discord.Option(
                name="from",
                description="Language to translate from",
                description_localizaitons={
                    "ja_JP": "翻訳元の言語",
                },
                required=False,
            ),
        ],
    )
    async def translate(
        self, ctx: discord.ApplicationContext, text: str, to: str, from_: str = None
    ):
        """Translate text"""
        await ctx.defer()
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": f"Respond translation of user's text to [{to}]"
                    if not from_
                    else f"translate user's text from [{from_}] to [{to}]"
                    + "\nLanguage name or lanuage code must be in []",
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
            max_tokens=2000,
        )
        embed = discord.Embed(
            title="Translate",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name=f"Original {from_ + ' text' if from_ else 'text'}",
            value=text,
            inline=False,
        )
        embed.add_field(
            name=f"Translated to {to}",
            value=response["choices"][0]["message"]["content"].strip(),
            inline=False,
        )
        view = discord.ui.View(DeleteButton(ctx.user))
        await ctx.followup.send(embed=embed, view=view)


def setup(bot):
    return bot.add_cog(Translate(bot))
