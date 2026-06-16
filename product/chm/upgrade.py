"""Self-update mechanism for CHM.

Checks PyPI for the latest version and upgrades via pip.
"""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from chm import __version__

PYPI_URL = "https://pypi.org/pypi/chm-cli/json"
CHECK_FILE = Path.home() / ".config" / "chm" / ".last_update_check"


def get_latest_version() -> str | None:
    """Get the latest version from PyPI. Returns None if unreachable."""
    try:
        req = urllib.request.Request(PYPI_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data["info"]["version"]
    except Exception:
        return None


def check_for_update() -> dict:
    """Check if a newer version is available."""
    latest = get_latest_version()
    if not latest:
        return {"current": __version__, "latest": None, "update_available": False, "error": "Cannot reach PyPI"}

    current_parts = [int(x) for x in __version__.split(".")]
    latest_parts = [int(x) for x in latest.split(".")]

    update_available = latest_parts > current_parts

    return {
        "current": __version__,
        "latest": latest,
        "update_available": update_available,
        "message": (
            f"🚀 New version available: {latest} (you have {__version__})"
            if update_available
            else f"✅ You're on the latest version ({__version__})"
        ),
    }


def perform_upgrade() -> dict:
    """Upgrade CHM via pip. Returns result dict."""
    check = check_for_update()
    if not check["update_available"]:
        return {"success": True, "message": check["message"], "already_latest": True}

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "chm-cli"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return {"success": True, "message": f"✅ Upgraded to {check['latest']}!", "new_version": check["latest"]}
        else:
            return {"success": False, "message": f"pip failed: {result.stderr.strip()}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
