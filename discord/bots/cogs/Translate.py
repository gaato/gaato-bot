import os

import discord
import dotenv
import iso639
from discord.ext import commands
from iso639.exceptions import InvalidLanguageValue
from openai import AsyncOpenAI

from .. import DeleteButton

dotenv.load_dotenv(verbose=True)


client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

two_letter_codes: dict[str, list[str]] = {}
three_letter_codes: dict[str, list[str]] = {}
language_names: list[str] = []
for lang in iso639.iter_langs():
    if not lang.pt1:
        continue
    if lang.pt1:
        if lang.pt1 in two_letter_codes:
            two_letter_codes[lang.pt1].append(lang.name)
        else:
            two_letter_codes[lang.pt1] = [lang.name]
    language_names.append(f"{lang.name}")


def autocomplete_language(ctx: discord.AutocompleteContext) -> list[str]:
    input_value = ctx.value.lower()
    if len(input_value) <= 1:
        return []
    elif len(input_value) == 2:
        return two_letter_codes.get(input_value, [])
    elif len(input_value) == 3:
        return three_letter_codes.get(input_value, [])
    else:
        matching_languages = [
            name for name in language_names if name.lower().startswith(input_value)
        ]
        return sorted(matching_languages, key=len)[:30]


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
                autocomplete=autocomplete_language,
                required=True,
            ),
        ],
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install
        },
    )
    async def translate(self, ctx: discord.ApplicationContext, text: str, to: str):
        """Translate text"""
        await ctx.defer()
        try:
            lang = iso639.Lang(to)
        except InvalidLanguageValue:
            return await ctx.followup.send("Invalid language", ephemeral=True)
        if not lang.pt1:
            return await ctx.followup.send("Invalid language", ephemeral=True)
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "This is a direct translation task. "
                    f"Translate the following text to {lang.name}. "
                    "Do not add any additional comments or language indicators.",
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
            name=f"Original text",
            value=text,
            inline=False,
        )
        embed.add_field(
            name=f"Translated to {to}",
            value=response.choices[0].message.content,
            inline=False,
        )
        view = discord.ui.View(DeleteButton(ctx.user))
        await ctx.followup.send(embed=embed, view=view)


def setup(bot):
    return bot.add_cog(Translate(bot))
