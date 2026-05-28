from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List
from app.executor import AniCliExecutor
import logging

# Trace Debugging Configuration
logger = logging.getLogger("API_Router")
app = FastAPI(title="Premium Anime Scraper API")
executor = AniCliExecutor()

# Data Transfer Objects for Structural Responses
class AnimeSearchMatch(BaseModel):
    id: str
    title: str

class StreamResponse(BaseModel):
    anime_id: str
    episode: int
    url: str
    referer: str  # Critical cross-origin media header payload

@app.get("/api/v1/search", response_model=List[AnimeSearchMatch])
async def search_anime(query: str = Query(..., min_length=2, description="The text search query")):
    """
    Queries the upstream index and extracts matching titles with their specific IDs.
    """
    logger.info(f"Incoming catalog search request for token: '{query}'")
    results = await executor.search_catalog(query)
    
    if not results:
        logger.warning(f"Catalog query returned 0 matches for token: '{query}'")
        raise HTTPException(status_code=404, detail="No matching anime series discovered.")
        
    return results

@app.get("/api/v1/stream", response_model=StreamResponse)
async def get_stream(
    anime_id: str = Query(..., description="The precise upstream structural ID of the anime"),
    episode: int = Query(..., gt=0, description="Target episode marker")
):
    """
    Resolves the exact stream URL using the specified series ID and episode index.
    """
    logger.info(f"Stream generation requested for ID: '{anime_id}', Episode: {episode}")
    url = await executor.get_stream_url(anime_id, episode)
    
    if not url:
        logger.error(f"Execution matrix failed to resolve stream link for ID: '{anime_id}'")
        # Graceful Degradation: Trigger client-side under-maintenance screen
        raise HTTPException(
            status_code=503, 
            detail="Upstream scraper failed or is under maintenance. Try again later."
        )
        
    return StreamResponse(
        anime_id=anime_id,
        episode=episode,
        url=url,
        referer="https://youtu-chan.com"  # Bypasses resource blockades automatically
    )

@app.get("/health")
async def health_check():
    return {"status": "online", "system": "optimal"}
