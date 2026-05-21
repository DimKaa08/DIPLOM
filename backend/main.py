from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import auth, search, stream, playlist, favorites, recommendations
from backend.db.session import init_db


app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth")
app.include_router(search.router, prefix="/search")
app.include_router(stream.router, prefix="/stream")
app.include_router(playlist.router, prefix="/playlist")
app.include_router(favorites.router, prefix="/favorites")
app.include_router(recommendations.router, prefix="/recommendations")

@app.on_event("startup")
async def on_startup():
    init_db()
