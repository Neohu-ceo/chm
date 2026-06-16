"""End-to-end integration tests — CLI + SaaS full flow."""

import subprocess
import json
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error

PRODUCT_DIR = Path(__file__).parent.parent
CHM_BIN = str(PRODUCT_DIR / ".venv" / "bin" / "chm")
SAAS_BASE = "http://localhost:5001"
DEMO_REPO = "/tmp/chm-demo"


def api(method: str, path: str, data: dict = None, cookies: str = None) -> tuple[int, dict]:
    """Make an API call to the SaaS."""
    url = f"{SAAS_BASE}{path}"
    body = json.dumps(data).encode() if data else None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if cookies:
        req.add_header("Cookie", cookies)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            cookie_header = resp.headers.get("Set-Cookie", "")
            return resp.status, json.loads(resp.read()), cookie_header
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), ""


class TestE2E:
    """End-to-end test suite."""

    def test_cli_analyze(self):
        """CLI: run analyze on demo repo."""
        result = subprocess.run(
            [CHM_BIN, "analyze", DEMO_REPO, "--report", "json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert "health_score" in data
        assert "hotspots" in data
        assert "authors" in data
        assert "pulse" in data
        assert "complexity" in data
        assert 0 <= data["health_score"] <= 100

    def test_cli_html_report(self):
        """CLI: generate HTML report."""
        out = "/tmp/chm-e2e-report.html"
        result = subprocess.run(
            [CHM_BIN, "analyze", DEMO_REPO, "--report", "html", "-o", out],
            capture_output=True, timeout=30,
        )
        assert result.returncode == 0
        content = Path(out).read_text()
        assert "<!DOCTYPE html>" in content
        assert "Lighthouse Analytics" in content

    def test_cli_badge(self):
        """CLI: generate badge."""
        result = subprocess.run(
            [CHM_BIN, "badge", DEMO_REPO],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "<svg" in result.stdout

    def test_cli_doctor(self):
        """CLI: run doctor."""
        result = subprocess.run(
            [CHM_BIN, "doctor", DEMO_REPO],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert "Health Score" in result.stdout

    def test_cli_snapshot_and_trends(self):
        """CLI: snapshot + trends."""
        subprocess.run([CHM_BIN, "snapshot", DEMO_REPO], capture_output=True, timeout=10)
        result = subprocess.run(
            [CHM_BIN, "trends", DEMO_REPO],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_cli_config(self):
        """CLI: config management."""
        # Set
        subprocess.run([CHM_BIN, "config", "--set", "max_commits", "300"], capture_output=True, timeout=5)
        # Get
        result = subprocess.run(
            [CHM_BIN, "config", "--get", "max_commits"],
            capture_output=True, text=True, timeout=5,
        )
        assert "300" in result.stdout
        # Reset
        subprocess.run([CHM_BIN, "config", "--reset"], capture_output=True, timeout=5)

    def test_cli_export_csv(self):
        """CLI: export CSV."""
        out = "/tmp/chm-e2e-export.csv"
        result = subprocess.run(
            [CHM_BIN, "export", DEMO_REPO, "-o", out],
            capture_output=True, timeout=15,
        )
        assert result.returncode == 0
        content = Path(out).read_text()
        assert "# Hotspots" in content
        assert "# Contributors" in content
        assert "# Complexity" in content

    def test_saas_register_and_login(self):
        """SaaS: register, login, get profile."""
        email = f"e2e{int(time.time())}@test.com"
        # Register
        code, data, cookie = api("POST", "/api/auth/register", {
            "email": email, "password": "e2etest123", "name": "E2E User",
        })
        assert code == 201, f"Register failed: {data}"
        assert data["success"]
        session_cookie = cookie

        # Get profile
        code, data, _ = api("GET", "/api/auth/me", cookies=session_cookie)
        assert code == 200
        assert data["user"]["email"] == email

        # Create API key
        code, data, _ = api("POST", "/api/keys", {"name": "E2E Key"}, cookies=session_cookie)
        assert code == 201
        assert "key" in data

        # Start trial
        code, data, _ = api("POST", "/api/trial/start", {"plan": "pro"}, cookies=session_cookie)
        assert code == 200
        assert data["success"]

        # Upgrade via demo payment
        code, data, _ = api("POST", "/api/demo/complete-payment", {"plan": "pro", "provider": "demo"}, cookies=session_cookie)
        assert code == 200
        assert data["plan"] == "pro"

        # Generate license
        code, data, _ = api("POST", "/api/license", cookies=session_cookie)
        assert code == 201
        assert "license_key" in data

        # Validate license
        code, data, _ = api("POST", "/api/license/validate", {"license_key": data["license_key"]})
        assert code == 200
        assert data["valid"] is True

    def test_saas_health(self):
        """SaaS: health check."""
        code, data, _ = api("GET", "/health")
        assert code == 200
        assert data["status"] == "healthy"

    def test_saas_docs_public(self):
        """SaaS: docs page is accessible."""
        req = urllib.request.Request(f"{SAAS_BASE}/docs")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200

    def test_saas_leads(self):
        """SaaS: lead capture."""
        code, data, _ = api("POST", "/api/leads/capture", {
            "email": "lead@e2e.com", "source": "e2e_test",
        })
        assert code == 201
        assert data["success"]

    def test_rate_limiting(self):
        """SaaS: rate limiting on register (MUST run last)."""
        got_429 = False
        for i in range(15):
            code, _, _ = api("POST", "/api/auth/register", {
                "email": f"rl{i}_{int(time.time())}@test.com",
                "password": "test123",
                "name": f"RL{i}",
            })
            if code == 429:
                got_429 = True
                break
        assert got_429, "Rate limiting never triggered"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
