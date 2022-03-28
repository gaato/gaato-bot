import asyncio
import copy
import os
import random
import re
from typing import Dict

import discord
import yt_dlp
from discord.ext import commands, pages
from dotenv import load_dotenv
from googleapiclient.discovery import build

from gaato_bot.core.bot import GaatoBot


load_dotenv(verbose=True)
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

# Suppress noise about console usage from errors
yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '/tmp/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn '
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

client = discord.Client()


def get_video_from_url(url):
    meta = ytdl.extract_info(url, download=False)
    return meta

def get_videos_search(keyword):
    youtube = build('youtube', 'v3', developerKey=GOOGLE_API_KEY)
    youtube_query = youtube.search().list(q=keyword, part='id,snippet', maxResults=1)
    youtube_res = youtube_query.execute()
    return youtube_res.get('items', [])

def get_videos_from_playlist(playlist_id):
    youtube = build('youtube', 'v3', developerKey=GOOGLE_API_KEY)
    youtube_query = youtube.playlistItems().list(playlistId=playlist_id, part='snippet,contentDetails', maxResults=50)
    result = []
    while youtube_query:
        youtube_res = youtube_query.execute()
        result += youtube_res.get('items', [])
        youtube_query = youtube.playlistItems().list_next(
            youtube_query,
            youtube_res,
        )
    return result


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.02):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class AudioQueue(asyncio.Queue):
    def __init__(self):
        super().__init__()

    def __getitem__(self, idx):
        return self._queue[idx]

    def to_list(self):
        return list(self._queue)

    def reset(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, idx):
        del self._queue[idx]


class AudioStatus:
    def __init__(self, ctx: commands.Context, vc: discord.VoiceClient):
        self.vc: discord.VoiceClient = vc
        self.ctx: commands.Context = ctx
        self.queue = AudioQueue()
        self.done = asyncio.Event()
        self.playing = None
        self.loop = False
        self.qloop = False
        self.skipping = False
        asyncio.create_task(self.playing_task())

    async def add_audio(self, video):
        await self.queue.put(video)

    def get_list(self):
        return self.queue.to_list()

    async def playing_task(self):
        while True:
            try:
                video = await asyncio.wait_for(self.queue.get(), timeout=180)
            except asyncio.TimeoutError:
                asyncio.create_task(self.leave())
                break
            while self.vc and video['user'].voice and video['user'].voice.channel.id == self.vc.channel.id:
                self.done.clear()
                self.playing = copy.copy(video)
                self.playing['title'] += '（ダウンロード中）'
                try:
                    player = await YTDLSource.from_url(video['url'], loop=client.loop)
                except Exception as e:
                    print(e)
                    await self.ctx.send(f'{video["title"]} を再生できませんでした')
                    self.playing = None
                else:
                    try:
                        self.vc.play(player, after=self.play_next)
                        self.playing = video
                        await self.done.wait()
                    except Exception as e:
                        print(e)
                        await self.ctx.send(f'{video["title"]} を再生できませんでした')
                    self.playing = None
                if self.loop:
                    player = await YTDLSource.from_url(video['url'], loop=client.loop)
                elif self.qloop:
                    await self.add_audio(video)
                    break
                else:
                    break

    def play_next(self, err=None):
        self.done.set()

    async def leave(self):
        self.queue.reset()
        if self.vc:
            await self.vc.disconnect()
            self.vc = None

    @property
    def is_playing(self):
        return self.vc.is_playing()

    def skip(self):
        self.skipping = True
        self.vc.stop()


class Voice(commands.Cog):
    def __init__(self, bot: GaatoBot):
        self.bot = bot
        self.audio_statuses: Dict[int, AudioStatus] = {}

    @commands.command()
    async def join(self, ctx: commands.Context):
        """VC に参加"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send('先にボイスチャンネルに参加してください')
        vc = await ctx.author.voice.channel.connect()
        self.audio_statuses[ctx.guild.id] = AudioStatus(ctx, vc)

    @commands.command(aliases=['p'])
    async def play(self, ctx: commands.Context, *, url_or_keyword: str):
        """音楽を再生"""
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None or status.vc is None or not status.vc.is_connected:
            await ctx.invoke(self.join)
            status = self.audio_statuses[ctx.guild.id]
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Bot と同じボイスチャンネルに入ってください')
        if m := re.match(r'https?://((www|m)\.)?youtube\.com/playlist\?list=', url_or_keyword):
            playlist_id = url_or_keyword.replace(m.group(), '')
            result = get_videos_from_playlist(playlist_id)
            videos = []
            for r in result:
                try:
                    videos.append({
                        'title': r['snippet']['title'],
                        'url': 'https://www.youtube.com/watch?v=' + r['contentDetails']['videoId'],
                        'thumbnail': r['snippet']['thumbnails']['default']['url'],
                        'user': ctx.author,
                    })
                except KeyError:
                    pass
        elif re.match(r'https?://.+', url_or_keyword):
            try:
                result = get_video_from_url(url_or_keyword)
            except yt_dlp.utils.DownloadError:
                return await ctx.send('サポートしていない URL です')
            videos = [{
                'title': result.get('title'),
                'url': url_or_keyword,
                'thumbnail': result.get('thumbnail'),
                'user': ctx.author,
            }]
        else:
            result = get_videos_search(url_or_keyword)
            videos = [{
                'title': result[0]['snippet']['title'],
                'url': 'https://www.youtube.com/watch?v=' + result[0]['id']['videoId'],
                'thumbnail': result[0]['snippet']['thumbnails']['default']['url'],
                'user': ctx.author,
            }]
        for video in videos:
            await status.add_audio(video)
        if len(videos) == 1:
            embed = discord.Embed(
                title=f'{discord.utils.escape_markdown(videos[0]["title"])} をキューに追加しました',
                url=videos[0]["url"],
            )
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
            if videos[0]['thumbnail']:
                embed.set_thumbnail(url=videos[0]['thumbnail'])
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f'{len(videos)} 曲をキューに追加しました',
            )
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)

    @commands.command(aliases=['s'])
    async def skip(self, ctx: commands.Context):
        """流れている音楽をスキップ"""
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None or status.vc is None:
            return await ctx.send('Bot はまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Bot と同じボイスチャンネルに入ってください')
        if not status.is_playing:
            return await ctx.send('既に停止しています')
        title = status.playing['title']
        status.skip()
        embed = discord.Embed(
            title=f'{discord.utils.escape_markdown(title)} をスキップしました',
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['dc'])
    async def disconnect(self, ctx: commands.Context):
        """VC から切断"""
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None or status.vc is None:
            return await ctx.send('Bot はまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Bot と同じボイスチャンネルに入ってください')
        await status.leave()
        del self.audio_statuses[ctx.guild.id]
        embed = discord.Embed(
            title='切断しました',
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['q'])
    async def queue(self, ctx: commands.Context):
        """キューを表示"""
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None or status.vc is None:
            return await ctx.send('先にボイスチャンネルに参加してください')
        queue = status.get_list()
        if len(queue) == 0:
            if status.playing:
                embed = discord.Embed(
                    description=f'再生中: [{discord.utils.escape_markdown(status.playing["title"])}]({status.playing["url"]}) Requested by {status.playing["user"].mention}\n',
                )
                embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
                embed.set_footer(
                    text=f'{len(queue)} 曲, Loop: {"✅" if status.loop else "❌"}, Queue Loop: {"✅" if status.qloop else "❌"}',
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title='何も再生されていません',
                )
                embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
                await ctx.send(embed=embed)
        else:
            page_list = []
            for i in range((len(queue) - 1) // 10 + 1):
                songs = ''
                if status.playing:
                    songs += f'再生中: [{discord.utils.escape_markdown(status.playing["title"])}]({status.playing["url"]}) Requested by {status.playing["user"].mention}\n'
                for j in range(i * 10, (i + 1) * 10):
                    if j >= len(queue):
                        break
                    video = queue[j]
                    songs += f'{j + 1}. [{discord.utils.escape_markdown(video["title"])}]({video["url"]}) Requested by {video["user"].mention}\n'
                embed = discord.Embed(
                    description=songs,
                )
                embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
                embed.set_footer(
                    text=f'{len(queue)} 曲, Loop: {"✅" if status.loop else "❌"}, Queue Loop: {"✅" if status.qloop else "❌"}',
                )
                page_list.append(embed)
            paginator = pages.Paginator(pages=page_list)
            await paginator.send(ctx)

    @commands.command()
    async def shuffle(self, ctx: commands.Context):
        """キューをシャッフル"""
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None or status.vc is None:
            return await ctx.send('Bot はまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Bot と同じボイスチャンネルに入ってください')
        status.queue.shuffle()
        return await ctx.send('シャッフルしました')

    @commands.command(aliases=['rm'])
    async def remove(self, ctx: commands.Context, *, idx: int):
        """指定した番号の音楽をキューから削除"""
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None or status.vc is None:
            return await ctx.send('Bot はまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Bot と同じボイスチャンネルに入ってください')
        title = status.queue[idx - 1]['title']
        status.queue.remove(idx - 1)
        embed = discord.Embed(
            title=f'{discord.utils.escape_markdown(title)} を削除しました',
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command()
    async def loop(self, ctx: commands.Context):
        """１曲リピート"""
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None or status.vc is None:
            return await ctx.send('Bot はまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Bot と同じボイスチャンネルに入ってください')
        if status.loop:
            status.loop = False
            return await ctx.send('Loop を無効にしました')
        else:
            status.loop = True
            return await ctx.send('Loop を有効にしました')

    @commands.command(aliases=['loopqueue', 'lq', 'queueloop'])
    async def qloop(self, ctx: commands.Context):
        """キューループ"""
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None or status.vc is None:
            return await ctx.send('Bot はまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Bot と同じボイスチャンネルに入ってください')
        if status.qloop:
            status.qloop = False
            return await ctx.send('Queue Loop を無効にしました')
        else:
            status.qloop = True
            return await ctx.send('Queue Loop を有効にしました')

    @commands.command(aliases=['np'])
    async def nowplaying(self, ctx: commands.Context):
        """今流れている音楽を表示"""
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None or status.vc is None:
            return await ctx.send('Bot はまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Bot と同じボイスチャンネルに入ってください')
        if status.playing:
            embed = discord.Embed(
                title=discord.utils.escape_markdown(status.playing["title"]),
                url=status.playing["url"],
                description=f'Requested by {status.playing["user"].mention}',
            )
            if status.playing["thumbnail"]:
                embed.set_thumbnail(url=status.playing["thumbnail"])
        else:
            embed = discord.Embed(
                title='何も再生されていません',
            )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['cl'])
    async def clear(self, ctx: commands.Context):
        """キューを削除"""
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None or status.vc is None:
            return await ctx.send('Bot はまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Bot と同じボイスチャンネルに入ってください')
        status.queue.reset()
        embed = discord.Embed(
            title='キューを削除しました',
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


def setup(bot):
    return bot.add_cog(Voice(bot))
