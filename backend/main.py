# backend/main.py
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import auth, search, stream, playlist, favorites, recommendations
from backend.routers.events import router as events_router
from backend.db.session import init_db

load_dotenv()

# ── CORS ──────────────────────────────────────────────────────────────────────
# Берём список из .env, с fallback на localhost для разработки.
# ВАЖНО: нельзя использовать ["*"] вместе с allow_credentials=True —
# браузеры блокируют такие ответы. Нужен конкретный список источников.
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")


# ── LIFESPAN (заменяет устаревший @app.on_event) ──────────────────────────────
# Код до yield выполняется при старте, после yield — при остановке сервера.
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Database] Инициализация базы данных...")
    init_db()
    yield
    # Здесь можно закрыть соединения, пул и т.д. при остановке


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

# ── РОУТЕРЫ ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,            tags=["Auth"])
app.include_router(search.router,          tags=["Search"])
app.include_router(stream.router,          tags=["Stream"])
app.include_router(playlist.router,        tags=["Playlist"])
app.include_router(favorites.router,       tags=["Favorites"])
app.include_router(recommendations.router, tags=["Recommendations"])
app.include_router(events_router,          tags=["Events"])


@app.get("/")
def root():
    return {"status": "ok", "message": "Backend is running smoothly"}