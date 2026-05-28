import asyncio
import logging
import os
from typing import Optional, List, Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AniCliExecutor")

# Timeouts in seconds — search/episodes are fast API calls,
# stream needs multiple provider fetches in parallel
TIMEOUT_FAST = 30
TIMEOUT_STREAM = 60


class AniCliExecutor:
    """
    Async Python bridge to ani-cli-api.sh.

    Every call delegates to the shell wrapper, which sources the upstream
    ani-cli functions directly. When the bash script is updated by GitHub
    Actions, all logic here automatically reflects those changes.
    """

    def __init__(self, wrapper_path: str = "/server/bin/ani-cli-api.sh"):
        self.wrapper = wrapper_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_env(self, mode: str = "sub", quality: str = "best") -> dict:
        """Build a subprocess environment with ani-cli overrides."""
        env = os.environ.copy()
        env["ANI_CLI_MODE"] = mode
        env["ANI_CLI_QUALITY"] = quality
        # Safety: ensure the wrapper never tries to open a player
        env["ANI_CLI_PLAYER"] = "debug"
        return env

    async def _run(
        self,
        *args: str,
        env: Optional[dict] = None,
        timeout: int = TIMEOUT_FAST,
    ) -> tuple[str, str, int]:
        """
        Run the wrapper script with the given arguments.
        Returns (stdout, stderr, returncode).
        Kills the process if it exceeds the timeout.
        """
        process = await asyncio.create_subprocess_exec(
            self.wrapper,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env or self._build_env(),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.error("Subprocess timed out after %ds: %s %s", timeout, self.wrapper, " ".join(args))
            raise
        return stdout.decode(), stderr.decode(), process.returncode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(self, query: str, mode: str = "sub") -> List[Dict[str, str]]:
        """
        Search the anime catalog. Returns a list of {id, title} dicts.

        Calls ani-cli's search_anime() function under the hood, which
        hits the upstream GraphQL API and parses results with sed.
        """
        env = self._build_env(mode=mode)
        try:
            stdout, stderr, rc = await self._run("search", query, env=env)
        except asyncio.TimeoutError:
            return []

        if rc != 0:
            logger.error("Search failed (rc=%d): %s", rc, stderr.strip())
            return []

        results: List[Dict[str, str]] = []
        for line in stdout.strip().split("\n"):
            if "\t" in line:
                anime_id, title = line.split("\t", 1)
                results.append({
                    "id": anime_id.strip(),
                    "title": title.strip(),
                })
        return results

    async def episodes(self, anime_id: str, mode: str = "sub") -> List[str]:
        """
        List available episode numbers for a given anime ID.

        Calls ani-cli's episodes_list() function, which queries the
        upstream GraphQL API for the show's availableEpisodesDetail.
        """
        env = self._build_env(mode=mode)
        try:
            stdout, stderr, rc = await self._run("episodes", anime_id, env=env)
        except asyncio.TimeoutError:
            return []

        if rc != 0:
            logger.error("Episodes list failed (rc=%d): %s", rc, stderr.strip())
            return []

        return [ep.strip() for ep in stdout.strip().split("\n") if ep.strip()]

    async def get_stream(
        self,
        anime_id: str,
        episode: str,
        mode: str = "sub",
        quality: str = "best",
    ) -> Optional[Dict[str, str]]:
        """
        Resolve a direct stream URL for a specific episode.

        Calls ani-cli's get_episode_url() function, which:
        1. Fetches episode embed data from the upstream API
        2. Decrypts the response if needed (openssl aes-256-ctr)
        3. Resolves direct links from multiple providers in parallel
        4. Selects the link matching the requested quality

        Returns {url, referer} or None on failure.
        """
        env = self._build_env(mode=mode, quality=quality)
        try:
            stdout, stderr, rc = await self._run(
                "stream", anime_id, episode, env=env, timeout=TIMEOUT_STREAM
            )
        except asyncio.TimeoutError:
            return None

        if rc != 0:
            logger.error("Stream resolution failed (rc=%d): %s", rc, stderr.strip())
            return None

        return self._parse_stream_output(stdout)

    @staticmethod
    def _parse_stream_output(output: str) -> Optional[Dict[str, str]]:
        """Parse the wrapper's URL:/REFERER: prefixed output."""
        result: Dict[str, str] = {}
        for line in output.strip().split("\n"):
            if line.startswith("URL:"):
                result["url"] = line[4:].strip()
            elif line.startswith("REFERER:"):
                result["referer"] = line[8:].strip()

        if "url" not in result or not result["url"].startswith("http"):
            logger.warning("Stream output did not contain a valid URL")
            return None
        return result
