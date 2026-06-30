# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Импортируем роутеры чисто, без дубликатов
from backend.routers import auth, search, stream, playlist, favorites, recommendations
from backend.routers.events import router as events_router
from backend.db.session import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Определяем список разрешенных адресов (откуда идет фронтенд)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # или ваш URL фронтенда, например, ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # ВАЖНО: Браузер должен видеть эти заголовки, чтобы плеер мог мотать трек!
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"] 
)

# Настройка CORS (поддерживает и 3000, и 5173 для Vite)

# ─── ПОДКЛЮЧЕНИЕ РОУТЕРОВ (БЕЗ ДУБЛИРОВАНИЯ ПРЕФИКСОВ) ─────────────────────
# Мы полностью убрали аргумент prefix="..." из include_router. 
# Теперь все префиксы пуленепробиваемо настраиваются внутри самих файлов роутеров.

app.include_router(search.router)
app.include_router(stream.router, tags=["Stream"])
app.include_router(auth.router, tags=["Auth"])
app.include_router(playlist.router, tags=["Playlist"])
app.include_router(favorites.router, tags=["Favorites"])
app.include_router(recommendations.router, tags=["Recommendations"])
app.include_router(events_router, tags=["Events"])


@app.on_event("startup")
async def on_startup():
    print("[Database] Инициализация базы данных...")
    init_db()


@app.get("/")
def root():
    return {"status": "ok", "message": "Backend is running smoothly"}