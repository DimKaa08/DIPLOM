from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db import models
from backend.services.event_logger import EventLogger
from backend.routers.auth import get_current_user  # предполагаю, что тут твой current_user

router = APIRouter(prefix="/player", tags=["player"])


@router.get("/play/{track_id}")
def play_track(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    EventLogger.log(db, current_user.id, track.id, "play")

    # здесь твоя логика ответа
    return {
        "track_id": track.id,
        "title": track.title,
        "artist": track.artist,
    }


@router.post("/finish/{track_id}")
def finish_track(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    EventLogger.log(db, current_user.id, track.id, "finish")
    return {"status": "ok"}


@router.post("/skip/{track_id}")
def skip_track(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    EventLogger.log(db, current_user.id, track.id, "skip")
    return {"status": "ok"}
