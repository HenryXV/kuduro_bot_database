import discord

import asyncio
import ctypes
import ctypes.util
from discord import FFmpegPCMAudio
from pqdict import pqdict
from cogs.ytdlsource import YTDLSource


class MusicPlayer:

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'pq', 'next_song', 'loop_queue', 'wait', 'value', 'source', 'current', 'np', 'volume')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.pq = pqdict()
        self.next_song = asyncio.Event()
        self.loop_queue = False

        self.wait = False
        self.value = 0
        self.source = None
        self.np = None  # Now playing message
        self.volume = .5
        self.current = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next_song.clear()

            try:
                if len(self.pq) == 0 and self.wait is True:
                    source = FFmpegPCMAudio('intro.webm')
                    source.title = 'chill'
                elif len(self.pq) == 0:
                    await asyncio.sleep(5)
                    source = self.pq.pop()
                else:
                    source = self.pq.pop()
            except KeyError:
                await self._channel.send('There is no audio on the queue, so I will disconnect from the channel. Use the command !play or !p to queue more audios', delete_after=10)
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource) and not isinstance(source, FFmpegPCMAudio):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f'There was an error processing your song.\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source

            print(source.title, self._guild.name)

            opus = ctypes.util.find_library('opus')
            discord.opus.load_opus(opus)
            if not discord.opus.is_loaded():
                raise RuntimeError('Opus failed to load')

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next_song.set))
            if source.title == 'chill':
                self.np = await self._channel.send('Please, listen to this chill music until your audio is ready to play')
            else:
                self.np = await self._channel.send('Playing now: {a} - Requested by: <@{b}>'.format(a=source.title, b=source.requester.author.id))

            await self.next_song.wait()

            source.cleanup()
            self.current = None

            try:
                # We are no longer playing this song...
                await self.np.delete()
            except discord.HTTPException:
                pass

    async def check_members(self):

        channel = self.bot.voice_clients[0].channel
        print(channel.members, channel.name)

        if len(channel.members) == 1:
            await self._channel.send('There is no one connected to the voice channel {}, so I will disconnect.'.format(self._channel), delete_after=10)
            self.destroy(self._guild)
        else:
            pass

    def destroy(self, guild):
        return self.bot.loop.create_task(self._cog.cleanup(guild))
