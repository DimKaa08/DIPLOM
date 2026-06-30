from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db import models
from backend.services.event_logger import EventLogger
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/likes", tags=["likes"])


@router.post("/{track_id}")
def like_track(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    like = models.Like(user_id=current_user.id, track_id=track.id)
    db.add(like)
    db.commit()

    EventLogger.log(db, current_user.id, track.id, "like")

    return {"status": "liked"}
