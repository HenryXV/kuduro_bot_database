import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

import asyncio
import ksoftapi

class Lyrics(commands.Cog):

    __slots__ = ['bot', 'kclient']

    def __init__(self, bot):
        self.bot = bot

        load_dotenv()
        self.kclient = ksoftapi.Client(os.getenv('KSOFT_API'))

    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=True)
    @commands.command(name='lyrics', help='Search for the lyrics of the specified song')
    async def lyrics_(self, ctx, *, search: str):

        try:
            results = await self.kclient.music.lyrics(search, limit=1)
            first = results[0]
            embed = discord.Embed(title = first.name, description = first.lyrics, color = 9442302 )
            embed.set_author(name = first.artist)
            embed.add_field(name = 'Album title', value = first.album.split(',')[0])
            embed.add_field(name = 'Album year', value = first.album_year[0])

            await ctx.send(embed=embed)
        except ksoftapi.NoResults:
            await ctx.send('No lyrics found for {}'.format(search))

def setup(bot):
    bot.add_cog(Lyrics(bot))
