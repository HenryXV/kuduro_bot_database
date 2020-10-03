import discord
from discord.ext import commands

import asyncio
import json
import sqlite3
import random
import sqlalchemy as sa
from sqlalchemy import Table, Text, Column, Integer, String, create_engine, Sequence, ForeignKey, and_, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import HasPrefixes, insert
from sqlalchemy.orm import sessionmaker, relationship, backref


engine = create_engine('sqlite:///database\playlists.db', echo=False)

Base = declarative_base()

class Guild(Base):
    __tablename__ = 'guilds'

    id = Column(Integer, primary_key=True, unique=True)
    name = Column(String)

class Track(Base):
    __tablename__ = 'tracks'

    id = Column(Integer, Sequence('track_id_seq'), primary_key=True, unique=True)
    index = Column(Integer)
    web_url = Column(String)
    title = Column(String)
    duration = Column(Integer)
    guild_id = Column(Integer, ForeignKey('guilds.id'))

    guild = relationship('Guild', back_populates = 'tracks')

class Playlist(Base):
    __tablename__ = 'playlists'

    id = Column(Integer, Sequence('playlist_id_seq'), primary_key=True, unique=True)
    name = Column(String)
    track_id = Column(Integer, ForeignKey('tracks.id'))

Guild.tracks = relationship('Track', order_by = Track.id, back_populates = 'guild', cascade="all, delete, delete-orphan")

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

class Database(commands.Cog):

    __slots__ = ('bot', 'channel', 'cog')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._cog = ctx.cog

    def insert_pref(self, table):
        return insert(table).prefix_with('OR IGNORE')

    def search(self, delete):
        return session.query(Track).filter(or_(Track.index == delete, Track.title.ilike('{}%'.format(delete)))).filter(Track.guild_id == self._guild.id).first()

    def update_index(self, i):
        for track in session.query(Track).filter(and_(Track.index > i, Track.guild_id == self._guild.id)):
            track.index = track.index - 1

    def clean_database(self):
        for track in session.query(Track).filter(Track.guild_id == self._guild.id):
            session.delete(track)

        session.commit()

    def shuffle(self, ctx):
        indexes = [track.index for track in session.query(Track).filter(Track.guild_id == self._guild.id)]
        new_values = random.sample(indexes, k=len(indexes))
        print(new_values)
        for track in session.query(Track).filter(Track.guild_id == self._guild.id):
            track.index = new_values.pop()

        session.commit()

        self.sync_pq(ctx)

    def sync_pq(self, ctx):

        player = self._cog.get_player(ctx)

        for track in session.query(Track).filter(Track.guild_id == self._guild.id):
            [player.pq.updateitem(k, track.index) for k,v in player.pq.items() if k.title == track.title]

        print([(k.title,v) for k,v in player.pq.items()])
