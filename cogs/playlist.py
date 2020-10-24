import discord
from discord.ext import commands

import asyncio
import datetime
import traceback
import datetime
import cogs.database as db

class Playlist(commands.Cog):

    __slots__ = ('bot')

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='save_playlist', help='Saves your current queue with the specified name', aliases=['sp'])
    async def save_playlist_(self, ctx, *, name: str):

        playlist_count = db.Database.get_playlists(self, ctx)

        playlists_names = []

        for playlist in playlist_count:
            if playlist.name not in playlists_names:
                playlists_names.append(playlist.name)

        if len(playlists_names) == 10:
            return await ctx.send('You have reached the limit of 10 playlists per user, please remove another playlist to add another')

        playlist_name = db.Database.get_playlist_name(self, ctx, name)

        try:
            if name.lower() == playlist_name[0].name.lower():
                return await ctx.send('You already have a playlist with the name {}'.format(name))
        except IndexError:
            pass

        try:
            db.Database.save_playlist(self, ctx, name)
            await ctx.send('Your playlist has been saved as {}'.format(name))
        except Exception as e:
            traceback.print_exc()
            return await ctx.send('There was an error when saving your playlist')

    @commands.command(name='view_playlists', help='View all of your saved playlists', aliases=['vp'])
    async def view_playlists_(self, ctx):

        while True:
            playlists = db.Database.get_playlists(self, ctx)

            emojis = {0: '1️⃣', 1: '2️⃣', 2: '3️⃣', 3: '4️⃣', 4: '5️⃣', 5: '6️⃣', 6: '7️⃣', 7: '8️⃣', 8: '9️⃣', 9: '🔟'}
            playlists_names = []

            for playlist in playlists:
                if playlist.name not in playlists_names:
                    playlists_names.append(playlist.name)

            embed = discord.Embed(title="{}'s playlists".format(ctx.message.author.name), color=9442302)

            for index, playlist in enumerate(playlists_names):
                total_t = 0
                total_d = 0

                for track in db.Database.get_playlist_name(self, ctx, playlists_names[index]):
                    total_t = total_t + 1
                    total_d = total_d + track.duration

                time = datetime.timedelta(seconds=total_d)

                embed.add_field(name=f'{emojis.get(index)} - {playlist}', value=f'{total_t} audios with a duration of {time}')

            embed.set_footer(text='React with a number emoji of the playlist you want to see more information')

            message = await ctx.send(embed=embed)

            def check(reaction, user):
                return str(reaction.emoji) in emojis.values() and user == ctx.message.author

            def check_raw(payload):
                return str(payload.emoji) in emojis.values() and payload.user_id == ctx.message.author.id

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                new_pair = dict([(v,k) for k,v in emojis.items()])
                i_name = new_pair.get(str(reaction.emoji))

                try:
                    fmt = '\n'.join([f'{track.index} - {track.title}' for track in db.Database.get_playlist_name(self, ctx, playlists_names[i_name])])
                    embed = discord.Embed(title=f'{playlists_names[i_name]}', description=fmt, color=9442302)
                    embed.set_author(name=ctx.message.author.name)
                    embed.set_footer(text='Remove your reaction to go back to your playlists')

                    await message.edit(embed=embed)

                    payload = await self.bot.wait_for('raw_reaction_remove', check=check_raw)

                    await message.delete()

                    continue
                except IndexError:
                    await ctx.send('That playlist does not exist, choose another one', delete_after=10)
                    await message.delete()

                    continue

            except asyncio.TimeoutError:
                await ctx.send('Too slow to react, mate', delete_after=30)
                await message.delete()

                break

    @commands.command(name='delete_playlist', help='Deletes the playlist with the specified name', aliases=['dp'])
    async def delete_playlist_(self, ctx, *, name: str):

        playlist = db.Database.get_playlist_name(self, ctx, name)
        
        try:
            db.Database.delete_playlist(self, ctx, playlist[0].name)
            await ctx.message.add_reaction('❌')
        except IndexError:
            return await ctx.send('There is no playlist with the name: {}'.format(name))

def setup(bot):
    bot.add_cog(Playlist(bot))
