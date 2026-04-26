"""Hacking music fetcher and Discord webhook poster.

Pulls music entries from hacking- and cyberpunk-themed subreddits and music
blogs, picks one at random, and sends a rich embed to a Discord webhook URL.
"""

import html
import re
import random
from datetime import datetime, timezone
from typing import Callable, Optional

import feedparser
import requests

# ---------------------------------------------------------------------------
# RSS feed sources
# ---------------------------------------------------------------------------
MUSIC_FEEDS = [
    {"url": "https://www.reddit.com/r/HackingMusic/.rss",              "name": "Reddit /r/HackingMusic"},
    {"url": "https://www.reddit.com/r/outrun/.rss",                    "name": "Reddit /r/outrun"},
    {"url": "https://www.reddit.com/r/cyberpunk/.rss",                 "name": "Reddit /r/cyberpunk"},
    {"url": "https://www.reddit.com/r/retrowave/.rss",                 "name": "Reddit /r/retrowave"},
    {"url": "https://www.reddit.com/r/DarkAmbient/.rss",               "name": "Reddit /r/DarkAmbient"},
    {"url": "https://www.reddit.com/r/industrialmusic/.rss",           "name": "Reddit /r/industrialmusic"},
]

# Max entries to collect per feed before random selection
_MAX_PER_FEED = 20

# Discord embed colour (neon purple)
_EMBED_COLOUR = 0x9B59B6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_html(text: str) -> str:
    """Strip HTML tags, decode entities, and collapse whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_random_track(
    log_callback: Optional[Callable[[str], None]] = None,
) -> Optional[dict]:
    """Fetch a random music entry from the configured feeds.

    Returns a dict with keys ``title``, ``link``, ``summary``, ``source``,
    and ``published``, or *None* if no entries could be retrieved.
    """
    entries: list[dict] = []

    for feed_info in MUSIC_FEEDS:
        try:
            if log_callback:
                log_callback(f"Fetching from {feed_info['name']} …")
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:_MAX_PER_FEED]:
                raw_summary = entry.get("summary", entry.get("description", ""))
                summary = _clean_html(raw_summary)
                if len(summary) > 500:
                    summary = summary[:497] + "…"
                entries.append(
                    {
                        "title": _clean_html(entry.get("title", "Unknown Title")),
                        "link": entry.get("link", ""),
                        "summary": summary,
                        "source": feed_info["name"],
                        "published": entry.get("published", ""),
                    }
                )
        except Exception as exc:  # noqa: BLE001 – feedparser/network errors
            if log_callback:
                log_callback(f"Warning: could not fetch {feed_info['name']}: {exc}")

    if not entries:
        return None

    return random.choice(entries)


def post_to_discord(webhook_url: str, track: dict) -> None:
    """Post *track* as a Discord embed to *webhook_url*.

    Raises :class:`requests.HTTPError` on a non-2xx response.
    """
    description = track.get("summary", "No description available.")
    if len(description) > 4096:
        description = description[:4093] + "…"

    embed: dict = {
        "title": track["title"][:256],
        "url": track["link"] or None,
        "description": description,
        "color": _EMBED_COLOUR,
        "author": {"name": "🎵 Hacking Music of the Day"},
        "fields": [
            {
                "name": "Source",
                "value": track.get("source", "Unknown"),
                "inline": True,
            }
        ],
        "footer": {
            "text": f"Posted at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        },
    }

    if track.get("published"):
        embed["fields"].append(
            {"name": "Published", "value": track["published"], "inline": True}
        )

    response = requests.post(
        webhook_url,
        json={"embeds": [embed]},
        timeout=15,
    )
    response.raise_for_status()
