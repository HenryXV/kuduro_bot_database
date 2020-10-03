import discord
from discord.ext import commands

import asyncio
import json
import psycopg2
import random
import sqlalchemy as sa
from sqlalchemy import Table, Text, Column, Integer, String, create_engine, Sequence, ForeignKey, and_, or_
from sqlalchemy.dialects.postgresql import BIGINT, TEXT, INTEGER
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import HasPrefixes
from sqlalchemy.orm import sessionmaker, relationship, backref


engine = create_engine('postgresql+psycopg2://oytajjjmytxeqe:98e043a3ecd0e51737612d53f576aa6aa16080f253177a4d9ebb7c525a7cfb90@ec2-54-197-254-117.compute-1.amazonaws.com:5432/d5klk5lob226qh', echo=True)

Base = declarative_base()

class Guild(Base):
    __tablename__ = 'guilds'

    id = Column(BIGINT, primary_key=True, unique=True)
    name = Column(TEXT)

class Track(Base):
    __tablename__ = 'tracks'

    id = Column(INTEGER, Sequence('track_id_seq'), primary_key=True, unique=True)
    index = Column(INTEGER)
    web_url = Column(TEXT)
    title = Column(TEXT)
    duration = Column(TEXT)
    guild_id = Column(BIGINT, ForeignKey('guilds.id'))

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

    def search(self, delete):
        return session.query(Track).filter(or_(Track.index == delete, Track.title.ilike('{}%'.format(delete)))).filter(Track.guild_id == self._guild.id).first()

    def update_index(self, i):
        session.query(Track).filter(and_(Track.index > i, Track.guild_id == self._guild.id)).update({Track.index: Track.index - 1}, synchronize_session=False)
        session.commit()

    def clean_database(self):
        session.query(Track).filter(Track.guild_id == self._guild.id).delete(synchronize_session=False)

        session.commit()

    def shuffle(self, ctx):
        indexes = [track.index for track in session.query(Track).filter(Track.guild_id == self._guild.id)]
        new_values = random.sample(indexes, k=len(indexes))
        for track in session.query(Track).filter(Track.guild_id == self._guild.id):
            track.index = new_values.pop()

        session.commit()

        self.sync_pq(ctx)

    def sync_pq(self, ctx):

        player = self._cog.get_player(ctx)

        for track in session.query(Track).filter(Track.guild_id == self._guild.id):
            [player.pq.updateitem(k, int(track.index)) for k,v in player.pq.items() if k.title == track.title]

        print([(k.title,v) for k,v in player.pq.items()])
