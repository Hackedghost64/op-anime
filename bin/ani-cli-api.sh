#!/bin/sh
# ani-cli-api.sh — Headless API wrapper for ani-cli
#
# Sources function definitions and variables from the upstream ani-cli
# script, then exposes search/episodes/stream commands for server use.
#
# SELF-HEALING: When GitHub Actions updates bin/ani-cli from upstream,
# this wrapper automatically inherits the new functions, GraphQL queries,
# API URLs, and decryption logic — no manual sync required.
#
# Usage:
#   ani-cli-api.sh search <query>          → tab-separated: id\ttitle
#   ani-cli-api.sh episodes <anime_id>     → one episode number per line
#   ani-cli-api.sh stream <anime_id> <ep>  → URL:/REFERER: prefixed lines
#
# Environment variables (optional):
#   ANI_CLI_MODE     sub|dub  (default: sub)
#   ANI_CLI_QUALITY  best|worst|720p|1080p  (default: best)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANI_CLI="$SCRIPT_DIR/ani-cli"

if [ ! -f "$ANI_CLI" ]; then
    printf "ERROR: ani-cli not found at %s\n" "$ANI_CLI" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Load all function definitions and variable setup from ani-cli.
#
# Strategy: extract everything BEFORE the argument-parsing while-loop
# so the script's interactive main flow (fzf menus, playback loop, etc.)
# never executes. This gives us:
#   - All functions: search_anime, episodes_list, get_episode_url, etc.
#   - All variables: agent, allanime_refr, allanime_api, allanime_key, etc.
#
# The awk pattern matches the exact line `while [ $# -gt 0 ]; do` which
# starts ani-cli's argument parser — stable across upstream versions.
# ---------------------------------------------------------------------------
eval "$(awk '/^while \[ \$# -gt 0 \]; do/{exit} {print}' "$ANI_CLI")" 2>/dev/null

# Force headless server defaults — override interactive settings
player_function="debug"
use_external_menu="0"

# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------
case "$1" in
    search)
        # search_anime expects spaces encoded as +
        shift
        query=$(printf "%s" "$*" | sed 's| |+|g')
        [ -z "$query" ] && { printf "ERROR: query is required\n" >&2; exit 1; }
        search_anime "$query"
        ;;

    episodes)
        [ -z "$2" ] && { printf "ERROR: anime_id is required\n" >&2; exit 1; }
        episodes_list "$2"
        ;;

    stream)
        [ -z "$2" ] && { printf "ERROR: anime_id is required\n" >&2; exit 1; }
        [ -z "$3" ] && { printf "ERROR: episode number is required\n" >&2; exit 1; }

        # Set the globals that get_episode_url reads
        id="$2"
        ep_no="$3"

        # get_episode_url needs ep_list for its "episode not released" check
        ep_list=$(episodes_list "$id")

        # This populates $episode (URL) and $refr_flag (--referrer=...)
        get_episode_url

        if [ -n "$episode" ]; then
            printf "URL:%s\n" "$episode"
            # Strip the --referrer= prefix from refr_flag to get the bare URL
            [ -n "$refr_flag" ] && printf "REFERER:%s\n" "${refr_flag#--referrer=}"
        else
            printf "ERROR: no stream URL resolved\n" >&2
            exit 1
        fi
        ;;

    *)
        printf "Usage: %s {search|episodes|stream} [args...]\n" "$(basename "$0")" >&2
        printf "\nCommands:\n"
        printf "  search <query>             Search anime by title\n"
        printf "  episodes <anime_id>        List available episodes\n"
        printf "  stream <anime_id> <ep_no>  Resolve stream URL\n"
        printf "\nEnvironment:\n"
        printf "  ANI_CLI_MODE=sub|dub       Translation type (default: sub)\n"
        printf "  ANI_CLI_QUALITY=best|720p  Stream quality (default: best)\n"
        exit 1
        ;;
esac
