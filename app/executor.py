import asyncio
import logging
import os
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
        # Defensive Programming: Fail-fast validation checkpoints
        assert isinstance(query, str) and len(query.strip()) > 0, "Query must be a valid, non-empty string."
        assert isinstance(episode, int) and episode > 0, "Episode must be a positive integer."
        
        logger.info(f"Initiating scraping for query: '{query}', Episode: {episode}")
        
        try:
            # Copy environment and enforce headless player mode
            custom_env = os.environ.copy()
            custom_env["ANI_CLI_PLAYER"] = "debug"
            
            # Subprocess Configuration: Pass options BEFORE the query argument
            process = await asyncio.create_subprocess_exec(
                self.script_path, 
                "-S", "1", 
                "-e", str(episode), 
                query,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=custom_env
            )
            
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
        Parses the stdout by anchoring directly to the script's debug layout block.
        """
        logger.info("Parsing terminal standard output stream...")
        if "Selected link:" not in terminal_output:
            logger.warning("Execution completed, but 'Selected link:' anchor missing from stdout.")
            return None
            
        try:
            # Slice output directly after the explicit 'Selected link:' line marker
            parts = terminal_output.split("Selected link:")
            raw_link = parts[1].strip().split("\n")[0].strip()
            
            if raw_link.startswith("http"):
                logger.info(f"Successfully isolated URL from debug block.")
                return raw_link
        except Exception as e:
            logger.error(f"Failed to parse string boundary matrix: {str(e)}")
            
        logger.warning("Target block extraction failed to isolate a valid HTTP sequence.")
        return None
