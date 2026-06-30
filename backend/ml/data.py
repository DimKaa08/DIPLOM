# backend/ml/data.py

from typing import Dict, List, Tuple
from sqlalchemy.orm import Session

from backend.db.session import SessionLocal
from backend.db.models_user_event import UserEvent
from backend.ml.config import EVENT_WEIGHTS


def build_id_mappings(
    db: Session,
) -> Tuple[Dict[int, int], Dict[int, int]]:
    """
    Возвращает:
    - user_id_to_idx: {user_id -> user_idx}
    - track_id_to_idx: {track_id -> item_idx}
    """
    user_ids = (
        db.query(UserEvent.user_id)
        .distinct()
        .order_by(UserEvent.user_id)
        .all()
    )
    track_ids = (
        db.query(UserEvent.track_id)
        .distinct()
        .order_by(UserEvent.track_id)
        .all()
    )

    user_id_to_idx = {
        user_id: idx for idx, (user_id,) in enumerate(user_ids)
    }
    track_id_to_idx = {
        track_id: idx for idx, (track_id,) in enumerate(track_ids)
    }

    return user_id_to_idx, track_id_to_idx


def load_samples() -> Tuple[
    List[Tuple[int, int, float]],
    Dict[int, int],
    Dict[int, int],
]:
    """
    Возвращает:
    - samples: список (user_idx, item_idx, label)
    - user_id_to_idx
    - track_id_to_idx
    """
    db: Session = SessionLocal()
    try:
        user_id_to_idx, track_id_to_idx = build_id_mappings(db)

        events = db.query(UserEvent).all()

        samples: List[Tuple[int, int, float]] = []

        for ev in events:
            if ev.event_type not in EVENT_WEIGHTS:
                continue

            user_idx = user_id_to_idx.get(ev.user_id)
            item_idx = track_id_to_idx.get(ev.track_id)

            if user_idx is None or item_idx is None:
                continue

            label = EVENT_WEIGHTS[ev.event_type]
            samples.append((user_idx, item_idx, label))

        return samples, user_id_to_idx, track_id_to_idx
    finally:
        db.close()
