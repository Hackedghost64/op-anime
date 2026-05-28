import asyncio
import logging
import os
from typing import Optional, List, Dict

# Standardize log outputs across processing boundaries
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AniCliExecutor")

class AniCliExecutor:
    """
    Asynchronously coordinates the headless execution of the underlying scraper script.
    """
    def __init__(self, script_path: str = "/server/bin/ani-cli"):
        self.script_path = script_path

    async def search_catalog(self, query: str) -> List[Dict[str, str]]:
        """
        Executes text searches and handles standard terminal text maps defensively.
        """
        assert isinstance(query, str) and len(query.strip()) > 0, "Query payload cannot be empty."
        logger.info(f"Spawning catalog search process for: '{query}'")
        
        try:
            custom_env = os.environ.copy()
            custom_env["ANI_CLI_PLAYER"] = "debug"
            
            # We explicitly feed an empty input to the process standard input channel.
            # This triggers an immediate EOF when the script prompts for menu loops,
            # forcing the internal search functions to dump the parsed index to stdout.
            process = await asyncio.create_subprocess_exec(
                self.script_path, query,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=custom_env
            )
            
            # Send EOF immediately to bypass interactive wait matrices
            stdout, stderr = await process.communicate(input=b"\n")
            
            raw_output = stdout.decode().strip()
            logger.info(f"Raw process stdout capture check completed.")
            
            matches = []
            # Parse the tab-separated records returned from search_anime()
            for line in raw_output.split("\n"):
                if "\t" in line:
                    anime_id, metadata = line.split("\t", 1)
                    matches.append({
                        "id": anime_id.strip(),
                        "title": metadata.strip()
                    })
            return matches
            
        except Exception as e:
            logger.error(f"Critical state failure during directory lookup: {str(e)}")
            return []

    async def get_stream_url(self, anime_id: str, episode: int) -> Optional[str]:
        """
        Resolves direct streaming parameters by supplying surgical item identifiers.
        """
        assert isinstance(anime_id, str) and len(anime_id.strip()) > 0, "ID payload cannot be empty."
        assert isinstance(episode, int) and episode > 0, "Episode index must be positive."
        
        logger.info(f"Spawning scraper process for Target ID: '{anime_id}', Episode: {episode}")
        
        try:
            custom_env = os.environ.copy()
            custom_env["ANI_CLI_PLAYER"] = "debug"
            
            # Use strict integer 1 to select the exact targeted match safely
            process = await asyncio.create_subprocess_exec(
                self.script_path, 
                "-S", "1", 
                "-e", str(episode), 
                anime_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=custom_env
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Media resolver sub-process faulted: {stderr.decode().strip()}")
                return None
                
            return self._extract_link(stdout.decode())
            
        except Exception as e:
            logger.error(f"Critical state failure during content resolution: {str(e)}")
            return None

    def _extract_link(self, terminal_output: str) -> Optional[str]:
        """
        Slices the raw standard output stream cleanly relative to the text boundaries.
        """
        logger.info("Analyzing process standard output block...")
        if "Selected link:" not in terminal_output:
            logger.warning("Target block failed validation: 'Selected link:' string token missing.")
            return None
            
        try:
            parts = terminal_output.split("Selected link:")
            raw_link = parts[1].strip().split("\n")[0].strip()
            
            if raw_link.startswith("http"):
                logger.info("Successfully extracted HTTP stream target segment.")
                return raw_link
        except Exception as e:
            logger.error(f"Boundary index parsing failure: {str(e)}")
            
        logger.warning("Output evaluation terminated without finding a clean URI sequence.")
        return None
