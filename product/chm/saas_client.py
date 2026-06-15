"""SaaS platform integration for CHM CLI.

Handles license validation, API key usage, and usage reporting.
Set CHM_API_KEY or CHM_LICENSE_KEY environment variables, or use
chm login / chm license commands.
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# Default API endpoint — override with CHM_API_URL env var
DEFAULT_API_URL = "https://api.lighthouse-analytics.dev"
CONFIG_DIR = Path.home() / ".config" / "chm"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_api_url() -> str:
    """Get the API server URL."""
    return os.getenv("CHM_API_URL", DEFAULT_API_URL)


def get_config() -> dict:
    """Load local config."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config: dict):
    """Save local config."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_api_key() -> Optional[str]:
    """Get the configured API key."""
    return os.getenv("CHM_API_KEY") or get_config().get("api_key")


def get_license_key() -> Optional[str]:
    """Get the configured license key."""
    return os.getenv("CHM_LICENSE_KEY") or get_config().get("license_key")


def validate_license(key: str) -> dict:
    """Validate a license key against the server."""
    api_url = get_api_url()
    try:
        req = urllib.request.Request(
            f"{api_url}/api/license/validate",
            data=json.dumps({"license_key": key}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"valid": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"valid": False, "error": str(e), "offline": True}


def report_usage(action: str, repo_name: str = None, metadata: dict = None):
    """Report usage to the SaaS platform (non-blocking, best-effort)."""
    api_key = get_api_key()
    if not api_key:
        return

    try:
        api_url = get_api_url()
        data = {"action": action, "repo_name": repo_name}
        if metadata:
            data["metadata"] = metadata

        req = urllib.request.Request(
            f"{api_url}/api/usage/report",
            data=json.dumps(data).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # Usage reporting is best-effort, never block on failure


def check_entitlement() -> dict:
    """Check what the user is entitled to based on license/API key.

    Returns:
        {"plan": "free"|"pro"|"enterprise", "features": [...], "valid": bool}
    """
    # Try license key first
    license_key = get_license_key()
    if license_key:
        result = validate_license(license_key)
        if result.get("valid"):
            return {"plan": result.get("plan", "free"), "features": _plan_features(result.get("plan")), "valid": True, "method": "license"}

    # Try API key
    api_key = get_api_key()
    if api_key:
        # API keys are validated server-side on usage
        return {"plan": "pro", "features": _plan_features("pro"), "valid": True, "method": "api_key"}

    # Free tier
    return {"plan": "free", "features": _plan_features("free"), "valid": True, "method": "none"}


def _plan_features(plan: str) -> list[str]:
    """Get feature list for a plan."""
    features = {
        "free": ["terminal", "json"],
        "pro": ["terminal", "json", "html", "history", "email_reports"],
        "enterprise": ["terminal", "json", "html", "history", "email_reports", "ci_cd", "sso"],
    }
    return features.get(plan, features["free"])


def login(api_key: str):
    """Store API key locally."""
    config = get_config()
    config["api_key"] = api_key
    save_config(config)


def logout():
    """Remove stored credentials."""
    config = get_config()
    config.pop("api_key", None)
    config.pop("license_key", None)
    save_config(config)
