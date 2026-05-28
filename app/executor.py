import asyncio
import logging
import re
from typing import Optional

# Trace Debugging: Standardize log output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AniCliExecutor")

class AniCliExecutor:
    """
    Asynchronously executes the ani-cli bash script and extracts media URLs.
    """
    def __init__(self, script_path: str = "/server/bin/ani-cli"):
        self.script_path = script_path

    async def get_stream_url(self, query: str, episode: int) -> Optional[str]:
        # Defensive Programming: Fail-fast before allocating resources
        assert isinstance(query, str) and len(query.strip()) > 0, "Query must be a valid, non-empty string."
        assert isinstance(episode, int) and episode > 0, "Episode must be a positive integer."
        
        logger.info(f"Initiating scraping for query: '{query}', Episode: {episode}")
        
        try:
            # We must use headless flags. Ensure ani-cli supports non-interactive output.
            # You may need to tweak these arguments based on ani-cli's current CLI docs.
            process = await asyncio.create_subprocess_exec(
                self.script_path, query, "-e", str(episode),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for execution without blocking the server
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Bash execution failed. Error: {stderr.decode().strip()}")
                return None
                
            return self._extract_link(stdout.decode())
            
        except Exception as e:
            logger.error(f"Critical state failure in executor: {str(e)}")
            return None

    def _extract_link(self, terminal_output: str) -> Optional[str]:
        """
        Parses the stdout using regex to find the final streaming link.
        """
        # Looks for http/https links ending in typical video formats
        match = re.search(r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|\.mkv))', terminal_output, re.IGNORECASE)
        if match:
            url = match.group(1)
            logger.info(f"Successfully extracted URL: {url}")
            return url
            
        logger.warning("Execution succeeded, but regex failed to find a valid media URL in stdout.")
        return None
