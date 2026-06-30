# backend/services/event_logger.py
from sqlalchemy.orm import Session
from backend.db.models_user_event import UserEvent

class EventLogger:
    @staticmethod
    def log(db: Session, user_id: int, track_id: int, event_type: str):
        event = UserEvent(
            user_id=user_id,
            track_id=track_id,
            event_type=event_type
        )
        db.add(event)
        db.commit()
