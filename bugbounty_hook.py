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
        "name": "HackerOne – Google VRP",
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
        "name": "Microsoft MSRC",
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
    # ── Extended programs ───────────────────────────────────────────────────
    {
        "name": "HackerOne – Meta (Facebook)",
        "platform": "HackerOne",
        "url": "https://www.facebook.com/whitehat",
        "max_reward": "$100,000+",
        "scope": "facebook.com, instagram.com, whatsapp.com, oculus.com, meta.com",
        "focus": "Account takeover, IDOR, OAuth, privacy data access, RCE",
        "description": (
            "Meta's bug bounty is one of the oldest and most generous in the industry. "
            "Bugs that affect the privacy or account security of billions of users earn top rewards. "
            "WhatsApp and Oculus/VR surfaces are less tested and offer good opportunities."
        ),
    },
    {
        "name": "Apple Security Bounty",
        "platform": "Apple (private invite / public)",
        "url": "https://security.apple.com/bounty/",
        "max_reward": "$1,000,000",
        "scope": "iCloud, Apple ID, iOS/macOS/tvOS kernel, Safari, App Store",
        "focus": "Kernel exploits, iCloud auth bypass, Safari RCE, zero-click attacks",
        "description": (
            "Apple's security bounty offers the highest published maximum reward in the industry – "
            "up to $1M for a zero-click kernel RCE with persistence on iOS. "
            "Even lower-severity iCloud and Apple ID bugs pay five figures."
        ),
    },
    {
        "name": "Samsung Mobile Security Rewards",
        "platform": "Samsung (direct)",
        "url": "https://security.samsungmobile.com/securityRewardProgram.smsb",
        "max_reward": "$1,000,000",
        "scope": "Samsung Galaxy devices, One UI, Samsung Knox, SmartThings",
        "focus": "RCE, privilege escalation, Knox bypass, arbitrary data access",
        "description": (
            "Samsung's mobile security program covers its Android-based devices and Knox security platform. "
            "Critical device takeover and Knox-bypass vulnerabilities are eligible for seven-figure rewards."
        ),
    },
    {
        "name": "HackerOne – GitLab",
        "platform": "HackerOne",
        "url": "https://hackerone.com/gitlab",
        "max_reward": "$20,000",
        "scope": "gitlab.com, GitLab CE/EE, CI/CD pipelines, Kubernetes integration",
        "focus": "SSRF, IDOR, stored XSS, pipeline injection, auth bypass",
        "description": (
            "GitLab's fully public program covers its self-hosted and SaaS offerings. "
            "Pipeline-injection and project-isolation bugs are particularly rewarded. "
            "GitLab also credits researchers publicly in their Hall of Fame."
        ),
    },
    {
        "name": "HackerOne – Mozilla",
        "platform": "HackerOne",
        "url": "https://hackerone.com/mozilla",
        "max_reward": "$10,000",
        "scope": "Firefox, Thunderbird, Mozilla web services, MDN, Pocket",
        "focus": "Memory safety, sandbox escape, XSS, auth flaws, policy bypass",
        "description": (
            "Mozilla's program has been running since 2004 and covers Firefox's complex attack surface. "
            "Sandbox-escape and memory-safety bugs in Firefox earn the highest payouts."
        ),
    },
    {
        "name": "HackerOne – Spotify",
        "platform": "HackerOne",
        "url": "https://hackerone.com/spotify",
        "max_reward": "$15,000",
        "scope": "spotify.com, Spotify API, mobile apps, Spotify for Developers",
        "focus": "Auth bypass, account takeover, IDOR, API abuse, XSS",
        "description": (
            "Spotify's program covers its streaming platform and developer-facing APIs. "
            "Bugs that expose private listening data or allow account takeover are highest priority."
        ),
    },
    {
        "name": "HackerOne – LinkedIn",
        "platform": "HackerOne",
        "url": "https://hackerone.com/linkedin",
        "max_reward": "$17,000",
        "scope": "linkedin.com, LinkedIn Learning, LinkedIn APIs, Recruiter",
        "focus": "IDOR, XSS, data scraping, OAuth flaws, account takeover",
        "description": (
            "LinkedIn's program covers its professional-networking platform. "
            "Privacy-impacting bugs – including mass data access and account takeover – are top priority."
        ),
    },
    {
        "name": "HackerOne – Reddit",
        "platform": "HackerOne",
        "url": "https://hackerone.com/reddit",
        "max_reward": "$10,000",
        "scope": "reddit.com, old.reddit.com, Reddit API, mobile apps",
        "focus": "IDOR, XSS, CSRF, mod-privilege escalation, auth flaws",
        "description": (
            "Reddit's program covers the community platform and its public API. "
            "Bugs that let users access or modify content or accounts they shouldn't are prioritised."
        ),
    },
    {
        "name": "HackerOne – Discord",
        "platform": "HackerOne",
        "url": "https://hackerone.com/discord",
        "max_reward": "$10,000",
        "scope": "discord.com, Discord API, desktop and mobile clients",
        "focus": "RCE via Electron, IDOR, XSS, server isolation, token leakage",
        "description": (
            "Discord's Electron-based desktop client is an interesting target for RCE via XSS. "
            "Server-isolation and account-security bugs are also high priority."
        ),
    },
    {
        "name": "HackerOne – Cloudflare",
        "platform": "HackerOne",
        "url": "https://hackerone.com/cloudflare",
        "max_reward": "$3,000",
        "scope": "cloudflare.com, Cloudflare dashboard, Workers, Pages, R2",
        "focus": "WAF bypass, tenant isolation, cache poisoning, Workers sandbox escape",
        "description": (
            "Cloudflare's program is interesting because edge and serverless attack surfaces are novel. "
            "Workers sandbox escapes and WAF-bypass techniques earn the highest rewards."
        ),
    },
    {
        "name": "HackerOne – Zoom",
        "platform": "HackerOne",
        "url": "https://hackerone.com/zoom",
        "max_reward": "$50,000",
        "scope": "zoom.us, Zoom desktop/mobile client, Zoom Phone, Zoom Rooms",
        "focus": "RCE via meeting links, IDOR, auth bypass, meeting privacy",
        "description": (
            "Zoom's program covers its video-conferencing platform and clients. "
            "Bugs enabling zero-click RCE or unauthorised access to meetings can earn $50K+."
        ),
    },
    {
        "name": "HackerOne – Stripe",
        "platform": "HackerOne",
        "url": "https://hackerone.com/stripe",
        "max_reward": "$25,000",
        "scope": "stripe.com, Stripe API, Stripe Checkout, Radar, Connect",
        "focus": "Payment bypass, IDOR, race conditions, API key exposure, auth flaws",
        "description": (
            "Stripe's payment infrastructure processes hundreds of billions annually. "
            "Bugs that could allow unauthorised payment capture or account pivoting earn the highest rewards."
        ),
    },
    {
        "name": "HackerOne – Coinbase",
        "platform": "HackerOne",
        "url": "https://hackerone.com/coinbase",
        "max_reward": "$50,000",
        "scope": "coinbase.com, Coinbase Pro, Coinbase Wallet, Coinbase APIs",
        "focus": "Crypto theft, account takeover, IDOR, trading manipulation, key exposure",
        "description": (
            "Coinbase is one of the world's largest crypto exchanges. "
            "Any bug that could allow unauthorised access to customer funds is critical-priority."
        ),
    },
    {
        "name": "HackerOne – Twitch",
        "platform": "HackerOne",
        "url": "https://hackerone.com/twitch",
        "max_reward": "$25,000",
        "scope": "twitch.tv, Twitch API, Extensions platform, mobile apps",
        "focus": "IDOR, XSS, streamer account takeover, extension sandbox escape",
        "description": (
            "Twitch's program covers its live-streaming platform. "
            "Bugs affecting streamer subscriptions, revenue, or viewer privacy earn the highest rewards."
        ),
    },
    {
        "name": "Bugcrowd – OpenAI",
        "platform": "Bugcrowd",
        "url": "https://bugcrowd.com/openai",
        "max_reward": "$20,000",
        "scope": "openai.com, ChatGPT, OpenAI API, DALL-E, Sora",
        "focus": "Prompt injection, data leakage, account takeover, API abuse, model extraction",
        "description": (
            "OpenAI's bug bounty covers its web properties and AI APIs. "
            "Novel attack classes like prompt injection, jailbreaking leading to data exfiltration, "
            "and plugin sandbox escapes are of particular interest."
        ),
    },
    {
        "name": "HackerOne – Snapchat",
        "platform": "HackerOne",
        "url": "https://hackerone.com/snapchat",
        "max_reward": "$15,000",
        "scope": "snapchat.com, Snap mobile apps, Snapchat API, Bitmoji",
        "focus": "Media leakage, account takeover, IDOR, ephemeral content access",
        "description": (
            "Snapchat's program focuses on privacy and media-confidentiality bugs. "
            "Any vulnerability that allows accessing ephemeral content without permission is critical."
        ),
    },
    {
        "name": "Bugcrowd – Twilio",
        "platform": "Bugcrowd",
        "url": "https://bugcrowd.com/twilio",
        "max_reward": "$10,000",
        "scope": "twilio.com, Authy, SendGrid, Segment, Twilio APIs",
        "focus": "Account takeover, SMS/OTP bypass, API key leakage, SSRF",
        "description": (
            "Twilio powers communications for thousands of apps. "
            "OTP-bypass, account-takeover, and API credential exposure bugs are highest priority."
        ),
    },
    {
        "name": "HackerOne – Adobe",
        "platform": "HackerOne",
        "url": "https://hackerone.com/adobe",
        "max_reward": "$25,000",
        "scope": "adobe.com, Creative Cloud, Acrobat, Adobe Sign, Experience Manager",
        "focus": "RCE via PDF/image parsing, SSRF, XSS, auth bypass",
        "description": (
            "Adobe's program spans its Creative Cloud suite and enterprise products. "
            "Parser bugs in PDF, image, and font handling are classic high-value targets."
        ),
    },
    {
        "name": "HackerOne – Salesforce",
        "platform": "HackerOne",
        "url": "https://hackerone.com/salesforce",
        "max_reward": "$25,000",
        "scope": "salesforce.com, Force.com, Heroku, MuleSoft, Slack (Enterprise)",
        "focus": "Apex code injection, SOQL injection, IDOR, tenant isolation, SSRF",
        "description": (
            "Salesforce's vast CRM platform introduces unique attack vectors like Apex and SOQL injection. "
            "Tenant-isolation bugs across its multi-cloud ecosystem are especially rewarded."
        ),
    },
    {
        "name": "HackerOne – Automattic (WordPress.com)",
        "platform": "HackerOne",
        "url": "https://hackerone.com/automattic",
        "max_reward": "$10,875",
        "scope": "wordpress.com, WooCommerce, Jetpack, Tumblr, Akismet",
        "focus": "XSS, SSRF, IDOR, plugin vulnerabilities, multisite escapes",
        "description": (
            "Automattic powers WordPress.com and WooCommerce. "
            "Bugs in Jetpack and WooCommerce plugins affect millions of self-hosted sites too, "
            "making cross-site XSS and privilege escalation highly impactful."
        ),
    },
    {
        "name": "HackerOne – Proton",
        "platform": "HackerOne",
        "url": "https://hackerone.com/protonmail",
        "max_reward": "$10,000",
        "scope": "proton.me, ProtonMail, ProtonVPN, ProtonCalendar, ProtonDrive",
        "focus": "Encryption bypass, XSS, account takeover, VPN tunnel leaks",
        "description": (
            "Proton's end-to-end-encrypted services are a high-value privacy target. "
            "Any bug that undermines the encryption model or leaks private data is critical."
        ),
    },
    {
        "name": "HackerOne – Okta",
        "platform": "HackerOne",
        "url": "https://hackerone.com/okta",
        "max_reward": "$25,000",
        "scope": "okta.com, Auth0, Okta SSO, Okta Verify app",
        "focus": "SSO bypass, MFA bypass, account takeover, tenant isolation, OIDC/SAML flaws",
        "description": (
            "Okta is the identity layer for thousands of enterprise apps. "
            "SSO-bypass and MFA-defeat bugs here have the potential to compromise countless downstream tenants."
        ),
    },
    {
        "name": "Bugcrowd – Palo Alto Networks",
        "platform": "Bugcrowd",
        "url": "https://bugcrowd.com/paloaltonetworks",
        "max_reward": "$15,000",
        "scope": "PAN-OS, Prisma Cloud, Cortex XDR, GlobalProtect VPN",
        "focus": "RCE via firewall management, VPN bypass, auth bypass, CVE hunting",
        "description": (
            "Palo Alto's security products are deployed at enterprises worldwide. "
            "RCE on PAN-OS or GlobalProtect VPN would be a critical corporate network compromise."
        ),
    },
    {
        "name": "HackerOne – Elastic",
        "platform": "HackerOne",
        "url": "https://hackerone.com/elastic",
        "max_reward": "$20,000",
        "scope": "elastic.co, Elasticsearch, Kibana, Logstash, Elastic Cloud",
        "focus": "Unauthenticated data access, injection, SSRF, privilege escalation",
        "description": (
            "Elastic's search-and-observability stack stores sensitive log data for enterprises. "
            "Unauthenticated Elasticsearch cluster access is a common and high-impact finding."
        ),
    },
    {
        "name": "HackerOne – HackerOne",
        "platform": "HackerOne",
        "url": "https://hackerone.com/security",
        "max_reward": "$20,000",
        "scope": "hackerone.com, HackerOne API, programme management features",
        "focus": "IDOR across programme boundaries, XSS, auth, data leakage",
        "description": (
            "HackerOne runs a bug bounty on its own platform – a meta target! "
            "Cross-programme data leakage and researcher/company boundary violations are the most impactful bugs."
        ),
    },
    {
        "name": "HackerOne – U.S. Department of Defense",
        "platform": "HackerOne (Hack the Pentagon)",
        "url": "https://hackerone.com/deptofdefense",
        "max_reward": "$3,000",
        "scope": "*.mil, publicly accessible DoD web properties",
        "focus": "IDOR, auth bypass, data exposure, injection, misconfigured services",
        "description": (
            "The DoD's Vulnerability Disclosure Program is the largest in the world by scope. "
            "Thousands of publicly accessible .mil properties are in scope and many go largely untested."
        ),
    },
    {
        "name": "HackerOne – Grab",
        "platform": "HackerOne",
        "url": "https://hackerone.com/grab",
        "max_reward": "$10,000",
        "scope": "grab.com, GrabFood, GrabPay, GrabCar APIs, mobile apps",
        "focus": "Payment fraud, IDOR, ride-booking manipulation, account takeover",
        "description": (
            "Grab is Southeast Asia's leading super-app. "
            "Payment and booking manipulation bugs are the most impactful given the financial stakes."
        ),
    },
    {
        "name": "HackerOne – Kraken",
        "platform": "HackerOne",
        "url": "https://hackerone.com/kraken",
        "max_reward": "$10,000",
        "scope": "kraken.com, Kraken Pro, Kraken API, mobile apps",
        "focus": "Crypto theft, trading manipulation, account takeover, API key exposure",
        "description": (
            "Kraken is one of the oldest and most trusted crypto exchanges. "
            "Any bug that could allow fund manipulation or unauthorised withdrawals is immediately critical."
        ),
    },
    {
        "name": "Bugcrowd – Square / Block",
        "platform": "Bugcrowd",
        "url": "https://bugcrowd.com/square",
        "max_reward": "$10,000",
        "scope": "squareup.com, Cash App, Square POS, Afterpay, TIDAL",
        "focus": "Payment bypass, account takeover, IDOR, API key exposure",
        "description": (
            "Block (formerly Square) runs payment and consumer-finance products. "
            "Cash App payment-flow and account-security bugs are among the most critical."
        ),
    },
    {
        "name": "HackerOne – Netflix",
        "platform": "HackerOne",
        "url": "https://hackerone.com/netflix",
        "max_reward": "$15,000",
        "scope": "netflix.com, Netflix API, streaming infrastructure, device SDKs",
        "focus": "Account takeover, content DRM bypass, IDOR, payment fraud",
        "description": (
            "Netflix's program covers its global streaming platform. "
            "Bugs enabling account takeover or premium content access without payment are highest priority."
        ),
    },
    {
        "name": "HackerOne – Cloudinary",
        "platform": "HackerOne",
        "url": "https://hackerone.com/cloudinary",
        "max_reward": "$5,000",
        "scope": "cloudinary.com, media delivery APIs, transformation URLs",
        "focus": "SSRF via image URLs, broken access control, media manipulation",
        "description": (
            "Cloudinary powers image/video delivery for thousands of apps. "
            "SSRF via transformation parameters and broken access control on media assets are prime targets."
        ),
    },
    {
        "name": "HackerOne – Semrush",
        "platform": "HackerOne",
        "url": "https://hackerone.com/semrush",
        "max_reward": "$5,000",
        "scope": "semrush.com, SEMrush API, related marketing tools",
        "focus": "IDOR, XSS, auth bypass, data scraping of competitor intelligence",
        "description": (
            "SEMrush's marketing-analytics platform stores competitive SEO data for enterprise clients. "
            "Cross-account data access and XSS are the most common finding classes."
        ),
    },
    {
        "name": "HackerOne – HubSpot",
        "platform": "HackerOne",
        "url": "https://hackerone.com/hubspot",
        "max_reward": "$10,000",
        "scope": "hubspot.com, HubSpot CRM, Marketing Hub, CMS Hub",
        "focus": "SSRF, XSS, IDOR, template injection, CSRF",
        "description": (
            "HubSpot's CRM platform stores sales and marketing data for thousands of SMBs. "
            "Template injection in HubSpot's CMS and cross-portal data leakage are interesting targets."
        ),
    },
    {
        "name": "HackerOne – Kubernetes (CNCF)",
        "platform": "HackerOne",
        "url": "https://hackerone.com/kubernetes",
        "max_reward": "$10,000",
        "scope": "Kubernetes core, API server, kubelet, etcd, kubectl",
        "focus": "Container escape, cluster takeover, RBAC bypass, API server auth",
        "description": (
            "Kubernetes is the backbone of cloud-native infrastructure worldwide. "
            "Container-escape and API-server compromise bugs have massive downstream impact across the ecosystem."
        ),
    },
    {
        "name": "Intigriti – Swisscom",
        "platform": "Intigriti",
        "url": "https://app.intigriti.com/programs/swisscom/swisscombbp/detail",
        "max_reward": "€10,000",
        "scope": "swisscom.ch, Swisscom TV, business portals, APIs",
        "focus": "Auth bypass, IDOR, XSS, telecom API abuse",
        "description": (
            "Swisscom is Switzerland's largest telecom provider. "
            "Bugs on their customer portals and telecom APIs that affect subscriber data are top priority."
        ),
    },
    {
        "name": "Intigriti – Bugcrowd",
        "platform": "Intigriti",
        "url": "https://app.intigriti.com/programs/bugcrowd/bugcrowdbbp/detail",
        "max_reward": "€5,000",
        "scope": "bugcrowd.com, Bugcrowd platform APIs",
        "focus": "Programme boundary bypass, IDOR, researcher account takeover",
        "description": (
            "Like HackerOne, Bugcrowd runs a bounty on its own platform via a competitor. "
            "Cross-programme data leakage and authentication bugs are particularly interesting."
        ),
    },
    {
        "name": "HackerOne – Docker",
        "platform": "HackerOne",
        "url": "https://hackerone.com/docker",
        "max_reward": "$5,000",
        "scope": "docker.com, Docker Hub, Docker Desktop, Docker Scout",
        "focus": "Container escape, registry auth bypass, supply-chain attacks, image tampering",
        "description": (
            "Docker's program covers its container-runtime and registry infrastructure. "
            "Container-escape bugs and supply-chain vulnerabilities in Docker Hub have broad industry impact."
        ),
    },
    {
        "name": "HackerOne – Binance",
        "platform": "HackerOne",
        "url": "https://hackerone.com/binance",
        "max_reward": "$15,000",
        "scope": "binance.com, Binance Chain, BNB Smart Chain, Binance API",
        "focus": "Crypto theft, account takeover, trading engine manipulation, API key exposure",
        "description": (
            "Binance is the world's largest crypto exchange by volume. "
            "Any bug allowing fund access or trading manipulation is immediately critical with enormous stakes."
        ),
    },
    {
        "name": "HackerOne – Rocket.Chat",
        "platform": "HackerOne",
        "url": "https://hackerone.com/rocket_chat",
        "max_reward": "$5,000",
        "scope": "rocket.chat, Rocket.Chat server, mobile and desktop apps",
        "focus": "RCE via admin settings, XSS in messages, IDOR, privilege escalation",
        "description": (
            "Rocket.Chat is a popular open-source team-messaging platform. "
            "Many self-hosted deployments go unpatched, and XSS in message rendering is a recurring target."
        ),
    },
    {
        "name": "HackerOne – TikTok",
        "platform": "HackerOne",
        "url": "https://hackerone.com/tiktok",
        "max_reward": "$14,800",
        "scope": "tiktok.com, TikTok mobile apps, TikTok APIs, creator tools",
        "focus": "Account takeover, privacy data access, IDOR, XSS, content manipulation",
        "description": (
            "TikTok's program covers its global short-video platform. "
            "Bugs that allow mass scraping of private data or influencer account takeover are top priority."
        ),
    },
    {
        "name": "Intigriti – Ubisoft",
        "platform": "Intigriti",
        "url": "https://app.intigriti.com/programs/ubisoft/ubisoft/detail",
        "max_reward": "€10,000",
        "scope": "ubisoft.com, Ubisoft Connect, game APIs, player account services",
        "focus": "Account takeover, game currency manipulation, IDOR, XSS",
        "description": (
            "Ubisoft runs a bounty covering its gaming platform and player accounts. "
            "Virtual currency manipulation and account-takeover bugs are top priority."
        ),
    },
    {
        "name": "HackerOne – Brave Software",
        "platform": "HackerOne",
        "url": "https://hackerone.com/brave",
        "max_reward": "$5,000",
        "scope": "brave.com, Brave Browser, Brave Rewards, BAT wallet",
        "focus": "Browser sandbox escape, wallet theft, fingerprinting bypass, XSS",
        "description": (
            "Brave's privacy-focused browser and built-in crypto wallet make for a unique attack surface. "
            "Bugs that drain the integrated BAT wallet or break privacy guarantees are highest priority."
        ),
    },
    {
        "name": "HackerOne – Nextcloud",
        "platform": "HackerOne",
        "url": "https://hackerone.com/nextcloud",
        "max_reward": "$2,500",
        "scope": "nextcloud.com, Nextcloud Hub, Nextcloud apps, Talk, Files",
        "focus": "RCE via app framework, IDOR, file access bypass, XSS",
        "description": (
            "Nextcloud is a widely deployed self-hosted collaboration suite. "
            "Many enterprises host their own instances – IDOR and app-framework RCE bugs have broad impact."
        ),
    },
]

# Discord embed colour (gold / bounty)
_EMBED_COLOUR = 0xF1C40F


def _compact(value: str, limit: int = 1024) -> str:
    """Return *value* trimmed to Discord field limits."""
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _program_text(program: dict) -> str:
    return " ".join(
        [
            program.get("name", ""),
            program.get("platform", ""),
            program.get("scope", ""),
            program.get("focus", ""),
            program.get("description", ""),
        ]
    ).lower()


def _matching_tip(program: dict) -> str:
    """Generate a practical tip aligned with the selected program profile."""
    text = _program_text(program)
    scope_hint = program.get("scope", "")
    scope_hint = scope_hint.split(",")[0].strip() if scope_hint else "primary in-scope assets"

    rulebook = [
        (("idor", "authorization", "tenant isolation"),
         "Start with horizontal and vertical authorization checks on each API object ID; compare responses across two accounts."),
        (("ssrf", "metadata", "cloud"),
         "Map URL-fetch features first, then test SSRF controls and cloud-metadata protections with strict allow-list bypass checks."),
        (("xss", "stored xss"),
         "Trace all rich-text and markdown inputs end-to-end and test stored-XSS payloads that execute in higher-privileged views."),
        (("oauth", "token", "account takeover"),
         "Focus on OAuth/token lifecycle: callback validation, token leakage in redirects, and scope escalation across apps."),
        (("payment", "wallet", "trading", "fund"),
         "Review money-moving flows for amount tampering, replay, race conditions, and missing server-side integrity checks."),
        (("rce", "pipeline", "ci/cd", "sandbox"),
         "Probe template/build execution paths and worker isolation boundaries for command execution or sandbox escapes."),
        (("api", "jwt", "key exposure"),
         "Enumerate API auth models, then verify signature validation, key rotation handling, and permission enforcement per endpoint."),
    ]

    for keywords, tip in rulebook:
        if any(keyword in text for keyword in keywords):
            return f"{tip} Prioritise {scope_hint}."

    return (
        "Begin with account boundary tests and high-impact business flows first, then move to injection and misconfiguration checks "
        f"on {scope_hint}."
    )


def _matching_writeup(program: dict) -> str:
    """Generate writeup guidance aligned with the selected program and platform."""
    platform = program.get("platform", "").lower()
    focus = program.get("focus", "general web security issues")
    name = program.get("name", "this program")

    if "hackerone" in platform:
        source = "HackerOne disclosed reports"
    elif "bugcrowd" in platform:
        source = "Bugcrowd disclosed reports"
    elif "intigriti" in platform:
        source = "Intigriti public hall-of-fame writeups"
    else:
        source = "public writeups and conference talks"

    return (
        f"Read {source} for {name} and prioritise cases covering: {focus}. "
        "Use those patterns to build your first test checklist."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pick_random_program(
    log_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """Return a randomly selected bug bounty program dict."""
    program = random.choice(BUG_BOUNTY_PROGRAMS).copy()
    program.setdefault("tip", _matching_tip(program))
    program.setdefault("writeup", _matching_writeup(program))
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
            {"name": "Scope",       "value": _compact(program.get("scope", "See program")),   "inline": False},
            {"name": "Focus Areas", "value": _compact(program.get("focus", "General")),       "inline": False},
            {"name": "Tip",         "value": _compact(program.get("tip", "")),                "inline": False},
            {"name": "Matching Writeup", "value": _compact(program.get("writeup", "")),       "inline": False},
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
