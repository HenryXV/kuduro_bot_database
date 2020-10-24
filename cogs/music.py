import discord
from discord.ext import commands

import asyncio
import sys
import traceback
import datetime
import urllib.request
import re
import youtube_dl
import cogs.database as db
from sqlalchemy.dialects.postgresql import insert
from cogs.music_player import MusicPlayer
from cogs.spotify import Spotify
from cogs.ytdlsource import YTDLSource

class Music(commands.Cog):

    __slots__ = ('bot', 'players', 'databases')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.databases = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
            del self.databases[guild.id]
        except KeyError:
            pass

    async def __local_check(self, ctx):
        # A local check which applies to all commands in this cog.
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx, error):
        # A local error handler for all errors arising from commands in this cog.
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    def get_player(self, ctx):
    # Retrieve the guild player, or generate one.
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player
        return player

    def get_database(self, ctx):
        try:
            database = self.databases[ctx.guild.id]
        except KeyError:
            database = db.Database(ctx)
            self.databases[ctx.guild.id] = database
            db.session.execute(insert(db.Guild).values(id=database._guild.id, name=database._guild.name).on_conflict_do_nothing())
            database.clean_database(ctx)

        return database

    async def is_empty(self, ctx):

        player = self.get_player(ctx)

        while True:

            await asyncio.sleep(3)

            if len(player.pq) == 0 and player.loop_queue == True:
                await self.loop_queue_(ctx)
            elif player.loop_queue == False: break
            else: continue

    @commands.command(name='join', help='Connects the bot to your current channel')
    async def join(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()

    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=True)
    @commands.command(name='play', help='Connects to your channel and play an audio from youtube [search or url]', aliases=['p'])
    async def play_(self, ctx, *, search: str):

        await Music.join(self, ctx)
        
        async with ctx.typing():

            player = self.get_player(ctx)
            player.wait = True

            database = self.get_database(ctx)
            
            # Uses urrllib.request to search videos from the query term provided
            # then creates an url for the video       
            search = '+'.join(search.split())
            
            html = urllib.request.urlopen(f"https://www.youtube.com/results?search_query={search}")
            video_ids = re.findall(r"watch\?v=(\S{11})", html.read().decode())
            try:
                url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            except IndexError:
                if len(player.pq) == 0:
                    await Music.stop_(self, ctx)
                
                embed = discord.Embed(title='An error occurred while searching you video',
                                      description=f'It was not possible to find a video with the name: {search}',
                                      color=9442302)
                
                return await ctx.send(embed=embed)
            # If download is True, source will be a discord.FFmpegPCMAudio with a VolumeTransformer.
            try:
                source = await YTDLSource.create_source(ctx, url, loop=self.bot.loop, download=True)
            except youtube_dl.utils.DownloadError as e:
                if len(player.pq) == 0:
                    await Music.stop_(self, ctx)
                
                e = str(e).split(';')
                
                embed = discord.Embed(title=f"An error occurred while downloading: {url}",
                                      description=str(e[0]),
                                      color=9442302)

                return await ctx.send(embed=embed)

            track = db.Database.search(self, ctx, source.title)
            if track != None:
                return await ctx.send('The audio {} is already on the queue'.format(source.title))

            player.value = player.value + 1
            player.pq.additem(source, player.value)

            stmt = insert(db.Track).values(index=player.value, web_url=source.web_url, title=source.title, duration=source.duration, guild_id=database._guild.id).on_conflict_do_nothing()

            db.session.execute(stmt)

            db.session.commit()

        await ctx.message.add_reaction('✅')
        await ctx.send(f'```ini\n[Added {source.title} to the Queue]\n```', delete_after=30)

        player.wait = False

    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=True)
    @commands.command(name='next', help='Skips to the next song on the queue', aliases=['n'])
    async def skip_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        # if voice.is_playing() and len(player.pq) > 0:
        voice.stop()
        await ctx.message.add_reaction('⏭️')
        # else:
        #     await ctx.send('There is no audio on the queue', delete_after=10)

    @commands.command(name='pause', help='Pauses the audio currently being played')
    async def pause(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice.is_playing():
            voice.pause()
            await ctx.message.add_reaction('⏸️')
        elif voice.is_paused():
            await ctx.send('The audio is already paused', delete_after=10)
        else:
            await ctx.send('There is no audio playing right now', delete_after=10)

    @commands.command(name='resume', help='Resumes the audio currently playing')
    async def resume(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice.is_paused():
            voice.resume()
            await ctx.message.add_reaction('✅')
        elif voice.is_playing():
            await ctx.send('The audio is already playing', delete_after=10)
        else:
            await ctx.send('There is no audio being played right now', delete_after=10)

    @commands.command(name='queue', help='Show the audios currently queued', aliases=['q', 'playlist'])
    async def queue_info_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        queue = list(db.session.query(db.Track.index, db.Track.title).filter(db.Track.guild_id==database._guild.id).order_by(db.Track.index))

        if len(queue) == 0:
            return await ctx.send('There is no audio on the queue. Use the command !play or !p to queue audios', delete_after=20)

        fmt = '\n'.join([f'{track[0]} - {track[1]}' for track in queue])

        embed = discord.Embed(title='Your queue', description=fmt, color=9442302)

        await ctx.send(embed=embed)

    @commands.command(name='playing_now', help='Shows the current audio playing', aliases=['pn', 'now', 'currentaudio', 'playing'])
    async def now_playing_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice_channel = ctx.voice_client

        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('I am not playing anything right now. Use the command !play or !p to add audios to the queue')

        try:
            # Remove our previous now_playing message.
            await player.np.delete()
        except discord.HTTPException:
            pass

        player.np = await ctx.send('Playing: {a} - Requested by: <@{b}>'.format(a=voice_channel.source.title, b=voice_channel.source.requester.author.id))

    @commands.command(name='volume', help='Changes the volume between 1 and 100', aliases=['vol'])
    async def change_volume_(self, ctx, *, vol: float):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice_channel = ctx.voice_client

        if not 0 < vol < 101:
            return await ctx.send('Please, use number only between 1 and 100')

        player = self.get_player(ctx)

        if voice_channel.source:
            voice_channel.source.volume = vol / 100

        player.volume = vol / 100

        await ctx.send(f'The volume is now on **{vol}%**')

    @commands.command(name='stop', help='ATTENTION!!! This command will destroy your playlist and all changes made')
    async def stop_(self, ctx):

        player = self.get_player(ctx)
        player.loop_queue = False

        await self.cleanup(ctx.guild)

        await ctx.message.add_reaction('⏹️')

    @commands.command(name='remove', help='[track position] Deletes the audio specified by the user', aliases=['re'])
    async def remove_(self, ctx, *, delete):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        try:
            to_delete = database.search(ctx, delete)
            title = to_delete.title
            index = to_delete.index

            try:
                title_to_del = [k for k,v in player.pq.items() if k.title == title]
                del player.pq[title_to_del[0]]
            except IndexError:
                pass

            db.session.delete(to_delete)

            db.session.commit()

            database.update_index(index)

            await ctx.send('The audio {} was removed from the queue'.format(title), delete_after=60)
        except AttributeError as e:
            print(e)
            return await ctx.send('The audio is not on the queue', delete_after=10)

        await ctx.message.add_reaction('❌')

        if player.value > 0:
            player.value = player.value - 1

    @commands.command(name='remove_range', help='Removes tracks position from start to end (inclusive) [start] [end]  Ex: 1 6')
    async def remove_range(self, ctx, start: int, end: int):

        to_del = list(range(start, end+1))
        print(to_del)

        for _ in to_del:
            await self.remove_(ctx, delete=start)

    @commands.command(name='clear', help='Deletes all audios from the queue')
    async def clear_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        player.pq.clear()
        database.clean_database(ctx)

        player.value = 0

        await ctx.send('All audios have been removed', delete_after=5)

    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=True)
    @commands.command(name='jump', help='[track position] Skips to the specified audio', aliases=['j'])
    async def jump_(self, ctx, *, jump):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        try:
            to_jump = database.search(ctx, jump)
            title = to_jump.title
            index = to_jump.index

            print(title, index)

            audio = [k for k,v in player.pq.items() if k.title == title]

            if len(audio) == 0:
                if player.loop_queue == True:
                    player.loop_queue = False
                player.pq.clear()
                mes = await ctx.send('Going back in time...')
                for track in db.session.query(db.Track).filter(db.Track.index >= index, db.Track.guild_id == database._guild.id):
                    source = await YTDLSource.create_source(ctx, track.web_url, loop=self.bot.loop, download=True)
                    if source.title == title:
                        player.pq.additem(source, track.index)
                        await Music.skip_(self, ctx)
                        await mes.delete()
                    else:
                        player.pq.additem(source, track.index)
                player.loop_queue = True
            else:
                database.sync_pq(ctx)
                keys = [k for k,v in player.pq.items() if v < index]
                for key in keys:
                    del player.pq[key]

                await Music.skip_(self, ctx)

        except AttributeError:
            return await ctx.send('The audio specified is not on the queue')

    @commands.command(name='shuffle', help='Randomizes all audios in the queue')
    async def shuffle_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice_channel = ctx.voice_client

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        database.shuffle(ctx)

        await ctx.message.add_reaction('🔀')

    @commands.after_invoke(is_empty)
    @commands.command(name='loop_queue', help='Loops through the queue', aliases=['lp'])
    async def loop_queue_true(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)

        if player.loop_queue == False:
            player.loop_queue = True
            return await ctx.send('The queue will loop when it ends')
        else:
            return await ctx.send('The queue is already looping')

    @commands.command(name='loop_queue_stop', help='Stops the loop queue', aliases=['lqs'])
    async def stop_loop_queue_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)

        if player.loop_queue == True:
            player.loop_queue = False
            return await ctx.send('The queue is not going to loop anymore')
        else:
            return await ctx.send('The queue is already not looping')

    async def loop_queue_(self, ctx):

        player = self.get_player(ctx)
        player.wait = True

        database = self.get_database(ctx)

        for track in db.session.query(db.Track).filter(db.Track.guild_id == database._guild.id):
            source = await YTDLSource.create_source(ctx, track.web_url, loop=self.bot.loop, download=True)
            player.pq.additem(source, track.index)

        player.wait = False

    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=True)
    @commands.command(name='load_playlist', help='Loads a playlist with the specified name', aliases=['loadp'])
    async def load_playlist_(self, ctx, *, name: str):

        playlist = db.Database.get_playlist_name(self, ctx, name)

        await ctx.trigger_typing()
        
        try:
            await db.Database.load_playlist(self, ctx, playlist[0].name)
            return await ctx.send('Any changes made to the queue will not affect your saved playlist', delete_after=30)
        except IndexError:
            return await ctx.send('There is no playlist with the name: {}'.format(name))
    
    @commands.command(name='spotify')
    async def search_spotify_tracks_(self, ctx, *, search: str):
        
        sp = Spotify()
        
        search_result = sp.search_tracks(search, limit = 5)
                
        embed = discord.Embed(title=f'Results for the term: {search}', color=9442302)
        
        embed.set_author(name='Spotify Track Search')
        
        for i, t in enumerate(search_result):
            
            time = str(datetime.timedelta(milliseconds = t['duration']))
            
            embed.add_field(name=f"{i+1} - {t['track_n']}",
                            value=f"Artist(s): {t['artists_n']} \n Duration: {time[2:7]} minutes",
                            inline=True)
        
        await ctx.send(embed = embed)
        
def setup(bot):
    bot.add_cog(Music(bot))
