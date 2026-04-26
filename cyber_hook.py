"""Cybersecurity writeup fetcher and Discord webhook poster.

Pulls entries from several well-known security RSS feeds, picks one at
random, and sends a rich embed to a Discord webhook URL.
"""

import html
import re
import random
from datetime import datetime
from typing import Callable, Optional

import feedparser
import requests

# ---------------------------------------------------------------------------
# RSS feed sources
# ---------------------------------------------------------------------------
WRITEUP_FEEDS = [
    {"url": "https://ctftime.org/writeups/rss/",                    "name": "CTFTime Writeups"},
    {"url": "https://portswigger.net/blog/rss",                     "name": "PortSwigger Blog"},
    {"url": "https://research.nccgroup.com/feed/",                  "name": "NCC Group Research"},
    {"url": "https://googleprojectzero.blogspot.com/feeds/posts/default",
                                                                    "name": "Google Project Zero"},
    {"url": "https://www.exploit-db.com/rss.xml",                   "name": "Exploit-DB"},
    {"url": "https://www.hackerone.com/blog.rss",                   "name": "HackerOne Blog"},
    {"url": "https://security.googleblog.com/feeds/posts/default",  "name": "Google Security Blog"},
]

# Max entries to collect per feed before random selection
_MAX_PER_FEED = 20

# Discord embed colour (matrix green)
_EMBED_COLOUR = 0x00FF41


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

def fetch_random_writeup(
    log_callback: Optional[Callable[[str], None]] = None,
) -> Optional[dict]:
    """Fetch a random cybersecurity writeup entry from the configured feeds.

    Returns a dict with keys ``title``, ``link``, ``summary``, ``source``,
    and ``published``, or *None* if no entries could be retrieved.
    """
    entries: list[dict] = []

    for feed_info in WRITEUP_FEEDS:
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
        except Exception as exc:  # noqa: BLE001
            if log_callback:
                log_callback(f"Warning: could not fetch {feed_info['name']}: {exc}")

    if not entries:
        return None

    return random.choice(entries)


def post_to_discord(webhook_url: str, writeup: dict) -> None:
    """Post *writeup* as a Discord embed to *webhook_url*.

    Raises :class:`requests.HTTPError` on a non-2xx response.
    """
    description = writeup.get("summary", "No description available.")
    if len(description) > 4096:
        description = description[:4093] + "…"

    embed: dict = {
        "title": writeup["title"][:256],
        "url": writeup["link"] or None,
        "description": description,
        "color": _EMBED_COLOUR,
        "author": {"name": "🔐 Cybersecurity Writeup of the Day"},
        "fields": [
            {
                "name": "Source",
                "value": writeup.get("source", "Unknown"),
                "inline": True,
            }
        ],
        "footer": {
            "text": f"Posted at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        },
    }

    if writeup.get("published"):
        embed["fields"].append(
            {"name": "Published", "value": writeup["published"], "inline": True}
        )

    response = requests.post(
        webhook_url,
        json={"embeds": [embed]},
        timeout=15,
    )
    response.raise_for_status()
