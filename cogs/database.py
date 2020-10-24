import os
from dotenv import load_dotenv
import random
from cogs.ytdlsource import YTDLSource
from sqlalchemy import Column, Integer, String, create_engine, Sequence, ForeignKey, and_
from sqlalchemy.dialects.postgresql import BIGINT, TEXT, INTEGER
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker, relationship

load_dotenv()
URL = os.getenv('DATABASE_URL')

engine = create_engine(URL, echo=False)

Base = declarative_base()

class Guild(Base):
    __tablename__ = 'guilds'

    id = Column(BIGINT, primary_key=True, unique=True)
    name = Column(TEXT)

class User(Base):
    __tablename__ = 'users'

    id = Column(BIGINT, primary_key=True, unique=True)
    name = Column(TEXT)

class Track(Base):
    __tablename__ = 'tracks'

    id = Column(INTEGER, Sequence('track_id_seq'), primary_key=True, unique=True)
    index = Column(INTEGER)
    web_url = Column(TEXT)
    title = Column(TEXT)
    duration = Column(INTEGER)
    guild_id = Column(BIGINT, ForeignKey('guilds.id'))

    guild = relationship('Guild', back_populates = 'tracks')

class Playlist(Base):
    __tablename__ = 'playlists'

    id = Column(Integer, Sequence('playlist_id_seq'), primary_key=True, unique=True)
    name = Column(String)
    index = Column(INTEGER)
    web_url = Column(TEXT)
    title = Column(TEXT)
    duration = Column(INTEGER)
    user_id = Column(BIGINT, ForeignKey('users.id'))

    user = relationship('User', back_populates = 'playlists')

Guild.tracks = relationship('Track', order_by = Track.id, back_populates = 'guild', cascade="all, delete, delete-orphan")
User.playlists = relationship('Playlist', order_by = Playlist.id, back_populates = 'user', cascade="all, delete, delete-orphan")

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

class Database():

    __slots__ = ('bot', '_guild', '_user', '_cog')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._user = ctx.message.author
        self._cog = ctx.cog

        session.execute(insert(User).values(id=self._user.id, name=self._user.name).on_conflict_do_nothing())

    @staticmethod
    def search(ctx, to_search):

        try:
            int(to_search)
            return session.query(Track).filter(Track.index == to_search).filter(Track.guild_id == ctx.guild.id).first()
        except ValueError:
            return session.query(Track).filter(Track.title.ilike('%{}%'.format(to_search))).filter(Track.guild_id == ctx.guild.id).first()

    def update_index(self, i):
        session.query(Track).filter(and_(Track.index > i, Track.guild_id == self._guild.id)).update({Track.index: Track.index - 1}, synchronize_session=False)
        session.commit()

    @staticmethod
    def clean_database(ctx):
        session.query(Track).filter(Track.guild_id == ctx.guild.id).delete(synchronize_session=False)

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

    @staticmethod
    def save_playlist(ctx, name):

        for track in session.query(Track).filter(Track.guild_id == ctx.guild.id):
            session.execute(insert(Playlist).values(name=name, index=track.index, web_url=track.web_url, title=track.title, duration=track.duration, user_id=ctx.message.author.id))

        session.commit()

    @staticmethod
    def get_playlists(ctx):

        return list(session.query(Playlist).filter(Playlist.user_id == ctx.message.author.id))

    @staticmethod
    def get_playlist_name(ctx, name):

        return session.query(Playlist).filter(Playlist.name.ilike(name), Playlist.user_id == ctx.message.author.id).all()

    async def load_playlist(self, ctx, name):

        await self.join(ctx)

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        player.pq.clear()
        Database.clean_database(self, ctx)

        player.wait = True

        for track in session.query(Playlist).filter(Playlist.name.ilike(name), Playlist.user_id == database._user.id):
            source = await YTDLSource.create_source(ctx, track.web_url, loop=self.bot.loop, download=True)

            player.value = player.value + 1
            player.pq.additem(source, track.index)

            session.execute(insert(Track).values(index=track.index, web_url=source.web_url, title=source.title, duration=source.duration, guild_id=ctx.guild.id).on_conflict_do_nothing())

        player.wait = False

        await ctx.message.add_reaction('✅')

        session.commit()

    @staticmethod
    def delete_playlist(ctx, name):

        session.query(Playlist).filter(Playlist.name == name, Playlist.user_id == ctx.message.author.id).delete(synchronize_session = False)

        session.commit()
