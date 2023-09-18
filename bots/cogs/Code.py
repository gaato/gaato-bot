import io
import pathlib
import re
import sqlite3
from typing import List, Optional, Tuple

import aiohttp
import discord
import requests
from discord.ext import commands
from discord.interactions import Interaction

from .. import DeleteButton, LimitedSizeDict

URL = "https://wandbox.org/api/"
BASE_DIR = pathlib.Path(__file__).parent.parent


dbname = BASE_DIR.parent / "db.sqlite3"
conn = sqlite3.connect(dbname, check_same_thread=False)
c = conn.cursor()
c.execute(
    "CREATE TABLE IF NOT EXISTS code (message_id INTEGER, author_id INTEGER, language TEXT, code TEXT, stdin TEXT)"
)


def get_autocomplete_languages() -> List[str]:
    with requests.get(URL + "list.json") as r:
        r.raise_for_status()
        result = r.json()
        language_names = set(
            map(lambda data: data["language"].lower().replace(" ", ""), result)
        )
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
        async with session.get(URL + "list.json") as r:
            if r.status == 200:
                result = await r.json()
                language_names = set(map(lambda data: data["language"], result))
                languages_dict = {}
                for language_name in language_names:
                    language_information = next(
                        filter(
                            lambda language_information: language_information[
                                "language"
                            ]
                            == language_name,
                            result,
                        )
                    )
                    languages_dict[
                        language_name.lower().replace(" ", "")
                    ] = language_information["name"]
    return languages_dict


async def run_core(
    author: discord.User,
    language: str,
    code: str,
    stdin: str = "",
) -> Tuple[discord.Embed, Optional[discord.File]]:
    language_dict = await get_languages()
    if language not in language_dict.keys():
        embed = discord.Embed(
            title="The following languages are supported",
            description=", ".join(language_dict.keys()),
            color=0xFF0000,
        )
        embed.set_author(name=author.name, icon_url=author.display_avatar.url)
        return embed, None
    if language == "nim":
        compiler_option = (
            "--hint[Processing]:off\n"
            "--hint[Conf]:off\n"
            "--hint[Link]:off\n"
            "--hint[SuccessX]:off"
        )
    else:
        compiler_option = ""
    url = URL + "compile.json"
    params = {
        "compiler": language_dict[language],
        "code": code,
        "stdin": stdin,
        "compiler-option-raw": compiler_option,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=params) as r:
            if r.status == 200:
                result = await r.json()
            else:
                embed = discord.Embed(
                    title="Connection Error", description=f"{r.status}", color=0xFF0000
                )
                embed.set_author(name=author.name, icon_url=author.display_avatar.url)
                return embed, None
    embed = discord.Embed(title=f"Result ({language_dict[language]}):")
    embed_color = 0xFF0000
    files = []
    for k, v in result.items():
        if k in ("program_message", "compiler_message"):
            continue
        if v == "":
            continue
        if k == "status" and v == "0":
            embed_color = 0x007000
        if language == "nim" and k == "compiler_error":
            v = re.sub(r"CC: \S+\n", "", v)
            if v == "":
                continue
        if len(v) > 1000 or len(v.split("\n")) > 100:
            files.append(discord.File(io.StringIO(v), k + ".txt"))
        else:
            embed.add_field(
                name=k,
                value="```\n" + v + "\n```",
            )
    embed.color = embed_color
    embed.set_author(name=author.name, icon_url=author.display_avatar.url)
    return embed, files


class EditButton(discord.ui.Button):
    def __init__(self, label="Edit", style=discord.ButtonStyle.primary, **kwargs):
        super().__init__(label=label, style=style, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        c = conn.cursor()
        c.execute("SELECT * FROM code WHERE message_id = ?", (interaction.message.id,))
        result = c.fetchone()
        if result is None:
            embed = discord.Embed(
                title="Error", description="Not found.", color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await interaction.response.send_modal(
            RunModal(result[2], code=result[3], stdin=result[4])
        )


class ViewCodeButton(discord.ui.Button):
    def __init__(
        self, label="View Code", style=discord.ButtonStyle.secondary, **kwargs
    ):
        super().__init__(label=label, style=style, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        c = conn.cursor()
        c.execute("SELECT * FROM code WHERE message_id = ?", (interaction.message.id,))
        result = c.fetchone()
        if result is None:
            embed = discord.Embed(
                title="Error", description="Not found.", color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            title=result[2],
            description=f"```{result[2]}\n{result[3]}```",
            color=0x007000,
        )
        if result[4] != "":
            embed.add_field(
                name="Standard Input",
                value=f"```\n{result[4]}\n```",
            )
        embed.set_author(
            name=interaction.guild.get_member(result[1]).name,
            icon_url=interaction.guild.get_member(result[1]).display_avatar.url,
        )
        embed.set_footer(
            text=f"Requested by {interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )
        view = discord.ui.View(DeleteButton(interaction.user), timeout=None)
        await interaction.response.send_message(embed=embed, view=view)


class RunModal(discord.ui.Modal):
    def __init__(
        self, language: str, title="Run code", code="", stdin="", *args, **kwargs
    ):
        super().__init__(title=title, *args, **kwargs)
        self.language = (
            language.lower()
            .replace("pp", "++")
            .replace("sharp", "#")
            .replace("clisp", "lisp")
        )
        self.add_item(
            discord.ui.InputText(
                label="Code",
                placeholder="Write code here",
                style=discord.InputTextStyle.long,
                value=code,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Standard Input",
                required=False,
                style=discord.InputTextStyle.long,
                value=stdin,
            )
        )

    async def callback(self, interaction: Interaction):
        await interaction.response.defer(invisible=False)
        embed, files = await run_core(
            interaction.user,
            self.language,
            self.children[0].value,
            self.children[1].value,
        )
        view = discord.ui.View(
            DeleteButton(interaction.user), EditButton(), ViewCodeButton(), timeout=None
        )
        m = await interaction.followup.send(
            embed=embed, files=files, view=view, wait=True
        )
        c.execute(
            "INSERT INTO code VALUES (?, ?, ?, ?, ?)",
            (
                m.id,
                interaction.user.id,
                self.language,
                self.children[0].value,
                self.children[1].value,
            ),
        )


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
        code = re.sub(r"(```[a-zA-Z0-9]*\n|```)($|\n)", "", code)
        view = discord.ui.View(DeleteButton(ctx.author), timeout=None)
        embed, files = await run_core(ctx.author, language, code)
        m = await ctx.reply(embed=embed, files=files, view=view)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @discord.message_command()
    async def escape(self, ctx: discord.ApplicationContext, message: discord.Message):
        await ctx.respond(
            discord.utils.escape_markdown(
                discord.utils.escape_mentions(message.content)
            ),
            ephemeral=True,
        )

    @discord.slash_command(
        name="run",
        description="Run code",
        options=[
            discord.Option(
                name="language",
                description="Language",
                required=True,
                autocomplete=auto_complete_language,
            )
        ],
    )
    async def run_slash(self, ctx: discord.ApplicationContext, language: str):
        await ctx.send_modal(RunModal(language, title="Run code"))


def setup(bot):
    return bot.add_cog(Code(bot))
