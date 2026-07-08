# backend/db/models_user_event.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from backend.db.session import Base

class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), index=True, nullable=False)
    event_type = Column(String, nullable=False)  # play, skip, like, favorite, finish
    timestamp = Column(DateTime, server_default=func.now())
