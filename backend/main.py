from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, search, stream, playlists, favorites, recommendations
from db.session import init_db

app = FastAPI(title="Music Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # потом сузишь под фронт
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(stream.router, prefix="/stream", tags=["stream"])
app.include_router(playlists.router, prefix="/playlists", tags=["playlists"])
app.include_router(favorites.router, prefix="/favorites", tags=["favorites"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])


@app.on_event("startup")
async def on_startup():
    init_db()
