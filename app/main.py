from enum import Enum
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.executor import AniCliExecutor

app = FastAPI(
    title="op-anime API",
    description="Self-healing anime backend powered by ani-cli",
    version="2.0.0",
)

# CORS — allows Flutter web, any browser client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

executor = AniCliExecutor()


# --------------------------------------------------------------------------
# Enums & Models
# --------------------------------------------------------------------------

class TranslationType(str, Enum):
    sub = "sub"
    dub = "dub"


class SearchResult(BaseModel):
    id: str
    title: str


class EpisodesResponse(BaseModel):
    anime_id: str
    mode: str
    episodes: List[str]
    count: int


class StreamResponse(BaseModel):
    anime_id: str
    episode: str
    url: str
    referer: str
    quality: Optional[str] = None


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@app.get("/api/v1/search", response_model=List[SearchResult])
async def search_anime(
    query: str = Query(..., min_length=1, description="Anime title to search for"),
    mode: TranslationType = Query(
        TranslationType.sub, description="sub or dub"
    ),
):
    """
    Search the anime catalog by title.

    Returns a list of matching anime with their IDs and titles.
    The ID is needed for the /episodes and /stream endpoints.
    """
    results = await executor.search(query, mode=mode.value)

    if not results:
        raise HTTPException(status_code=404, detail="No results found.")

    return [SearchResult(**r) for r in results]


@app.get("/api/v1/episodes", response_model=EpisodesResponse)
async def get_episodes(
    anime_id: str = Query(..., min_length=1, description="Anime ID from search results"),
    mode: TranslationType = Query(
        TranslationType.sub, description="sub or dub"
    ),
):
    """
    List all available episode numbers for a given anime.

    Use the anime_id returned by /search. Episode numbers may
    include decimals (e.g. "5.5" for specials).
    """
    episodes = await executor.episodes(anime_id, mode=mode.value)

    if not episodes:
        raise HTTPException(
            status_code=404,
            detail="No episodes found for this anime and translation type.",
        )

    return EpisodesResponse(
        anime_id=anime_id,
        mode=mode.value,
        episodes=episodes,
        count=len(episodes),
    )


@app.get("/api/v1/stream", response_model=StreamResponse)
async def get_stream(
    anime_id: str = Query(..., min_length=1, description="Anime ID from search results"),
    episode: str = Query(..., min_length=1, description="Episode number (e.g. '1', '5.5')"),
    mode: TranslationType = Query(
        TranslationType.sub, description="sub or dub"
    ),
    quality: str = Query(
        "best", description="Video quality: best, worst, 720p, 1080p, etc."
    ),
):
    """
    Resolve a direct stream URL for a specific episode.

    The returned URL can be played directly in a video player.
    Include the returned referer header when fetching the stream
    to avoid CORS / hotlink blocks.
    """
    result = await executor.get_stream(
        anime_id, episode, mode=mode.value, quality=quality
    )

    if not result:
        raise HTTPException(
            status_code=503,
            detail="Failed to resolve stream URL. The upstream scraper may be "
            "down or the episode may not be available. Try again later.",
        )

    return StreamResponse(
        anime_id=anime_id,
        episode=episode,
        url=result["url"],
        referer=result.get("referer", ""),
        quality=quality,
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
