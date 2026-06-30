# backend/db/models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, Float, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from .session import Base
from datetime import datetime


# Смежная таблица для связи многие-ко-многим (Playlists <-> Tracks)
playlist_tracks = Table(
    "playlist_tracks",
    Base.metadata,
    Column("playlist_id", ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    # Стандартные связи
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    history = relationship("History", back_populates="user", cascade="all, delete-orphan")
    playlists = relationship("Playlist", back_populates="user", cascade="all, delete-orphan")
    
    # Связи с черными списками
    blacklist = relationship("RecommendationBlacklist", back_populates="user", cascade="all, delete-orphan")
    blacklist_tracks = relationship("TrackBlacklist", back_populates="user", cascade="all, delete-orphan")

    # Сбор логов и профилирования для обучения ИИ
    interactions = relationship("UserInteraction", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String)  # 'youtube' или 'soundcloud'
    source_id = Column(String, unique=True, index=True)
    title = Column(String)
    artist = Column(String, nullable=True)
    genre = Column(String, nullable=True)  # Вот эта колонка!
    duration = Column(Integer, default=180)
    thumbnail_url = Column(String, nullable=True)

    # Обратные связи
    favorites = relationship("Favorite", back_populates="track", cascade="all, delete-orphan")
    history = relationship("History", back_populates="track", cascade="all, delete-orphan")
    playlists = relationship("Playlist", secondary=playlist_tracks, back_populates="tracks")
    blacklist = relationship("TrackBlacklist", back_populates="track", cascade="all, delete-orphan")
    
    # Связь с логами взаимодействий для анализа жанров/треков моделью
    interactions = relationship("UserInteraction", back_populates="track", cascade="all, delete-orphan")


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    type = Column(String, default="custom")  # custom / recommendations / favorites / history
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    user = relationship("User", back_populates="playlists")
    tracks = relationship("Track", secondary=playlist_tracks, back_populates="playlists")


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="favorites")
    track = relationship("Track", back_populates="favorites")


class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"))
    played_at = Column(DateTime, default=datetime.utcnow)
    listened_seconds = Column(Integer, default=0)
    skipped = Column(Boolean, default=False)

    user = relationship("User", back_populates="history")
    track = relationship("Track", back_populates="history")


# 📊 МОДЕРНИЗИРОВАННАЯ ТАБЛИЦА: Логи для обучения рекомендательной системы
class UserInteraction(Base):
    __tablename__ = "user_interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False) # Сделали связь числовой для джоинов жанров
    
    # Метрики удержания и прослушивания
    listen_duration = Column(Integer, default=0)    # Сколько секунд прослушано суммарно
    completion_rate = Column(Float, default=0.0)    # Процент прослушивания (0.0 - 1.0)
    is_finished = Column(Boolean, default=False)    # 👈 Дослушал ли до самого конца?
    is_looped = Column(Boolean, default=False)      # Поставил ли на повтор (Loop)

    # Метрики пропуска (Скипов)
    was_skipped = Column(Boolean, default=False)    # Был ли пропущен
    skip_position = Column(Integer, nullable=True)  # 👈 На какой конкретно секунде нажал кнопку "Вперед"
    skip_type = Column(String, nullable=True)       # 👈 'immediate' (сразу <10с) / 'partial' (послушал немного) / 'none'

    # Результирующий скор для датасета ML
    engagement_score = Column(Float, default=0.0) 
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="interactions")
    track = relationship("Track", back_populates="interactions")


# 🧠 НОВАЯ ТАБЛИЦА: Профиль вычисленных предпочтений пользователя (Data Store для выдачи рекомендаций)
# 🧠 ПРОФИЛЬ ВКУСОВ: Теперь работает и на SQLite, и на PostgreSQL
class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    
    # .with_variant говорит: "По умолчанию используй JSON (для SQLite), но если это postgresql — бахай JSONB"
    preferred_genres = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)
    preferred_artists = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)
    
    # Средний порог терпения пользователя в секундах перед скипом плохой песни
    skip_threshold = Column(Float, default=10.0)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="preferences")


# 📌 МОДЕЛЬ ЧЕРНОГО СПИСКА 1: Для внешних кандидатов (YT/SoundCloud) по их строковому ID
class RecommendationBlacklist(Base):
    __tablename__ = "recommendation_blacklists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    track_id = Column(String, index=True, nullable=False)  
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="blacklist")


# 📌 МОДЕЛЬ ЧЕРНОГО СПИСКА 2: Блокировка треков, уже сохраненных в нашей БД tracks
class TrackBlacklist(Base):
    __tablename__ = "track_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow) 

    user = relationship("User", back_populates="blacklist_tracks")
    track = relationship("Track", back_populates="blacklist")