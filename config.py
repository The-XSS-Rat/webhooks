"""Configuration management – load and save settings to a local JSON file."""

import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG: dict = {
    "cyber_webhook_url": "",
    "cyber_interval_hours": 24,
    "cyber_auto_start": False,
    "resources_webhook_url": "",
    "resources_interval_hours": 24,
    "resources_auto_start": False,
    "music_webhook_url": "",
    "music_interval_hours": 24,
    "music_auto_start": False,
}


def load_config() -> dict:
    """Return the saved configuration, merged with defaults for any missing keys."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Persist *config* to disk."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
