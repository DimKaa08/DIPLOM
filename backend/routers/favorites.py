from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..db.session import get_db
from ..db import models
#from auth import get_current_user

router = APIRouter()


@router.post("/add")
def add_favorite(
    track_id: int,
    db: Session = Depends(get_db),
    #user_id: int = Depends(get_current_user)
):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    #fav = models.Favorite(user_id=user_id, track_id=track_id)
    #db.add(fav)
    #db.commit()
    #db.refresh(fav)
    return {"status": "ok", "favorite_id": None}


@router.delete("/remove")
def remove_favorite(
    track_id: int,
    db: Session = Depends(get_db),
    #user_id: int = Depends(get_current_user)
):
    fav = (
        db.query(models.Favorite)
        #.filter(models.Favorite.user_id == user_id, models.Favorite.track_id == track_id)
        .first()
    )
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete(fav)
    db.commit()
    return {"status": "ok"}


@router.get("/list", response_model=List[int])
def list_favorites(
    db: Session = Depends(get_db),
    #user_id: int = Depends(get_current_user)
):
    #favs = db.query(models.Favorite).filter(models.Favorite.user_id == user_id).all()
    #return [f.track_id for f in favs]
    return []