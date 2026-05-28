import asyncio
import logging
import os
import json
from typing import Optional, List, Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AniCliExecutor")

class AniCliExecutor:
    """
    Asynchronously coordinates catalog discovery and streaming link resolution.
    """
    def __init__(self, script_path: str = "/server/bin/ani-cli"):
        self.script_path = script_path
        # Replicating the exact operational header parameters from upstream source
        self.agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0"
        self.referer = "https://youtu-chan.com"
        self.api_url = "https://api.allanime.day/api"

    async def search_catalog(self, query: str) -> List[Dict[str, str]]:
        """
        Queries the upstream GraphQL index natively using curl and applies the exact sed parsing rule.
        """
        assert isinstance(query, str) and len(query.strip()) > 0, "Query payload cannot be empty."
        logger.info(f"Executing direct native API matrix scan for token: '{query}'")
        
        # Exact GraphQL payload extracted from script search loop definitions
        gql_query = (
            "query($search: SearchInput $limit: Int $page: Int $translationType: VaildTranslationTypeEnumType "
            "$countryOrigin: VaildCountryOriginEnumType) { shows(search: $search limit: $limit page: $page "
            "translationType: $translationType countryOrigin: $countryOrigin) { edges { _id name availableEpisodes __typename } }}"
        )
        
        payload = {
            "variables": {
                "search": {
                    "allowAdult": False,
                    "allowUnknown": False,
                    "query": query
                },
                "limit": 40,
                "page": 1,
                "translationType": "sub",
                "countryOrigin": "ALL"
            },
            "query": gql_query
        }

        try:
            # We bypass the script and invoke curl + sed directly to escape terminal traps completely
            curl_cmd = (
                f"curl -e '{self.referer}' -s -H 'Content-Type: application/json' -X POST '{self.api_url}' "
                f"-d '{json.dumps(payload)}' -A '{self.agent}' | "
                f"sed 's|Show|\\n|g' | sed -nE 's|.*_id\":\"([^\"]*)\",\"name\":\"(.+)\",.*sub\":([1-9][^,]*).*|\\1\\t\\2 (\\3 episodes)|p' | sed 's/\\\\\"//g'"
            )
            
            process = await asyncio.create_subprocess_shell(
                curl_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Native API bridge faulted: {stderr.decode().strip()}")
                return []
                
            matches = []
            raw_output = stdout.decode().strip()
            
            for line in raw_output.split("\n"):
                if "\t" in line:
                    anime_id, metadata = line.split("\t", 1)
                    matches.append({
                        "id": anime_id.strip(),
                        "title": metadata.strip()
                    })
            return matches
            
        except Exception as e:
            logger.error(f"Critical data mapping failure inside api bridge: {str(e)}")
            return []

    async def get_stream_url(self, anime_id: str, episode: int) -> Optional[str]:
        """
        Resolves direct streaming parameters by supplying surgical item identifiers to the script.
        """
        assert isinstance(anime_id, str) and len(anime_id.strip()) > 0, "ID payload cannot be empty."
        assert isinstance(episode, int) and episode > 0, "Episode index must be positive."
        
        logger.info(f"Spawning scraper process for Target ID: '{anime_id}', Episode: {episode}")
        
        try:
            custom_env = os.environ.copy()
            custom_env["ANI_CLI_PLAYER"] = "debug"
            
            # Streaming works fine with -S 1 because it bypasses the search menu entirely when an exact ID match hits
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
