import discord
from discord.ext import commands

import asyncio
import datetime
import traceback
import cogs.database as db
from cogs.music import Music
from cogs.music_player import MusicPlayer

class Playlist(commands.Cog):

    __slots__ = ('bot', 'users')

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='save_playlist', help='Saves your current queue with the specified name')
    async def save_playlist_(self, ctx, *, name: str):

        playlist_name = db.Database.get_playlist_name(self, ctx, name)

        if playlist_name != None:
            return await ctx.send('You already have a playlist with the name {}'.format(name))

        try:
            db.Database.save_playlist(self, ctx, name)
            await ctx.send('Your playlist has been saved as {}'.format(name))
        except Exception as e:
            traceback.print_exc()
            return await ctx.send('There was an error when saving your playlist')

    @commands.command(name='view_playlists', help='View all of your saved playlists')
    async def view_playlists_(self, ctx):

        playlists = db.Database.get_playlists(self, ctx)

        playlists_names = []

        for playlist in playlists:
            if playlist.name not in playlists_names:
                playlists_names.append(playlist.name)

        fmt = '\n'.join(([f'{index+1} - {playlist}' for index, playlist in enumerate(playlists_names)]))

        embed = discord.Embed(title="{}'s playlists".format(ctx.message.author.name), description=fmt)

        await ctx.send(embed=embed)

    @commands.command(name='delete_playlist', help='Deletes the playlist with the specified name')
    async def delete_playlist_(self, ctx, *, name: str):

        playlist_name = db.Database.get_playlist_name(self, ctx, name)

        if playlist_name != None:
            db.Database.delete_playlist(self, ctx, name)

            await ctx.message.add_reaction('❌')
            return await ctx.send('Your playlist {} has been removed'.format(name))
        else:
            return await ctx.send('You do not have any playlist with that name')

def setup(bot):
    bot.add_cog(Playlist(bot))
