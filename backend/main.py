# backend/main.py  — добавлен onboarding роутер
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import auth, search, stream, playlist, favorites, recommendations
from backend.routers.events     import router as events_router
from backend.routers.onboarding import router as onboarding_router   # ← НОВОЕ
from backend.db.session import init_db, SessionLocal
from backend.db import models

load_dotenv()

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")


def _should_train() -> bool:
    from backend.ml.config import MAPPINGS_PATH
    import torch
    mappings_ok = False
    if os.path.exists(MAPPINGS_PATH):
        try:
            m = torch.load(MAPPINGS_PATH, map_location="cpu")
            mappings_ok = "user2idx" in m and "item2idx" in m
        except Exception:
            mappings_ok = False
    if mappings_ok:
        return False
    db = SessionLocal()
    try:
        return db.query(models.UserInteraction).count() >= 10
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Database] Инициализация базы данных...")
    init_db()
    try:
        if _should_train():
            from backend.ml.tasks import train_task
            task = train_task.delay(epochs=5, batch_size=16)
            print(f"[ML] Автообучение при старте. task_id={task.id}")
        else:
            print("[ML] Модель актуальна или данных недостаточно.")
    except Exception as e:
        print(f"[ML] Не удалось запустить автообучение: {e}")
    yield
    print("[Server] Завершение работы.")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

app.include_router(auth.router,            tags=["Auth"])
app.include_router(search.router,          tags=["Search"])
app.include_router(stream.router,          tags=["Stream"])
app.include_router(playlist.router,        tags=["Playlist"])
app.include_router(favorites.router,       tags=["Favorites"])
app.include_router(recommendations.router, tags=["Recommendations"])
app.include_router(events_router,          tags=["Events"])
app.include_router(onboarding_router,      tags=["Onboarding"])   # ← НОВОЕ


@app.get("/")
def root():
    return {"status": "ok", "message": "Backend is running smoothly"}