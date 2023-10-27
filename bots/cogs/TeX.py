import io
import os
import pathlib
import sqlite3
import time
from typing import Optional, Tuple, Union

import aiohttp
import discord
import dotenv
import openai
from discord.ext import commands

from .. import SUPPORT_SERVER_LINK, DeleteButton, LimitedSizeDict

dotenv.load_dotenv(verbose=True)

BASE_DIR = pathlib.Path(__file__).parent.parent
dbname = BASE_DIR.parent / "db.sqlite3"
conn = sqlite3.connect(dbname, check_same_thread=False)
c = conn.cursor()
c.execute(
    "CREATE TABLE IF NOT EXISTS tex (message_id INTEGER, response_id INTEGER, author_id INTEGER, code TEXT, spoiler INTEGER, error_message TEXT)"
)
c.execute("CREATE TABLE IF NOT EXISTS tex_ai (author_id INTEGER, time INTEGER)")

openai.api_key = os.getenv("OPENAI_API_KEY")


def fix_latex_error(
    latex_formula,
    error_message,
):
    prompt = f"LaTeX formula: {latex_formula}\nError message: {error_message}\nPlease provide the corrected LaTeX formula in the following format: \\( \\text{{[Your LaTeX formula here]}} \\)"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
    )
    full_response = response["choices"][0]["message"]["content"].strip()
    start_idx = full_response.find("\\(")
    end_idx = full_response.find("\\)")
    if start_idx != -1 and end_idx != -1:
        fixed_formula = full_response[start_idx + 2 : end_idx]
        return fixed_formula
    else:
        return "No LaTeX formula found in the response."


async def respond_core(
    author: discord.User, code: str, spoiler: bool
) -> Tuple[str, discord.Embed, Optional[discord.File], Optional[str]]:
    url = f"http://tex.gaato.net/render/png"
    params = {"latex": code}
    headers = {"Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=params, headers=headers) as r:
            match r.status:
                case 200:
                    result = await r.read()
                    file = discord.File(
                        io.BytesIO(result), filename=f"tex.png", spoiler=spoiler
                    )
                    embed = discord.Embed(color=0x008000)
                    embed.set_author(
                        name=author.name, icon_url=author.display_avatar.url
                    )
                    if not spoiler:
                        embed.set_image(url="attachment://tex.png")
                    if "\\\\" in code and "\\begin" not in code and "\\end" not in code:
                        embed.add_field(
                            name="Hint",
                            value="You can use gather or align environment.",
                        )
                    return "", embed, file, None
                case 400:
                    error_message = await r.text()
                    embed = discord.Embed(
                        title="Rendering Error",
                        description=f"```\n{error_message}\n```",
                        color=0xFF0000,
                    )
                    embed.set_author(
                        name=author.name,
                        icon_url=author.display_avatar.url,
                    )
                    return "", embed, None, error_message
                case _:
                    embed = discord.Embed(
                        title="Error",
                        description=f"Unexpected status code: {r.status}",
                        color=0xFF0000,
                    )
                    embed.set_author(
                        name=author.name,
                        icon_url=author.display_avatar.url,
                    )
                    return "", embed, None, None


class EditButton(discord.ui.Button):
    def __init__(self, label="Edit", style=discord.ButtonStyle.primary, **kwargs):
        super().__init__(label=label, style=style, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        c = conn.cursor()
        c.execute("SELECT * FROM tex WHERE message_id = ?", (interaction.message.id,))
        result = c.fetchone()
        if result is None:
            embed = discord.Embed(
                title="Error", description="Not found.", color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await interaction.response.send_modal(
            TeXModal(spoiler=bool(result[3]), value=result[2])
        )


class AIButton(discord.ui.Button):
    def __init__(
        self, label="Auto fix with AI", style=discord.ButtonStyle.blurple, **kwargs
    ):
        super().__init__(label=label, style=style, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(invisible=False)
        c = conn.cursor()
        c.execute("SELECT * FROM tex_ai WHERE author_id = ?", (interaction.user.id,))
        result = c.fetchone()
        if result is not None:
            if result[1] + 60 * 60 > int(time.time()):
                embed = discord.Embed(
                    title="Error",
                    description="You can only use this button once per hour.",
                    color=0xFF0000,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
        c.execute("SELECT * FROM tex WHERE response_id = ?", (interaction.message.id,))
        result = c.fetchone()
        if result is None:
            embed = discord.Embed(
                title="Error", description="Not found.", color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        latex_formula = result[3]
        error_message = result[5]
        fixed_formula = fix_latex_error(latex_formula, error_message)
        content, embed, file, error = await respond_core(
            interaction.user,
            fixed_formula,
            bool(result[4]),
        )
        c.execute(
            "INSERT INTO tex_ai VALUES (?, ?)", (interaction.user.id, int(time.time()))
        )
        embed.set_footer(text="Powered by OpenAI")
        if error is None:
            embed.add_field(
                name="Code",
                value=f"```tex\n{fixed_formula}\n```",
            )
            view = discord.ui.View(DeleteButton(interaction.user), timeout=None)
            m = await interaction.followup.send(
                content=content,
                embed=embed,
                file=file,
                view=view,
                ephemeral=True,
            )
            c.execute(
                "INSERT INTO tex VALUES (?, ?, ?, ?, ?, ?)",
                (
                    interaction.message.id,
                    m.id,
                    interaction.user.id,
                    fixed_formula,
                    int(result[4]),
                    None,
                ),
            )
            conn.commit()
        else:
            embed = discord.Embed(
                title="Error", description="Failed to fix.", color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class TeXModal(discord.ui.Modal):
    def __init__(
        self, spoiler, env=None, value="", title="LaTeX to Image", *arg, **kwargs
    ):
        self.spoiler = spoiler
        if env:
            value = f"\\begin{{{env}}}\n{value}\n\\end{{{env}}}"
        super().__init__(title=title, *arg, **kwargs)
        self.add_item(
            discord.ui.InputText(
                label="Code",
                placeholder="Input TeX code here",
                style=discord.InputTextStyle.long,
                value=value,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(invisible=False)
        content, embed, file, error = await respond_core(
            interaction.user,
            self.children[0].value,
            self.spoiler,
        )
        embed.add_field(
            name="Code",
            value=f"```tex\n{self.children[0].value}\n```",
        )
        if error is None:
            view = discord.ui.View(
                DeleteButton(interaction.user), EditButton(), timeout=None
            )
        else:
            view = discord.ui.View(
                DeleteButton(interaction.user), EditButton(), AIButton(), timeout=None
            )
        if file is None:
            m = await interaction.followup.send(
                content=content, embed=embed, view=view, wait=True
            )
        else:
            m = await interaction.followup.send(
                content=content, embed=embed, file=file, view=view, wait=True
            )
        c = conn.cursor()
        c.execute(
            "INSERT INTO tex VALUES (?, ?, ?, ?, ?, ?)",
            (
                m.id,
                m.id,
                interaction.user.id,
                self.children[0].value,
                int(self.spoiler),
                error,
            ),
        )


class TeX(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_message_id_to_bot_message = LimitedSizeDict(size_limit=100)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.content != after.content:
            if before.id in self.user_message_id_to_bot_message:
                await self.user_message_id_to_bot_message[before.id].delete()

    async def respond(
        self,
        ctx: Union[commands.Context, discord.ApplicationContext],
        code: str,
        spoiler: bool,
    ):
        async with ctx.typing():
            code = code.replace("```tex", "").replace("```", "").strip()
            content, embed, file, error = await respond_core(ctx.author, code, spoiler)
            if error is None:
                view = discord.ui.View(DeleteButton(ctx.author), timeout=None)
            else:
                view = discord.ui.View(
                    DeleteButton(ctx.author), AIButton(), timeout=None
                )
            c = conn.cursor()
            if file is None:
                if isinstance(ctx, discord.ApplicationContext):
                    m = await ctx.respond(content=content, embed=embed, view=view)
                else:
                    m = await ctx.reply(content=content, embed=embed, view=view)
            else:
                if isinstance(ctx, discord.ApplicationContext):
                    m = await ctx.respond(
                        content=content, embed=embed, file=file, view=view
                    )
                else:
                    m = await ctx.reply(
                        content=content, embed=embed, file=file, view=view
                    )
            if isinstance(ctx, discord.ApplicationContext):
                c.execute(
                    "INSERT INTO tex VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        m.id,
                        m.id,
                        ctx.author.id,
                        code,
                        int(spoiler),
                        error,
                    ),
                )
            else:
                c.execute(
                    "INSERT INTO tex VALUES (?, ?, ?, ?, ?, ?)",
                    (ctx.message.id, m.id, ctx.author.id, code, int(spoiler), error),
                )
            return m

    @commands.command()
    async def tex(self, ctx: commands.Context, *, code: str):
        """LaTeX to image (in math mode)"""
        m = await self.respond(ctx, code, False)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @commands.command()
    async def stex(self, ctx: commands.Context, *, code: str):
        """LaTeX to spoiler image (in math mode)"""
        m = await self.respond(ctx, code, True)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @commands.command()
    async def aitex(self, ctx: commands.Context, *, code: str):
        """LaTeX to image (in math mode)"""
        with ctx.typing():
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "Convert to LaTeX formulae.\n"
                        "Response only LaTeX formulae without any other text.\n"
                        "Don't include $ or \\[ or \\] in the response.",
                    },
                    {"role": "user", "content": code},
                ],
                max_tokens=50,
            )
        m = await self.respond(
            ctx, response["choices"][0]["message"]["content"].strip(), False
        )
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @discord.slash_command(
        name="tex",
        description="TeX to image",
        options=[
            discord.Option(
                type=str,
                name="code",
                description="LaTeX code",
                required=False,
            ),
            discord.Option(
                type=str,
                name="env",
                description="The environment to use",
                required=False,
                choices=[
                    discord.OptionChoice(name="align", value="align"),
                    discord.OptionChoice(name="gather", value="gather"),
                ],
            ),
            discord.Option(
                type=bool,
                name="spoiler",
                description="Whether to mark the image as a spoiler",
                required=False,
                default=False,
            ),
        ],
    )
    async def tex_slash(
        self,
        ctx: discord.ApplicationContext,
        code: Optional[str] = None,
        env: Optional[str] = None,
        spoiler: bool = False,
    ):
        if code is None:
            modal = TeXModal(spoiler, env)
            await ctx.send_modal(modal)
        else:
            await self.respond(ctx, code, spoiler)

    @discord.slash_command(
        name="aitex",
        description="text to LaTeX image with AI",
        options=[
            discord.Option(
                type=str,
                name="text",
                description="Text to convert to LaTeX formulae",
                required=True,
            ),
            discord.Option(
                type=bool,
                name="spoiler",
                description="Whether to mark the image as a spoiler",
                required=False,
                default=False,
            ),
        ],
    )
    async def aitex_slash(
        self,
        ctx: discord.ApplicationContext,
        text: str,
        spoiler: bool = False,
    ):
        await ctx.defer()
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "Convert to LaTeX formulae.\n"
                    "Response only LaTeX formulae without any other text.\n"
                    "Don't include $ or \\[ or \\] in the response.",
                },
                {"role": "user", "content": text},
            ],
            max_tokens=50,
        )
        await self.respond(
            ctx, response["choices"][0]["message"]["content"].strip(), spoiler
        )


def setup(bot):
    return bot.add_cog(TeX(bot))
