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
    # ── Exposed Login Portals ──────────────────────────────────────────────
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
    {
        "category": "Exposed Login Portals",
        "template": 'intitle:"cPanel" inurl:2082 OR inurl:2083 site:{tld}',
        "description": "Finds exposed cPanel web-hosting control panels.",
        "use_case": "Exposed cPanel instances are common on shared hosting – often running old software.",
        "tip": "Check for the version in the page title or footer, then look up known CVEs.",
    },
    {
        "category": "Exposed Login Portals",
        "template": 'inurl:"/phpmyadmin/" intitle:"phpMyAdmin" site:{tld}',
        "description": "Locates publicly accessible phpMyAdmin database management interfaces.",
        "use_case": "phpMyAdmin exposes full database control – default credentials are widely published.",
        "tip": "Try default credentials: root/root, root/(empty). Report without logging in.",
    },
    {
        "category": "Exposed Login Portals",
        "template": 'inurl:"/admin/login" OR inurl:"/administrator/login" site:{tld}',
        "description": "Finds generic admin login paths across a TLD.",
        "use_case": "Common CMS and custom admin panels often live at predictable paths.",
        "tip": "Pair with Burp to check for default credentials or password-spray vectors.",
    },
    {
        "category": "Exposed Login Portals",
        "template": 'intitle:"Webmin" inurl:10000 site:{tld}',
        "description": "Discovers exposed Webmin server-administration panels.",
        "use_case": "Webmin on port 10000 is frequently left internet-facing on VPS hosts.",
        "tip": "CVE-2019-15107 is a classic backdoor RCE in Webmin – check version first.",
    },
    {
        "category": "Exposed Login Portals",
        "template": 'intitle:"Grafana" inurl:"/login" site:{tld}',
        "description": "Finds exposed Grafana dashboard login pages.",
        "use_case": "Grafana dashboards leak infrastructure metrics and sometimes embed secrets.",
        "tip": "Default credentials are admin/admin. Anonymous access is also often enabled.",
    },
    {
        "category": "Exposed Login Portals",
        "template": 'inurl:"/wp-admin/setup-config.php" site:{tld}',
        "description": "Finds WordPress sites whose setup has never been completed.",
        "use_case": "An incomplete WordPress setup allows an attacker to set their own DB credentials.",
        "tip": "If the setup wizard is accessible you may be able to take over the entire installation.",
    },
    # ── Sensitive Files ────────────────────────────────────────────────────
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
    {
        "category": "Sensitive Files",
        "template": 'filetype:pdf "confidential" OR "internal use only" site:{tld}',
        "description": "Finds publicly indexed confidential PDF documents.",
        "use_case": "Sensitive business documents are frequently indexed by mistake.",
        "tip": "Also try filetype:docx, filetype:xlsx for spreadsheets and Word docs.",
    },
    {
        "category": "Sensitive Files",
        "template": 'filetype:xls OR filetype:xlsx inurl:password site:{tld}',
        "description": "Looks for Excel spreadsheets that contain password data.",
        "use_case": "IT teams often store credentials in spreadsheets and accidentally expose them.",
        "tip": "Also search for filetype:csv intext:password to cover CSV exports.",
    },
    {
        "category": "Sensitive Files",
        "template": 'filetype:pem OR filetype:crt OR filetype:cer site:{tld}',
        "description": "Searches for exposed SSL/TLS certificate or key files.",
        "use_case": "Exposed private key files (filetype:key, filetype:pem) allow HTTPS impersonation.",
        "tip": "Check filetype:key separately – that's where private keys typically live.",
    },
    {
        "category": "Sensitive Files",
        "template": 'filetype:cfg intext:"password" site:{tld}',
        "description": "Finds configuration files containing the word password.",
        "use_case": "App config files are a goldmine for credentials and connection strings.",
        "tip": "Also try filetype:ini, filetype:conf, filetype:properties.",
    },
    {
        "category": "Sensitive Files",
        "template": 'filetype:json intext:"api_key" OR intext:"access_token" site:{tld}',
        "description": "Finds JSON files leaking API keys or access tokens.",
        "use_case": "Client-side JS bundles and debug endpoints often expose tokens in JSON.",
        "tip": "Also look for filetype:js to catch tokens embedded in JavaScript files.",
    },
    {
        "category": "Sensitive Files",
        "template": 'inurl:"/etc/passwd" filetype:txt site:{tld}',
        "description": "Finds accidentally web-exposed /etc/passwd content.",
        "use_case": "Confirms LFI is being exploited or that passwd was accidentally copied to webroot.",
        "tip": "Combine with an LFI payload to read /etc/shadow if permissions allow.",
    },
    # ── Configuration & Secrets ────────────────────────────────────────────
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
    {
        "category": "Configuration & Secrets",
        "template": 'filetype:yaml OR filetype:yml intext:"password:" site:{tld}',
        "description": "Finds YAML config files with embedded passwords.",
        "use_case": "Docker Compose, Ansible, and Kubernetes YAML files frequently contain secrets.",
        "tip": "docker-compose.yml and .travis.yml are particularly common and revealing.",
    },
    {
        "category": "Configuration & Secrets",
        "template": 'inurl:"application.properties" filetype:properties site:{tld}',
        "description": "Finds Spring Boot / Java application configuration files.",
        "use_case": "Spring application.properties often contains DB credentials and API keys.",
        "tip": "Also try application.yml and bootstrap.yml for Spring Cloud Config.",
    },
    {
        "category": "Configuration & Secrets",
        "template": 'inurl:".htpasswd" filetype:htpasswd site:{tld}',
        "description": "Finds exposed Apache .htpasswd credential files.",
        "use_case": ".htpasswd contains hashed credentials that can be cracked offline.",
        "tip": "Use hashcat with mode -m 1500 (MD5-crypt) or -m 3200 (bcrypt).",
    },
    {
        "category": "Configuration & Secrets",
        "template": 'intext:"BEGIN RSA PRIVATE KEY" site:{tld}',
        "description": "Searches for RSA private key content published on web pages.",
        "use_case": "An RSA private key in a web page is an immediate high-severity finding.",
        "tip": "Also search for 'BEGIN OPENSSH PRIVATE KEY' and 'BEGIN EC PRIVATE KEY'.",
    },
    {
        "category": "Configuration & Secrets",
        "template": 'inurl:"secrets.yaml" OR inurl:"secrets.yml" site:{tld}',
        "description": "Finds Kubernetes or Helm secrets files indexed by Google.",
        "use_case": "Kubernetes secrets files contain base64-encoded credentials for cluster services.",
        "tip": "Base64-decode values in found files: echo 'b64value' | base64 -d",
    },
    {
        "category": "Configuration & Secrets",
        "template": 'inurl:"settings.py" intext:"SECRET_KEY" site:{tld}',
        "description": "Finds Django settings.py files exposing the SECRET_KEY.",
        "use_case": "Django's SECRET_KEY is used to sign session cookies – knowing it enables session forgery.",
        "tip": "Also check for DEBUG=True and DATABASES credentials in the same file.",
    },
    {
        "category": "Configuration & Secrets",
        "template": 'filetype:json inurl:"credentials" site:{tld}',
        "description": "Finds credentials JSON files (AWS, GCP, Firebase, etc.).",
        "use_case": "Cloud provider credential files in JSON format are a critical finding.",
        "tip": "GCP service account keys are named *-credentials.json or serviceaccount.json.",
    },
    # ── Open Directories ───────────────────────────────────────────────────
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
    {
        "category": "Open Directories",
        "template": 'intitle:"Index of" "server at" site:{tld}',
        "description": "Finds Apache-style directory listings across a TLD.",
        "use_case": "Apache auto-index reveals directory structure and all contained files.",
        "tip": "The 'Server at' footer reveals the software version – check for known vulnerabilities.",
    },
    {
        "category": "Open Directories",
        "template": 'intitle:"Directory listing for /" site:{tld}',
        "description": "Finds Tomcat / Jetty / Python HTTP server directory listings.",
        "use_case": "Java app servers often expose directory listings during development or misconfiguration.",
        "tip": "Look for WEB-INF/, classes/, and .jar files that may contain source code.",
    },
    {
        "category": "Open Directories",
        "template": 'intitle:"Index of /var/www" site:{tld}',
        "description": "Finds servers with a web root exposed as a directory listing.",
        "use_case": "Reveals the full web server document root including hidden configuration files.",
        "tip": "Check for .env, .git, and database dump files in the listing.",
    },
    # ── Vulnerable Parameters ──────────────────────────────────────────────
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
    {
        "category": "Vulnerable Parameters",
        "template": 'inurl:"?search=" OR inurl:"?q=" OR inurl:"?query=" site:{tld}',
        "description": "Finds search parameters – potential XSS and injection points.",
        "use_case": "Unsanitised search parameters are a primary XSS vector in web applications.",
        "tip": "Test with ?q=<script>alert(1)</script> and observe if it reflects unescaped.",
    },
    {
        "category": "Vulnerable Parameters",
        "template": 'inurl:"?cat=" OR inurl:"?category=" OR inurl:"?pid=" site:{tld}',
        "description": "Finds category and product-ID parameters common in e-commerce sites.",
        "use_case": "E-commerce parameters are frequently injectable and lead to DB enumeration.",
        "tip": "Add a single quote to the value and check for SQL error messages.",
    },
    {
        "category": "Vulnerable Parameters",
        "template": 'inurl:"?callback=" OR inurl:"?jsonp=" site:{tld}',
        "description": "Finds JSONP callback parameters – potential XSS and data leakage.",
        "use_case": "JSONP endpoints reflect the callback parameter name – XSS if unsanitised.",
        "tip": "Inject ?callback=alert to see if it's reflected in the response.",
    },
    {
        "category": "Vulnerable Parameters",
        "template": 'inurl:"?token=" OR inurl:"?access_token=" OR inurl:"?api_key=" site:{tld}',
        "description": "Finds secrets passed in URL query strings (bad practice).",
        "use_case": "Tokens in URLs end up in browser history, server logs, and referrer headers.",
        "tip": "Try to replay the token – it may still be valid and grant unauthorised access.",
    },
    {
        "category": "Vulnerable Parameters",
        "template": 'inurl:"?debug=1" OR inurl:"?test=1" OR inurl:"?staging=true" site:{tld}',
        "description": "Finds debug/test mode toggle parameters left active in production.",
        "use_case": "Debug mode often exposes stack traces, verbose errors, and hidden functionality.",
        "tip": "Try other values: debug=true, debug=on, test=true, dev=1.",
    },
    # ── Cloud & DevOps Exposure ────────────────────────────────────────────
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
    {
        "category": "Cloud & DevOps Exposure",
        "template": 'site:blob.core.windows.net "{company}"',
        "description": "Finds Azure Blob Storage containers referencing a company name.",
        "use_case": "Misconfigured Azure blobs can expose sensitive files to the internet.",
        "tip": "Use tools like BlobHunter to enumerate Azure storage accounts automatically.",
    },
    {
        "category": "Cloud & DevOps Exposure",
        "template": 'site:storage.googleapis.com "{company}"',
        "description": "Finds Google Cloud Storage buckets referencing a company name.",
        "use_case": "Public GCS buckets may expose backups, media, or sensitive user data.",
        "tip": "Use gsutil ls gs://BUCKET_NAME to enumerate contents without authentication.",
    },
    {
        "category": "Cloud & DevOps Exposure",
        "template": 'inurl:"/sonarqube/" OR intitle:"SonarQube" site:{tld}',
        "description": "Finds exposed SonarQube code-quality dashboards.",
        "use_case": "Unauthenticated SonarQube leaks full source code, security issues, and secrets.",
        "tip": "Default credentials are admin/admin. Also check for publicly readable project reports.",
    },
    {
        "category": "Cloud & DevOps Exposure",
        "template": 'intitle:"Kubernetes Dashboard" inurl:"/api/v1/namespaces" site:{tld}',
        "description": "Finds exposed Kubernetes dashboards.",
        "use_case": "An open Kubernetes dashboard gives full cluster control.",
        "tip": "Many dashboards are exposed without auth – check for skip login option.",
    },
    {
        "category": "Cloud & DevOps Exposure",
        "template": 'inurl:".travis.yml" filetype:yml site:{tld}',
        "description": "Finds exposed Travis CI configuration files.",
        "use_case": ".travis.yml can contain encrypted secrets that may be decryptable.",
        "tip": "Check for env: global: with encrypted: values – repo private key may crack them.",
    },
    {
        "category": "Cloud & DevOps Exposure",
        "template": 'inurl:"Dockerfile" filetype:dockerfile site:{tld}',
        "description": "Finds Dockerfiles indexed from public web servers.",
        "use_case": "Dockerfiles reveal app architecture, internal paths, and sometimes credentials.",
        "tip": "Look for ARG and ENV instructions that hardcode secrets into images.",
    },
    {
        "category": "Cloud & DevOps Exposure",
        "template": 'inurl:"/actuator/env" OR inurl:"/actuator/configprops" site:{tld}',
        "description": "Finds exposed Spring Boot Actuator endpoints.",
        "use_case": "Actuator /env dumps all environment variables including passwords and API keys.",
        "tip": "Also check /actuator/heapdump – downloadable heap dumps often contain credentials.",
    },
    # ── Error Messages & Stack Traces ──────────────────────────────────────
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
    {
        "category": "Error Messages & Stack Traces",
        "template": 'intext:"Traceback (most recent call last)" site:{tld}',
        "description": "Finds pages leaking Python stack traces.",
        "use_case": "Python tracebacks reveal framework, file paths, and sometimes variable values.",
        "tip": "Django debug pages can expose SECRET_KEY and full settings when DEBUG=True.",
    },
    {
        "category": "Error Messages & Stack Traces",
        "template": 'intext:"NullPointerException" intext:"at com." site:{tld}',
        "description": "Finds Java stack traces leaking class and package names.",
        "use_case": "Java exceptions expose application structure and framework versions.",
        "tip": "Spring Boot /error pages often include exception details in JSON format too.",
    },
    {
        "category": "Error Messages & Stack Traces",
        "template": 'intitle:"500 Internal Server Error" intext:"Exception" site:{tld}',
        "description": "Finds 500-error pages that leak exception details.",
        "use_case": "Detailed error pages indicate DEBUG mode or misconfigured error handling.",
        "tip": "Submit fuzzed inputs to the same endpoint to trigger different exceptions.",
    },
    {
        "category": "Error Messages & Stack Traces",
        "template": 'intext:"Warning: include(" intext:"failed to open stream" site:{tld}',
        "description": "Finds PHP file-include warnings that may indicate LFI.",
        "use_case": "PHP include warnings confirm LFI and expose the attempted file path.",
        "tip": "Use the exposed path to build absolute LFI payloads for /etc/passwd.",
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
    {
        "category": "IoT & SCADA",
        "template": 'intitle:"RouterOS" inurl:"/winbox/" site:{tld}',
        "description": "Finds exposed MikroTik RouterOS management interfaces.",
        "use_case": "MikroTik devices with exposed Winbox or web interfaces are common attack targets.",
        "tip": "CVE-2018-14847 is a well-known credential-bypass for Winbox.",
    },
    {
        "category": "IoT & SCADA",
        "template": 'intitle:"Hikvision" inurl:"/doc/page/login.asp"',
        "description": "Finds Hikvision IP camera login pages.",
        "use_case": "Hikvision cameras are the world's most popular – and often run default credentials.",
        "tip": "Default credentials: admin/12345. Many models have unauthenticated RTSP streams.",
    },
    {
        "category": "IoT & SCADA",
        "template": 'intitle:"Home Energy Management" OR intitle:"Smart Meter" inurl:login site:{tld}',
        "description": "Finds smart energy management system login panels.",
        "use_case": "Smart meter management portals can expose customer consumption data.",
        "tip": "Energy management systems are rarely hardened – check for default credentials.",
    },
    # ── API Keys & Tokens ──────────────────────────────────────────────────
    {
        "category": "API Keys & Tokens",
        "template": 'site:github.com intext:"api_key" intext:"{company}"',
        "description": "Searches GitHub for API keys committed to public repositories.",
        "use_case": "Developers often accidentally commit API keys to public repos.",
        "tip": "Use truffleHog or gitleaks against the org to scan full commit history.",
    },
    {
        "category": "API Keys & Tokens",
        "template": 'site:github.com "-----BEGIN RSA PRIVATE KEY-----"',
        "description": "Searches GitHub for committed RSA private keys.",
        "use_case": "Accidentally committed private keys are immediately actionable.",
        "tip": "Keys in commit history persist even after deletion – scan all branches.",
    },
    {
        "category": "API Keys & Tokens",
        "template": 'site:github.com "AKIA" intext:"{company}"',
        "description": "Finds AWS IAM access keys (AKIA prefix) in GitHub repos.",
        "use_case": "AWS access keys give programmatic access to cloud resources.",
        "tip": "AKIA is the prefix for long-term IAM access keys. Validate with aws sts get-caller-identity.",
    },
    {
        "category": "API Keys & Tokens",
        "template": 'site:github.com "ghp_" OR "github_pat_" intext:"{company}"',
        "description": "Finds GitHub Personal Access Tokens in public repositories.",
        "use_case": "A leaked GitHub PAT may give write access to private repos.",
        "tip": "Report to GitHub Security – they auto-revoke detected tokens.",
    },
    {
        "category": "API Keys & Tokens",
        "template": 'site:github.com "sk_live_" intext:"{company}"',
        "description": "Finds live Stripe secret API keys committed to GitHub.",
        "use_case": "A live Stripe secret key allows charging customers and reading financial data.",
        "tip": "sk_live_ keys are live production credentials – report immediately.",
    },
    {
        "category": "API Keys & Tokens",
        "template": 'site:github.com "AIza" intext:"{company}"',
        "description": "Finds Google API keys (AIza prefix) in GitHub repos.",
        "use_case": "Google API keys can be abused for Maps, Firebase, or cloud service billing.",
        "tip": "Check key permissions with the Google API Explorer before reporting scope.",
    },
    {
        "category": "API Keys & Tokens",
        "template": 'site:github.com "xoxb-" OR "xoxp-" intext:"{company}"',
        "description": "Finds Slack bot and user tokens in GitHub repositories.",
        "use_case": "Slack tokens allow reading and posting messages in workspaces.",
        "tip": "xoxb- = bot token, xoxp- = user token. Both allow API access to workspace data.",
    },
    # ── Admin Panels & CMS ─────────────────────────────────────────────────
    {
        "category": "Admin Panels & CMS",
        "template": 'inurl:"/admin/dashboard" OR inurl:"/admin/panel" site:{tld}',
        "description": "Finds admin dashboards at common URL paths.",
        "use_case": "Admin panels are high-value targets for credential attacks.",
        "tip": "Check response codes: a 200 without auth is an immediate finding.",
    },
    {
        "category": "Admin Panels & CMS",
        "template": 'intitle:"Drupal" inurl:"/user/login" site:{tld}',
        "description": "Locates Drupal CMS login pages.",
        "use_case": "Drupal has a history of critical RCE vulnerabilities (Drupalgeddon).",
        "tip": "Check /CHANGELOG.txt to identify the exact Drupal version and look up CVEs.",
    },
    {
        "category": "Admin Panels & CMS",
        "template": 'intitle:"Joomla" inurl:"/administrator/index.php" site:{tld}',
        "description": "Finds Joomla CMS administrator login pages.",
        "use_case": "Joomla administrator panels are a common target for bruteforce.",
        "tip": "Check /administrator/manifests/files/joomla.xml for the exact version.",
    },
    {
        "category": "Admin Panels & CMS",
        "template": 'inurl:"/wp-content/uploads/" filetype:php site:{tld}',
        "description": "Finds PHP files uploaded to WordPress – potential webshells.",
        "use_case": "PHP files in /wp-content/uploads/ strongly suggest a file-upload bypass.",
        "tip": "Access the file directly – if it executes code this is a confirmed RCE.",
    },
    {
        "category": "Admin Panels & CMS",
        "template": 'intitle:"Magento" inurl:"/admin/" site:{tld}',
        "description": "Finds Magento e-commerce admin login portals.",
        "use_case": "Magento admins control entire storefronts including payment data.",
        "tip": "Check /magento_version or /magento/pub/static/version to identify version.",
    },
    # ── Network Devices ────────────────────────────────────────────────────
    {
        "category": "Network Devices",
        "template": 'intitle:"Cisco" inurl:"/exec/show/version/cr" site:{tld}',
        "description": "Finds exposed Cisco device show-version output pages.",
        "use_case": "Reveals exact IOS version and model for targeted vulnerability research.",
        "tip": "Exposed Cisco HTTP management interfaces are frequently vulnerable to auth bypass.",
    },
    {
        "category": "Network Devices",
        "template": 'intitle:"Netgear" inurl:"/currentsetting.htm" site:{tld}',
        "description": "Finds internet-facing Netgear router management pages.",
        "use_case": "Netgear routers often have unauthenticated information disclosure.",
        "tip": "CVE-2017-5521 – unauthenticated admin password disclosure affects many Netgear models.",
    },
    {
        "category": "Network Devices",
        "template": 'intitle:"pfSense" inurl:"/index.php" intext:"Dashboard" site:{tld}',
        "description": "Locates internet-exposed pfSense firewall dashboards.",
        "use_case": "pfSense controls network traffic – RCE here gives full network access.",
        "tip": "Default credentials are admin/pfsense. Check for CVEs in the installed version.",
    },
    {
        "category": "Network Devices",
        "template": 'intitle:"Fortigate" inurl:"/remote/login" site:{tld}',
        "description": "Finds Fortinet FortiGate SSL-VPN login pages.",
        "use_case": "FortiGate VPNs have had several critical CVEs including credential disclosure.",
        "tip": "CVE-2018-13379 is a path-traversal that leaks VPN credentials in plain text.",
    },
    # ── Version Control & Source Code ──────────────────────────────────────
    {
        "category": "Version Control & Source Code",
        "template": 'site:github.com "{company}" password OR secret OR token intext:production',
        "description": "Searches GitHub for production credentials in repositories.",
        "use_case": "Production secrets committed to public repos are immediately critical.",
        "tip": "Check all branches, tags, and full commit history – deletion doesn't erase git history.",
    },
    {
        "category": "Version Control & Source Code",
        "template": 'site:gitlab.com "{company}" filetype:env',
        "description": "Searches GitLab for exposed .env files in public repos.",
        "use_case": "Developers sometimes make repos public accidentally with .env files inside.",
        "tip": "Also search for .env.production and .env.local which are commonly gitignored but forgotten.",
    },
    {
        "category": "Version Control & Source Code",
        "template": 'inurl:"/svn/" intitle:"Revision" site:{tld}',
        "description": "Finds exposed Subversion (SVN) repositories.",
        "use_case": "Browsable SVN repos allow downloading full source code history.",
        "tip": "Use svn checkout svn://target/svn/ to pull the full repo locally.",
    },
    {
        "category": "Version Control & Source Code",
        "template": 'inurl:"/.svn/entries" site:{tld}',
        "description": "Finds servers with an exposed .svn/entries file.",
        "use_case": "The entries file lists all files under version control and their paths.",
        "tip": "Tools like dvcs-ripper can reconstruct SVN repos from exposed metadata.",
    },
    # ── Database Exposure ──────────────────────────────────────────────────
    {
        "category": "Database Exposure",
        "template": 'intitle:"phpPgAdmin" inurl:"/phpPgAdmin/" site:{tld}',
        "description": "Finds exposed phpPgAdmin PostgreSQL administration interfaces.",
        "use_case": "phpPgAdmin gives full database access including reading all tables.",
        "tip": "Check whether anonymous login is enabled – many instances allow it by default.",
    },
    {
        "category": "Database Exposure",
        "template": 'inurl:"/db/index.php" intitle:"Adminer" site:{tld}',
        "description": "Finds exposed Adminer database management interfaces.",
        "use_case": "Adminer supports MySQL, PostgreSQL, SQLite, and more – full DB access.",
        "tip": "Adminer < 4.7.9 had an SSRF vulnerability – check version before testing further.",
    },
    {
        "category": "Database Exposure",
        "template": 'inurl:":9200" intitle:"Elasticsearch" site:{tld}',
        "description": "Finds exposed Elasticsearch instances on port 9200.",
        "use_case": "Unauthenticated Elasticsearch clusters can expose millions of records.",
        "tip": "Query /_cat/indices?v to list all indexes and their record counts.",
    },
    {
        "category": "Database Exposure",
        "template": 'inurl:":27017" OR inurl:":28017" intitle:"MongoDB" site:{tld}',
        "description": "Finds MongoDB instances with the HTTP status interface exposed.",
        "use_case": "MongoDB without auth is a perennial data-breach source.",
        "tip": "Use mongodump to extract data. Report total record count in your PoC.",
    },
    # ── Subdomains & Infrastructure ────────────────────────────────────────
    {
        "category": "Subdomains & Infrastructure",
        "template": 'site:{tld} -www inurl:dev OR inurl:staging OR inurl:test',
        "description": "Finds development, staging, and test subdomains on a TLD.",
        "use_case": "Dev/staging environments often have debug mode on and weaker controls.",
        "tip": "Staging environments frequently share prod DB credentials or point to prod APIs.",
    },
    {
        "category": "Subdomains & Infrastructure",
        "template": 'site:{tld} inurl:internal OR inurl:intranet OR inurl:corp',
        "description": "Finds internal or intranet subdomains accidentally exposed.",
        "use_case": "Internal tools exposed to the internet often lack proper authentication.",
        "tip": "Combine with tools like Amass to enumerate all subdomains on the target.",
    },
    {
        "category": "Subdomains & Infrastructure",
        "template": 'site:{tld} intitle:"under construction" OR intitle:"coming soon"',
        "description": "Finds placeholder pages on subdomains that may be takeover candidates.",
        "use_case": "Orphaned subdomains pointing to expired services are vulnerable to takeover.",
        "tip": "Check DNS CNAME targets with dig/nslookup – a dangling CNAME is takeover-ready.",
    },
    # ── Juicy Files & Documents ────────────────────────────────────────────
    {
        "category": "Juicy Files & Documents",
        "template": 'filetype:pdf inurl:"pentest" OR inurl:"security assessment" site:{tld}',
        "description": "Finds old penetration test reports accidentally published.",
        "use_case": "A leaked pentest report hands you the recon work for free.",
        "tip": "Old reports also reveal the technology stack, internal IPs, and previous findings.",
    },
    {
        "category": "Juicy Files & Documents",
        "template": 'filetype:xls OR filetype:xlsx intext:"username" intext:"password" site:{tld}',
        "description": "Finds Excel files containing username and password columns.",
        "use_case": "IT and support teams routinely store credentials in spreadsheets.",
        "tip": "Use LibreOffice Calc to open protected XLS files – password protection is weak.",
    },
    {
        "category": "Juicy Files & Documents",
        "template": 'filetype:doc OR filetype:docx intext:"confidential" intext:"not for distribution" site:{tld}',
        "description": "Finds Word documents marked confidential indexed by Google.",
        "use_case": "Sensitive business documents often get shared externally and indexed.",
        "tip": "Also look for NDAs, contracts, and HR documents with filetype:pdf.",
    },
    {
        "category": "Juicy Files & Documents",
        "template": 'inurl:"/api/swagger.json" OR inurl:"/api/swagger.yaml" site:{tld}',
        "description": "Finds exposed Swagger / OpenAPI specification files.",
        "use_case": "Swagger docs fully enumerate API endpoints, parameters, and auth schemes.",
        "tip": "Import into Burp via Extensions > OpenAPI Parser to auto-generate requests.",
    },
    {
        "category": "Juicy Files & Documents",
        "template": 'inurl:"/api/v1/docs" OR inurl:"/api/v2/docs" intitle:"API" site:{tld}',
        "description": "Finds API documentation pages.",
        "use_case": "API docs reveal all endpoints, authentication methods, and data structures.",
        "tip": "Look for undocumented or deprecated endpoints not linked from the UI.",
    },
    # ── Bug Bounty Recon ───────────────────────────────────────────────────
    {
        "category": "Bug Bounty Recon",
        "template": 'site:{tld} ext:php OR ext:asp OR ext:aspx OR ext:jsp inurl:upload',
        "description": "Finds upload endpoints in server-side script pages.",
        "use_case": "File upload endpoints are prime targets for unrestricted file upload / RCE.",
        "tip": "Bypass extension filters with double extensions: shell.php.jpg or null-byte tricks.",
    },
    {
        "category": "Bug Bounty Recon",
        "template": 'inurl:"/api/" intitle:"401 Unauthorized" OR intitle:"403 Forbidden" site:{tld}',
        "description": "Finds API endpoints returning auth errors – they exist but need creds.",
        "use_case": "Known API paths are valuable for IDOR testing once you have valid credentials.",
        "tip": "Try changing HTTP method (GET→POST), removing Auth header, or using null UUIDs.",
    },
    {
        "category": "Bug Bounty Recon",
        "template": 'inurl:"/.well-known/security.txt" site:{tld}',
        "description": "Finds security.txt files that list responsible-disclosure contacts.",
        "use_case": "Security.txt tells you exactly where and how to report bugs on a target.",
        "tip": "RFC 9116 defines the format – check for scope hints and bug bounty links.",
    },
    {
        "category": "Bug Bounty Recon",
        "template": 'site:hackerone.com "hacktivity" intext:"{company}"',
        "description": "Searches HackerOne's public hacktivity for disclosed reports on a target.",
        "use_case": "Disclosed reports reveal past finding classes and program scope nuances.",
        "tip": "Repeat or chain disclosed bugs – programs often fix only the specific instance.",
    },
    {
        "category": "Bug Bounty Recon",
        "template": 'inurl:"robots.txt" intext:"disallow" site:{tld}',
        "description": "Finds robots.txt files to enumerate disallowed (hidden) paths.",
        "use_case": "Disallowed paths in robots.txt often point to admin areas and sensitive endpoints.",
        "tip": "All paths in Disallow: lines are worth manually investigating.",
    },
    {
        "category": "Bug Bounty Recon",
        "template": 'inurl:"/.git/config" site:{tld}',
        "description": "Finds exposed .git/config files that reveal remote repo URLs.",
        "use_case": "git/config leaks the remote origin URL which may be a private GitHub/GitLab repo.",
        "tip": "Use git-dumper to reconstruct the full repo from the exposed .git/ directory.",
    },
    # ── Email & User Enumeration ───────────────────────────────────────────
    {
        "category": "Email & User Enumeration",
        "template": 'site:linkedin.com intitle:"at {company}" "email" OR "contact"',
        "description": "Finds LinkedIn profiles of employees at a target company.",
        "use_case": "Employee names and roles are the foundation for phishing and password-spray attacks.",
        "tip": "Use Hunter.io or Clearbit to convert names into email addresses.",
    },
    {
        "category": "Email & User Enumeration",
        "template": 'site:{tld} intext:"@{tld}" filetype:txt OR filetype:csv',
        "description": "Finds publicly indexed email address lists on a domain.",
        "use_case": "Email lists confirm active accounts and support phishing or password-spray.",
        "tip": "Validate emails with tools like verify-email.org before using them in attacks.",
    },
    # ── Miscellaneous High-Value ───────────────────────────────────────────
    {
        "category": "Miscellaneous",
        "template": 'inurl:"/cgi-bin/luci" intitle:"OpenWrt" site:{tld}',
        "description": "Finds internet-facing OpenWrt router admin interfaces.",
        "use_case": "OpenWrt routers with exposed admin panels are common in SMB environments.",
        "tip": "Check for CVE-2020-7982 – a package-manager signature bypass leading to RCE.",
    },
    {
        "category": "Miscellaneous",
        "template": 'intitle:"Kibana" inurl:":5601" site:{tld}',
        "description": "Finds exposed Kibana log-analytics dashboards.",
        "use_case": "Unauthenticated Kibana can expose all indexed log data including credentials.",
        "tip": "Check for Canvas, Discover, and Saved Searches – often contain raw log lines with secrets.",
    },
    {
        "category": "Miscellaneous",
        "template": 'intitle:"RabbitMQ Management" inurl:":15672" site:{tld}',
        "description": "Finds exposed RabbitMQ management consoles.",
        "use_case": "RabbitMQ management gives queue visibility and message injection capability.",
        "tip": "Default credentials: guest/guest. Can be used to inject malicious messages.",
    },
    {
        "category": "Miscellaneous",
        "template": 'intext:"Welcome to nginx!" intitle:"nginx" site:{tld}',
        "description": "Finds default nginx welcome pages – unconfigured servers.",
        "use_case": "Default pages indicate fresh installs; explore other virtual hosts.",
        "tip": "Try common paths: /phpinfo.php, /test.php, /info.php on the same host.",
    },
    {
        "category": "Miscellaneous",
        "template": 'inurl:"/phpinfo.php" intitle:"phpinfo()" site:{tld}',
        "description": "Finds phpinfo() pages that expose full PHP and server configuration.",
        "use_case": "phpinfo() leaks PHP version, loaded modules, environment variables, and file paths.",
        "tip": "Environment variables in phpinfo include all $_SERVER values – check for credentials.",
    },
    {
        "category": "Miscellaneous",
        "template": 'intext:"Traccar" inurl:"/api/session" site:{tld}',
        "description": "Finds exposed Traccar GPS-tracking server instances.",
        "use_case": "Traccar tracks vehicle fleets – exposed instances reveal real-time location data.",
        "tip": "Default credentials: admin/admin. API at /api/devices lists all tracked assets.",
    },
    {
        "category": "Miscellaneous",
        "template": 'intitle:"Portainer" inurl:":9000" site:{tld}',
        "description": "Finds exposed Portainer Docker management UI.",
        "use_case": "Portainer gives full Docker control – equivalent to root on the host.",
        "tip": "Uninitialized Portainer (first-run) lets you set your own admin password.",
    },
    {
        "category": "Miscellaneous",
        "template": 'inurl:"/telescope/requests" intitle:"Laravel Telescope" site:{tld}',
        "description": "Finds exposed Laravel Telescope debugging dashboards.",
        "use_case": "Telescope logs all requests, jobs, queries, and exceptions with full payloads.",
        "tip": "Check the 'Requests' tab – it may contain passwords submitted via forms.",
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
