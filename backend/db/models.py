from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Table
from sqlalchemy.orm import relationship
from .session import Base
from datetime import datetime

playlist_tracks = Table(
    "playlist_tracks",
    Base.metadata,
    Column("playlist_id", ForeignKey("playlists.id"), primary_key=True),
    Column("track_id", ForeignKey("tracks.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    favorites = relationship("Favorite", back_populates="user")
    history = relationship("History", back_populates="user")
    playlists = relationship("Playlist", back_populates="user")


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)  # youtube / soundcloud / spotify
    source_id = Column(String, index=True)  # id в источнике
    title = Column(String)
    artist = Column(String)
    duration = Column(Integer, nullable=True)
    thumbnail_url = Column(String, nullable=True)

    favorites = relationship("Favorite", back_populates="track")
    history = relationship("History", back_populates="track")
    playlists = relationship("Playlist", secondary=playlist_tracks, back_populates="tracks")


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    type = Column(String, default="custom")  # custom / recommendations / favorites / history
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="playlists")
    tracks = relationship("Track", secondary=playlist_tracks, back_populates="playlists")


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    track_id = Column(Integer, ForeignKey("tracks.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="favorites")
    track = relationship("Track", back_populates="favorites")


class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    track_id = Column(Integer, ForeignKey("tracks.id"))
    played_at = Column(DateTime, default=datetime.utcnow)
    listened_seconds = Column(Integer, default=0)
    skipped = Column(Boolean, default=False)

    user = relationship("User", back_populates="history")
    track = relationship("Track", back_populates="history")
