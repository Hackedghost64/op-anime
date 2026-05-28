from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from app.executor import AniCliExecutor
import logging

logger = logging.getLogger("API_Router")
app = FastAPI(title="Premium Anime Scraper API")
executor = AniCliExecutor()

# Data Transfer Object for clean JSON responses
class StreamResponse(BaseModel):
    query: str
    episode: int
    url: str

@app.get("/api/v1/stream", response_model=StreamResponse)
async def get_stream(
    query: str = Query(..., description="The name of the anime"),
    episode: int = Query(..., gt=0, description="The episode number")
):
    """
    Endpoint for the Flutter app to request a video stream.
    """
    logger.info(f"Received API request for {query} ep {episode}")
    
    url = await executor.get_stream_url(query, episode)
    
    if not url:
        logger.error("Failed to retrieve URL. Sending 503 Graceful Degradation to client.")
        # Graceful Degradation: Flutter will catch this 503 and show the "Under Maintenance" UI.
        raise HTTPException(
            status_code=503, 
            detail="Upstream scraper failed or is under maintenance. Try again later."
        )
        
    return StreamResponse(query=query, episode=episode, url=url)

@app.get("/health")
async def health_check():
    return {"status": "online", "system": "optimal"}
