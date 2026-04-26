"""Bug bounty program selector and Discord webhook poster.

Maintains a curated list of well-known bug bounty programs with metadata
such as platform, reward range, and focus areas.  On each call it picks one
at random and posts a rich Discord embed so your community always has a fresh
target to look at.
"""

import random
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

# ---------------------------------------------------------------------------
# Curated bug bounty programs
# ---------------------------------------------------------------------------
BUG_BOUNTY_PROGRAMS: list[dict] = [
    {
        "name": "HackerOne – GitHub",
        "platform": "HackerOne",
        "url": "https://hackerone.com/github",
        "max_reward": "$30,000",
        "scope": "github.com, GitHub APIs, GitHub Actions, GitHub Enterprise",
        "focus": "Authentication, Authorization, SSRF, RCE, IDOR",
        "description": (
            "GitHub's public bug bounty accepts reports on github.com and related services. "
            "Critical vulnerabilities (RCE, auth bypass) regularly earn five-figure payouts."
        ),
    },
    {
        "name": "HackerOne – Google",
        "platform": "HackerOne / Google",
        "url": "https://bughunters.google.com/",
        "max_reward": "$31,337+",
        "scope": "*.google.com, *.youtube.com, *.blogger.com, Android, Chrome",
        "focus": "XSS, SQL injection, CSRF, auth flaws, memory-corruption",
        "description": (
            "Google's Vulnerability Reward Program is one of the most prestigious in the industry. "
            "Chrome and Android bugs can earn exceptional rewards through separate programs."
        ),
    },
    {
        "name": "Bugcrowd – Tesla",
        "platform": "Bugcrowd",
        "url": "https://bugcrowd.com/tesla",
        "max_reward": "$15,000",
        "scope": "Tesla web services, mobile apps, and vehicle-related APIs",
        "focus": "Automotive APIs, account takeover, IDOR, injection",
        "description": (
            "Tesla's program covers its web infrastructure and app ecosystem. "
            "Vehicle-related attack surfaces make this a unique and interesting target."
        ),
    },
    {
        "name": "HackerOne – Shopify",
        "platform": "HackerOne",
        "url": "https://hackerone.com/shopify",
        "max_reward": "$50,000",
        "scope": "*.shopify.com, Shopify apps, admin API",
        "focus": "SSRF, XSS, IDOR, privilege escalation, injection",
        "description": (
            "Shopify consistently ranks among the highest-paying programs on HackerOne. "
            "Their multi-tenant SaaS platform offers rich attack surface for authorization bugs."
        ),
    },
    {
        "name": "HackerOne – Twitter / X",
        "platform": "HackerOne",
        "url": "https://hackerone.com/twitter",
        "max_reward": "$20,160",
        "scope": "twitter.com, api.twitter.com, mobile apps",
        "focus": "Account takeover, IDOR, OAuth flaws, privacy leaks",
        "description": (
            "Twitter's program covers the core platform, APIs, and mobile applications. "
            "OAuth and account-security bugs are particularly valued."
        ),
    },
    {
        "name": "HackerOne – Uber",
        "platform": "HackerOne",
        "url": "https://hackerone.com/uber",
        "max_reward": "$10,000",
        "scope": "*.uber.com, Uber apps, driver/rider APIs",
        "focus": "IDOR, SSRF, auth bypass, geo-data exposure",
        "description": (
            "Uber's program spans rider, driver, and Eats surfaces. "
            "Authorization and business-logic bugs that affect rider or driver safety are prioritised."
        ),
    },
    {
        "name": "Bugcrowd – Mastercard",
        "platform": "Bugcrowd",
        "url": "https://bugcrowd.com/mastercard",
        "max_reward": "$10,000",
        "scope": "mastercard.com, payment APIs, developer portal",
        "focus": "Payment flows, data exposure, injection, auth",
        "description": (
            "Mastercard's program focuses on its web properties and payment-processing APIs. "
            "Bugs that could impact payment integrity receive the highest rewards."
        ),
    },
    {
        "name": "HackerOne – Dropbox",
        "platform": "HackerOne",
        "url": "https://hackerone.com/dropbox",
        "max_reward": "$32,768",
        "scope": "dropbox.com, desktop client, mobile apps, APIs",
        "focus": "File-sharing abuse, IDOR, XSS, OAuth, privilege escalation",
        "description": (
            "Dropbox rewards bugs that affect user data confidentiality and integrity across "
            "its cloud storage platform and client applications."
        ),
    },
    {
        "name": "Intigriti – Nordea Bank",
        "platform": "Intigriti",
        "url": "https://app.intigriti.com/programs/nordea/nordea/detail",
        "max_reward": "€10,000",
        "scope": "nordea.com, online banking portal, mobile banking",
        "focus": "Authentication, session management, IDOR, data exposure",
        "description": (
            "Nordea is one of the largest financial groups in Northern Europe. "
            "Bugs affecting banking customers' accounts or funds earn the highest rewards."
        ),
    },
    {
        "name": "HackerOne – Slack",
        "platform": "HackerOne",
        "url": "https://hackerone.com/slack",
        "max_reward": "$30,000",
        "scope": "slack.com, Slack apps, Slack API",
        "focus": "SSRF, XSS, IDOR, workspace isolation, token leakage",
        "description": (
            "Slack's program covers its SaaS collaboration platform. "
            "Multi-tenancy boundary issues and workspace-isolation bugs are high-priority."
        ),
    },
    {
        "name": "HackerOne – Microsoft",
        "platform": "Microsoft MSRC",
        "url": "https://www.microsoft.com/en-us/msrc/bounty",
        "max_reward": "$250,000",
        "scope": "Azure, Microsoft 365, Windows, Edge, Xbox",
        "focus": "RCE, privilege escalation, memory corruption, Azure tenant isolation",
        "description": (
            "Microsoft runs multiple specialised bounty programs covering Azure, M365, Windows, and more. "
            "The Azure program offers some of the highest rewards in the industry."
        ),
    },
    {
        "name": "HackerOne – PayPal",
        "platform": "HackerOne",
        "url": "https://hackerone.com/paypal",
        "max_reward": "$10,000",
        "scope": "paypal.com, Venmo, Braintree, Honey",
        "focus": "Payment bypass, IDOR, XSS, CSRF, account takeover",
        "description": (
            "PayPal's wide scope includes Venmo, Braintree, and Honey. "
            "Payment-flow manipulation and account-takeover bugs are the most valued."
        ),
    },
    {
        "name": "Bugcrowd – Atlassian",
        "platform": "Bugcrowd",
        "url": "https://bugcrowd.com/atlassian",
        "max_reward": "$20,000",
        "scope": "Jira, Confluence, Bitbucket, Trello (cloud)",
        "focus": "SSRF, IDOR, stored XSS, project-isolation bypass",
        "description": (
            "Atlassian covers its flagship cloud products. "
            "Bugs that let one tenant access another tenant's data earn the highest payouts."
        ),
    },
    {
        "name": "HackerOne – Yahoo",
        "platform": "HackerOne",
        "url": "https://hackerone.com/yahoo",
        "max_reward": "$15,000",
        "scope": "yahoo.com, Tumblr, AOL, associated APIs",
        "focus": "XSS, authentication, OAuth, data exposure",
        "description": (
            "Yahoo's consolidated program covers its network of consumer web properties. "
            "Cross-product OAuth and single-sign-on flaws are particularly interesting targets."
        ),
    },
    {
        "name": "HackerOne – Airbnb",
        "platform": "HackerOne",
        "url": "https://hackerone.com/airbnb",
        "max_reward": "$10,000",
        "scope": "airbnb.com, mobile apps, host/guest APIs",
        "focus": "Booking manipulation, IDOR, SSRF, account takeover",
        "description": (
            "Airbnb's program covers its core marketplace platform. "
            "Bugs affecting financial transactions or host/guest privacy are highest priority."
        ),
    },
]

# Discord embed colour (gold / bounty)
_EMBED_COLOUR = 0xF1C40F


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pick_random_program(
    log_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """Return a randomly selected bug bounty program dict."""
    program = random.choice(BUG_BOUNTY_PROGRAMS)
    if log_callback:
        log_callback(f"Selected program: {program['name']}")
    return program


def post_to_discord(webhook_url: str, program: dict) -> None:
    """Post *program* as a Discord embed to *webhook_url*.

    Raises :class:`requests.HTTPError` on a non-2xx response.
    """
    description = program.get("description", "No description available.")
    if len(description) > 4096:
        description = description[:4093] + "…"

    embed: dict = {
        "title": program["name"][:256],
        "url": program.get("url") or None,
        "description": description,
        "color": _EMBED_COLOUR,
        "author": {"name": "🏆 Bug Bounty Program of the Day"},
        "fields": [
            {"name": "Platform",    "value": program.get("platform", "Unknown"),    "inline": True},
            {"name": "Max Reward",  "value": program.get("max_reward", "Varies"),   "inline": True},
            {"name": "Scope",       "value": program.get("scope", "See program"),   "inline": False},
            {"name": "Focus Areas", "value": program.get("focus", "General"),       "inline": False},
        ],
        "footer": {
            "text": f"Posted at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        },
    }

    response = requests.post(
        webhook_url,
        json={"embeds": [embed]},
        timeout=15,
    )
    response.raise_for_status()
