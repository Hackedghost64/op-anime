import asyncio
from enum import Enum
from typing import List, Optional
import httpx
import re
import os
import logging
from urllib.parse import urljoin, quote, unquote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
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
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],
)

executor = AniCliExecutor()
http_client = httpx.AsyncClient(follow_redirects=True, verify=False)
logger = logging.getLogger("uvicorn")


async def update_ani_cli():
    ani_cli_url = "https://raw.githubusercontent.com/pystardust/ani-cli/master/ani-cli"
    local_bin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
    local_ani_cli_path = os.path.join(local_bin_dir, "ani-cli")
    
    logger.info(f"Self-healing: Checking/Updating ani-cli from {ani_cli_url}...")
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            res = await client.get(ani_cli_url)
            if res.status_code == 200:
                os.makedirs(local_bin_dir, exist_ok=True)
                with open(local_ani_cli_path, "wb") as f:
                    f.write(res.content)
                os.chmod(local_ani_cli_path, 0o755)
                logger.info("Self-healing: Successfully updated ani-cli to latest upstream version!")
            else:
                logger.warning(f"Self-healing: Failed to fetch ani-cli, status code {res.status_code}. Using local version.")
    except Exception as e:
        logger.error(f"Self-healing: Error updating ani-cli script: {str(e)}. Using local version.")


async def periodic_ani_cli_updater():
    while True:
        # Check and update every 12 hours (43200 seconds)
        await asyncio.sleep(43200)
        await update_ani_cli()


@app.on_event("startup")
async def startup_event():
    # Run immediate update check at startup
    await update_ani_cli()
    # Spawn background task for periodic update check
    asyncio.create_task(periodic_ani_cli_updater())




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
        raise HTTPException(status_code=404, detail="Search catalog is undergoing brief maintenance. Please try again in a few minutes.")

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
            detail="Episode database is undergoing brief maintenance. Please check back shortly.",
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
            detail="This streaming source is currently undergoing scheduled maintenance. Please try again in a few minutes.",
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


def rewrite_m3u8(content: str, base_url: str, referer: Optional[str]) -> str:
    lines = content.splitlines()
    new_lines = []
    for line in lines:
        line_str = line.strip()
        if not line_str:
            new_lines.append(line)
            continue

        if line_str.startswith("#"):
            # Check for URI="..." attribute (e.g. in EXT-X-KEY or EXT-X-MEDIA)
            match = re.search(r'URI="([^"]+)"', line)
            if match:
                uri = match.group(1)
                abs_url = urljoin(base_url, uri)
                proxy_url = f"/api/v1/proxy?url={quote(abs_url)}"
                if referer:
                    proxy_url += f"&referer={quote(referer)}"
                line = line.replace(f'URI="{uri}"', f'URI="{proxy_url}"')
            new_lines.append(line)
        else:
            abs_url = urljoin(base_url, line_str)
            proxy_url = f"/api/v1/proxy?url={quote(abs_url)}"
            if referer:
                proxy_url += f"&referer={quote(referer)}"
            new_lines.append(proxy_url)
    return "\n".join(new_lines)


@app.api_route("/api/v1/proxy", methods=["GET", "HEAD"])
async def proxy(request: Request, url: str = Query(...), referer: Optional[str] = Query(None)):
    target_url = unquote(url)

    # Forward headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }

    # Pass along range and other relevant headers
    if "range" in request.headers:
        headers["Range"] = request.headers["range"]
    if referer:
        headers["Referer"] = unquote(referer)
    elif "referer" in request.headers:
        if not ("localhost" in request.headers["referer"] or "127.0.0.1" in request.headers["referer"]):
            headers["Referer"] = request.headers["referer"]

    try:
        req = http_client.build_request(request.method, target_url, headers=headers)
        response = await http_client.send(req, stream=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail="This stream is currently undergoing maintenance. Please try again in a few minutes.")

    content_type = response.headers.get("content-type", "")
    if content_type == "application/octet-stream" or not content_type:
        content_type = "video/mp4"

    # For HEAD requests, return headers immediately without body
    if request.method == "HEAD":
        res_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
        for h in ["content-length", "content-range", "content-type", "accept-ranges"]:
            if h in response.headers:
                res_headers[h] = response.headers[h]
        # Force CORS video type
        if "content-type" not in res_headers or res_headers["content-type"] == "application/octet-stream":
            res_headers["content-type"] = "video/mp4"
            
        await response.aclose()
        return Response(status_code=response.status_code, headers=res_headers, media_type=content_type)

    # Check if this is an HLS playlist (m3u8)
    if "mpegurl" in content_type.lower() or "mpegurl" in target_url.lower() or target_url.endswith(".m3u8"):
        try:
            await response.aread()
            playlist_text = response.text
            base_url = str(response.url)
            rewritten = rewrite_m3u8(playlist_text, base_url, referer)
            return Response(
                content=rewritten,
                status_code=response.status_code,
                media_type="application/vnd.apple.mpegurl",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        except Exception as e:
            await response.aclose()
            raise HTTPException(status_code=500, detail="This playlist is undergoing scheduled maintenance. Please try again in a few minutes.")

    # For standard binary files (TS chunks, video files)
    async def chunk_generator():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()

    res_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
    }

    for h in ["content-length", "content-range", "content-type", "accept-ranges"]:
        if h in response.headers:
            res_headers[h] = response.headers[h]

    # Force CORS video type
    if "content-type" not in res_headers or res_headers["content-type"] == "application/octet-stream":
        res_headers["content-type"] = "video/mp4"

    return StreamingResponse(
        chunk_generator(),
        status_code=response.status_code,
        headers=res_headers,
        media_type=content_type
    )

