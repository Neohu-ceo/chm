"""CI/CD integration — generate workflow configs and install git hooks."""

from pathlib import Path

GITHUB_ACTIONS_WORKFLOW = """name: Code Health Check
on: [push, pull_request]
jobs:
  health:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: {fetch-depth: 500}
      - uses: actions/setup-python@v5
        with: {python-version: '3.12'}
      - run: pip install chm-cli
      - run: chm snapshot .
      - run: chm diff . --ci
      - run: chm badge . -o badge.svg
      - uses: actions/upload-artifact@v4
        with: {name: health-badge, path: badge.svg}
"""

PRE_COMMIT_HOOK = """#!/bin/bash
# CHM pre-commit health check
chm snapshot . --max-commits 50 2>/dev/null
echo "🏠 CHM: health snapshot saved"
"""


def generate_github_actions() -> str:
    """Generate a GitHub Actions workflow file content."""
    return GITHUB_ACTIONS_WORKFLOW.strip()


def install_precommit_hook(repo_path: str) -> bool:
    """Install CHM as a pre-commit hook."""
    hooks_dir = Path(repo_path) / ".git" / "hooks"
    if not hooks_dir.exists():
        return False

    hook_path = hooks_dir / "pre-commit"
    existing = hook_path.read_text() if hook_path.exists() else ""

    if "chm snapshot" in existing:
        return True  # Already installed

    content = existing + "\n" + PRE_COMMIT_HOOK if existing else "#!/bin/bash\n" + PRE_COMMIT_HOOK
    hook_path.write_text(content)
    hook_path.chmod(0o755)
    return True


def uninstall_precommit_hook(repo_path: str) -> bool:
    """Remove CHM from pre-commit hook."""
    hook_path = Path(repo_path) / ".git" / "hooks" / "pre-commit"
    if not hook_path.exists():
        return False

    content = hook_path.read_text()
    content = "\n".join(l for l in content.split("\n") if "chm snapshot" not in l)
    hook_path.write_text(content)
    return True
