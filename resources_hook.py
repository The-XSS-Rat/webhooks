"""Cybersecurity resources fetcher and Discord webhook poster.

Pulls entries from well-known security news and resource RSS feeds, picks one
at random, and sends a rich embed to a Discord webhook URL.
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
RESOURCE_FEEDS = [
    {"url": "https://krebsonsecurity.com/feed/",                        "name": "Krebs on Security"},
    {"url": "https://www.darkreading.com/rss.xml",                      "name": "Dark Reading"},
    {"url": "https://isc.sans.edu/rssfeed_full.xml",                    "name": "SANS ISC"},
    {"url": "https://feeds.feedburner.com/TheHackersNews",              "name": "The Hacker News"},
    {"url": "https://threatpost.com/feed/",                             "name": "Threatpost"},
    {"url": "https://www.bleepingcomputer.com/feed/",                   "name": "Bleeping Computer"},
    {"url": "https://www.reddit.com/r/netsec/.rss",                     "name": "Reddit /r/netsec"},
    {"url": "https://www.reddit.com/r/hacking/.rss",                    "name": "Reddit /r/hacking"},
]

# Max entries to collect per feed before random selection
_MAX_PER_FEED = 20

# Discord embed colour (deep blue)
_EMBED_COLOUR = 0x0F3460


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

def fetch_random_resource(
    log_callback: Optional[Callable[[str], None]] = None,
) -> Optional[dict]:
    """Fetch a random cybersecurity resource entry from the configured feeds.

    Returns a dict with keys ``title``, ``link``, ``summary``, ``source``,
    and ``published``, or *None* if no entries could be retrieved.
    """
    entries: list[dict] = []

    for feed_info in RESOURCE_FEEDS:
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
        except (feedparser.CharacterEncodingOverride, OSError, ValueError) as exc:
            if log_callback:
                log_callback(f"Warning: could not fetch {feed_info['name']}: {exc}")
        except Exception as exc:  # noqa: BLE001 – unknown feedparser/network errors
            if log_callback:
                log_callback(f"Warning: could not fetch {feed_info['name']}: {exc}")

    if not entries:
        return None

    return random.choice(entries)


def post_to_discord(webhook_url: str, resource: dict) -> None:
    """Post *resource* as a Discord embed to *webhook_url*.

    Raises :class:`requests.HTTPError` on a non-2xx response.
    """
    description = resource.get("summary", "No description available.")
    if len(description) > 4096:
        description = description[:4093] + "…"

    embed: dict = {
        "title": resource["title"][:256],
        "url": resource["link"] or None,
        "description": description,
        "color": _EMBED_COLOUR,
        "author": {"name": "📚 Cybersecurity Resource of the Day"},
        "fields": [
            {
                "name": "Source",
                "value": resource.get("source", "Unknown"),
                "inline": True,
            }
        ],
        "footer": {
            "text": f"Posted at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        },
    }

    if resource.get("published"):
        embed["fields"].append(
            {"name": "Published", "value": resource["published"], "inline": True}
        )

    response = requests.post(
        webhook_url,
        json={"embeds": [embed]},
        timeout=15,
    )
    response.raise_for_status()
