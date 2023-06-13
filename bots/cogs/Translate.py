import os
import uuid
from typing import List

import aiohttp
import dotenv
import discord
import requests
from discord.ext import commands, pages

from .. import DeleteButton

dotenv.load_dotenv(verbose=True)
BASE_URL = "https://api.cognitive.microsofttranslator.com"

# get langage code list
params = {"api-version": "3.0", "scope": "translation"}
headers = {
    "Ocp-Apim-Subscription-Key": os.environ.get("TRANSLATOR_TEXT_SUBSCRIPTION_KEY"),
    "Ocp-Apim-Subscription-Region": "japaneast",
    "Content-type": "application/json",
}
r = requests.get(f"{BASE_URL}/languages", params=params, headers=headers)
r.raise_for_status()
result = r.json()
language_codes = list(result["translation"].keys())


def auto_complete_language(ctx: discord.AutocompleteContext) -> List[str]:
    return list(
        filter(
            lambda language_code: language_code.startswith(ctx.value.lower()),
            language_codes,
        )
    )


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
                autocomplete=auto_complete_language,
            ),
            discord.Option(
                name="from",
                description="Language to translate from",
                description_localizaitons={
                    "ja_JP": "翻訳元の言語",
                },
                required=False,
                autocomplete=auto_complete_language,
            ),
        ],
    )
    async def translate(
        self, ctx: discord.ApplicationContext, text: str, to: str, from_: str = None
    ):
        print("translate")
        key = os.environ.get("TRANSLATOR_TEXT_SUBSCRIPTION_KEY")
        endpoint = BASE_URL + "/translate"
        params = {
            "api-version": "3.0",
            "to": to,
        }
        if from_:
            params["from"] = from_
        headers = {
            "Ocp-Apim-Subscription-Key": key,
            "Ocp-Apim-Subscription-Region": "japaneast",
            "Content-type": "application/json",
            "X-ClientTraceId": str(uuid.uuid4()),
        }
        body = [{"text": text}]
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint, params=params, headers=headers, json=body
            ) as r:
                if r.status != 200:
                    return await ctx.respond(f"Error: {r.status}")
                result = await r.json()
        embed = discord.Embed(
            title="Translation",
            color=0x008000,
        )
        embed.add_field(
            name=f'[{from_ if from_ else result[0]["detectedLanguage"]["language"]}]',
            value=f"{text}",
            inline=False,
        )
        embed.add_field(
            name=f"[{to}]",
            value=f'{result[0]["translations"][0]["text"]}',
            inline=False,
        )
        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url,
        )
        view = discord.ui.View(DeleteButton(ctx.author), timeout=None)
        await ctx.respond(embed=embed, view=view)


def setup(bot):
    return bot.add_cog(Translate(bot))
