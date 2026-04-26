# Webhook Command Center

A dark-themed Python desktop application that acts as a command centre for
Discord webhook bots.  Right now it ships with one bot – the
**Cybersecurity Writeups** scheduler – and is designed so more bots can be
added as new tabs in the future.

## Features

| Tab | What it does |
|-----|--------------|
| ⚙ Configuration | Set webhook URLs, post intervals, and auto-start options. Settings are saved to `config.json`. |
| 🔐 Cybersecurity Writeups | Automatically fetches a random cybersecurity writeup from several RSS feeds (CTFTime, PortSwigger, Google Project Zero, NCC Group, Exploit-DB, HackerOne, Google Security Blog) and posts a rich Discord embed every N hours. |

## Requirements

* Python 3.10+
* `tkinter` (included with most Python distributions; on Debian/Ubuntu install `python3-tk`)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

1. Open the **⚙ Configuration** tab.
2. Paste your Discord webhook URL into the *Discord Webhook URL* field.
3. Adjust the *Post Interval* (default: 24 hours).
4. Click **💾 Save Configuration**.
5. Switch to the **🔐 Cybersecurity Writeups** tab and press **▶ Start**.

The scheduler posts a writeup immediately and then again every N hours.
Use **⚡ Send Now** to post on demand at any time.

## Project structure

```
main.py        – GUI entry point (Tkinter)
config.py      – Load / save configuration (config.json)
cyber_hook.py  – RSS feed fetcher + Discord webhook poster
requirements.txt
```
