"""Google dork generator and Discord webhook poster.

Maintains a categorised library of Google dork templates, expands them with
random realistic values, and posts a rich Discord embed so your community
discovers new reconnaissance techniques every day.
"""

import random
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

# ---------------------------------------------------------------------------
# Dork template library
# Each entry: category, template (may contain placeholders), description,
# use_case, and optional example (pre-expanded string shown in the embed).
# ---------------------------------------------------------------------------

_DORK_LIBRARY: list[dict] = [
    # ── Exposed login portals ──────────────────────────────────────────────
    {
        "category": "Exposed Login Portals",
        "template": 'intitle:"Login" inurl:admin site:{tld}',
        "description": "Finds admin login pages across a top-level domain.",
        "use_case": "Identify poorly secured admin panels exposed to the internet.",
        "tip": "Combine with site:target.com to narrow to a specific organisation.",
    },
    {
        "category": "Exposed Login Portals",
        "template": 'inurl:"/wp-login.php" site:{tld}',
        "description": "Locates WordPress login pages.",
        "use_case": "Enumerate WordPress installations for bruteforce or credential-stuffing tests.",
        "tip": "Add inurl:xmlrpc.php to find XML-RPC endpoints that may be bruteforceable.",
    },
    {
        "category": "Exposed Login Portals",
        "template": 'intitle:"Plesk" inurl:8443 site:{tld}',
        "description": "Finds exposed Plesk hosting-control-panel login pages.",
        "use_case": "Discover unpatched or misconfigured Plesk instances.",
        "tip": "Old Plesk versions have known CVEs – check Shodan for the version banner.",
    },
    # ── Sensitive files ────────────────────────────────────────────────────
    {
        "category": "Sensitive Files",
        "template": 'filetype:env "DB_PASSWORD" site:{tld}',
        "description": "Searches for publicly accessible .env files containing DB credentials.",
        "use_case": "Find accidentally committed or web-accessible environment configuration.",
        "tip": "Try variations: filetype:env \"SECRET_KEY\", filetype:env \"AWS_SECRET\".",
    },
    {
        "category": "Sensitive Files",
        "template": 'filetype:sql "INSERT INTO" site:{tld}',
        "description": "Finds exposed SQL database dump files.",
        "use_case": "Discover database backups left in public web directories.",
        "tip": "Common backup names: dump.sql, backup.sql, db.sql, database.sql.",
    },
    {
        "category": "Sensitive Files",
        "template": 'filetype:log inurl:"/logs/" site:{tld}',
        "description": "Locates web-accessible application log files.",
        "use_case": "Log files can leak usernames, session tokens, internal IPs, and stack traces.",
        "tip": "Look for error.log, access.log, debug.log, application.log.",
    },
    {
        "category": "Sensitive Files",
        "template": 'filetype:xml inurl:"sitemap" site:{tld}',
        "description": "Finds sitemap XML files – useful for mapping all endpoints.",
        "use_case": "Enumerate hidden or unlisted pages not reachable from the homepage.",
        "tip": "Check /sitemap_index.xml for references to further sitemaps.",
    },
    {
        "category": "Sensitive Files",
        "template": 'filetype:bak OR filetype:old OR filetype:backup site:{tld}',
        "description": "Searches for backup copies of source files.",
        "use_case": "Backup files often contain source code, credentials, or older vulnerable code.",
        "tip": "Also try filetype:swp (vim swap files) and filetype:orig.",
    },
    # ── Configuration & secrets ────────────────────────────────────────────
    {
        "category": "Configuration & Secrets",
        "template": 'inurl:".git" intitle:"Index of" site:{tld}',
        "description": "Finds exposed .git directories on web servers.",
        "use_case": "A browsable .git directory lets you reconstruct the entire source code.",
        "tip": "Use git-dumper or GitTools to download and reconstruct the repo.",
    },
    {
        "category": "Configuration & Secrets",
        "template": '"AWS_ACCESS_KEY_ID" filetype:txt OR filetype:env OR filetype:cfg',
        "description": "Searches publicly indexed files for AWS access keys.",
        "use_case": "Exposed AWS keys can give full cloud-account access.",
        "tip": "Report immediately – AWS has an automated abuse-detection programme.",
    },
    {
        "category": "Configuration & Secrets",
        "template": 'inurl:"config.php" filetype:php site:{tld}',
        "description": "Finds PHP config files that may contain credentials.",
        "use_case": "config.php often holds database credentials and API keys.",
        "tip": "Look for wp-config.php, config.inc.php, configuration.php.",
    },
    {
        "category": "Configuration & Secrets",
        "template": 'inurl:"/.ssh/id_rsa" site:{tld}',
        "description": "Searches for accidentally exposed SSH private keys.",
        "use_case": "An exposed private key grants full SSH access to the associated server.",
        "tip": "Also look for id_dsa, id_ecdsa, id_ed25519.",
    },
    # ── Open directories ───────────────────────────────────────────────────
    {
        "category": "Open Directories",
        "template": 'intitle:"Index of /" inurl:{path} site:{tld}',
        "description": "Finds open directory listings under a specific path.",
        "use_case": "Open directories expose files, backups, and internal assets.",
        "tip": "Common paths: /upload, /backup, /files, /data, /documents.",
    },
    {
        "category": "Open Directories",
        "template": '"Parent Directory" inurl:/uploads/ site:{tld}',
        "description": "Locates open upload directories.",
        "use_case": "Unprotected upload dirs may contain user-submitted files or shell uploads.",
        "tip": "Look for .php, .jsp, .aspx files inside – could indicate file-upload to RCE.",
    },
    # ── Vulnerable parameters ──────────────────────────────────────────────
    {
        "category": "Vulnerable Parameters",
        "template": 'inurl:"?id=" site:{tld}',
        "description": "Finds URLs with numeric id parameters – classic SQL injection target.",
        "use_case": "Numeric GET parameters in database-backed apps are common injection points.",
        "tip": "Test with sqlmap: sqlmap -u \"http://target.com/page?id=1\" --dbs",
    },
    {
        "category": "Vulnerable Parameters",
        "template": 'inurl:"?redirect=" OR inurl:"?url=" OR inurl:"?next=" site:{tld}',
        "description": "Finds redirect/forwarding parameters – open redirect targets.",
        "use_case": "Open redirects aid phishing and can chain into account-takeover bugs.",
        "tip": "Test with ?redirect=https://evil.com and watch for 301/302 to external host.",
    },
    {
        "category": "Vulnerable Parameters",
        "template": 'inurl:"?file=" OR inurl:"?page=" OR inurl:"?include=" site:{tld}',
        "description": "Looks for file-inclusion parameters – potential LFI/RFI target.",
        "use_case": "Local File Inclusion can expose /etc/passwd, config files, and more.",
        "tip": "Start with ?file=../../../etc/passwd or use dotdotpwn for automated testing.",
    },
    # ── Cloud & DevOps exposure ────────────────────────────────────────────
    {
        "category": "Cloud & DevOps Exposure",
        "template": 'site:s3.amazonaws.com "{company}"',
        "description": "Finds S3 buckets that mention a company name.",
        "use_case": "Misconfigured public S3 buckets can expose PII, backups, or source code.",
        "tip": "Use AWSBucketDump or truffleHog to enumerate and check bucket contents.",
    },
    {
        "category": "Cloud & DevOps Exposure",
        "template": 'site:pastebin.com "{company}" password OR secret OR key',
        "description": "Searches Pastebin for leaked credentials related to a target.",
        "use_case": "Employees sometimes accidentally paste credentials in public pastes.",
        "tip": "Also try site:github.com, site:gist.github.com with the same keywords.",
    },
    {
        "category": "Cloud & DevOps Exposure",
        "template": 'inurl:".jenkins" OR inurl:"/jenkins/" intitle:"Dashboard" site:{tld}',
        "description": "Finds exposed Jenkins CI/CD dashboards.",
        "use_case": "Open Jenkins instances can allow code execution through build pipelines.",
        "tip": "Check /script endpoint for Groovy script console – common RCE vector.",
    },
    # ── Error messages & stack traces ──────────────────────────────────────
    {
        "category": "Error Messages & Stack Traces",
        "template": 'intext:"Fatal error" intext:"on line" site:{tld}',
        "description": "Finds pages leaking PHP fatal error messages with file paths.",
        "use_case": "Stack traces reveal internal file paths, class names, and framework versions.",
        "tip": "Path disclosure combined with LFI bugs is a potent attack chain.",
    },
    {
        "category": "Error Messages & Stack Traces",
        "template": 'intext:"ORA-01756" OR intext:"mysql_fetch" site:{tld}',
        "description": "Finds pages with visible Oracle or MySQL error output.",
        "use_case": "Database errors often indicate unsanitised input and SQL injection.",
        "tip": "Confirm injection manually then escalate with sqlmap --level=5 --risk=3.",
    },
    # ── IoT & SCADA ────────────────────────────────────────────────────────
    {
        "category": "IoT & SCADA",
        "template": 'intitle:"SCADA" inurl:login site:{tld}',
        "description": "Finds internet-exposed SCADA system login pages.",
        "use_case": "Critical infrastructure SCADA panels should never be internet-facing.",
        "tip": "Always report via responsible disclosure – do NOT attempt unauthorised access.",
    },
    {
        "category": "IoT & SCADA",
        "template": 'intitle:"Webcam" inurl:"/view.shtml"',
        "description": "Finds publicly accessible webcam streams.",
        "use_case": "Many IP cameras are internet-exposed with default or no credentials.",
        "tip": "Shodan.io is more efficient for IoT recon – use as a complement to dorking.",
    },
]

# Realistic placeholder values used when expanding templates
_TLDS = ["com", "net", "org", "io", "co.uk", "de", "fr", "nl", "gov", "edu"]
_PATHS = ["/upload", "/backup", "/files", "/data", "/documents", "/assets", "/tmp", "/old"]
_COMPANIES = ["acme", "techcorp", "enterprise", "globalbank", "shopco"]

# Discord embed colour (bright cyan / hacker green)
_EMBED_COLOUR = 0x00FFFF


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expand_template(template: str) -> str:
    """Replace common placeholders with random realistic values."""
    template = template.replace("{tld}", random.choice(_TLDS))
    template = template.replace("{path}", random.choice(_PATHS))
    template = template.replace("{company}", random.choice(_COMPANIES))
    return template


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_random_dork(
    log_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """Return a randomly selected and expanded dork dict.

    Keys: ``category``, ``dork``, ``template``, ``description``,
    ``use_case``, ``tip``.
    """
    entry = random.choice(_DORK_LIBRARY)
    dork = _expand_template(entry["template"])
    if log_callback:
        log_callback(f"Generated dork [{entry['category']}]: {dork}")
    return {
        "category": entry["category"],
        "dork": dork,
        "template": entry["template"],
        "description": entry["description"],
        "use_case": entry["use_case"],
        "tip": entry.get("tip", ""),
    }


def post_to_discord(webhook_url: str, dork: dict) -> None:
    """Post *dork* as a Discord embed to *webhook_url*.

    Raises :class:`requests.HTTPError` on a non-2xx response.
    """
    embed: dict = {
        "title": f"🔍 {dork['category']}",
        "description": f"```\n{dork['dork']}\n```\n{dork['description']}",
        "color": _EMBED_COLOUR,
        "author": {"name": "🕵️ Google Dork of the Day"},
        "fields": [
            {"name": "Use Case", "value": dork.get("use_case", "General recon"), "inline": False},
            {"name": "💡 Pro Tip", "value": dork.get("tip", "—"),               "inline": False},
            {"name": "Template",  "value": f"`{dork.get('template', dork['dork'])}`", "inline": False},
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
