"""CHM configuration management.

Stores user preferences in ~/.config/chm/config.json
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "chm"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "max_commits": 500,
    "default_report": "terminal",
    "api_url": "https://api.lighthouse-analytics.dev",
    "stale_months": 6,
    "min_duplicate_lines": 6,
}


def load() -> dict:
    """Load configuration, merging with defaults."""
    config = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            user = json.loads(CONFIG_FILE.read_text())
            config.update(user)
        except (json.JSONDecodeError, OSError):
            pass
    return config


def save(config: dict):
    """Save configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get(key: str, default=None):
    """Get a single config value."""
    return load().get(key, default)


def set_value(key: str, value):
    """Set a single config value and save."""
    config = load()
    config[key] = value
    save(config)


def list_all() -> dict:
    """List all current config."""
    return load()


def reset():
    """Reset to defaults."""
    save(dict(DEFAULTS))


def show_config() -> str:
    """Format config for display."""
    config = load()
    lines = []
    for key, value in config.items():
        # Mask secrets
        if "key" in key or "token" in key or "secret" in key:
            if isinstance(value, str) and len(value) > 8:
                value = value[:4] + "****" + value[-4:]
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)
