"""chm demo — Show CHM capabilities without needing a real repo.

Generates a demo git repo with realistic data and runs a full analysis.
Perfect for first-time users who just ran `pip install chm-cli`.
"""

import tempfile
import subprocess
import os
from pathlib import Path
from datetime import datetime


DEMO_COMMITS = [
    # (date, author, email, message, file_changes)
    ("2026-01-10 09:00", "Alice Chen", "alice@company.com",
     "feat: initial project scaffold",
     {"src/main.py": "+12", "src/config.py": "+8", "README.md": "+5"}),
    ("2026-01-12 14:30", "Bob Wang", "bob@company.com",
     "feat: add user authentication module",
     {"src/auth.py": "+45", "src/models.py": "+30", "src/main.py": "+3"}),
    ("2026-01-15 10:00", "Alice Chen", "alice@company.com",
     "feat: implement payment processing",
     {"src/payment.py": "+85", "src/models.py": "+12", "tests/test_payment.py": "+40"}),
    ("2026-01-18 16:00", "Bob Wang", "bob@company.com",
     "fix: handle edge cases in auth",
     {"src/auth.py": "+15,-8", "tests/test_auth.py": "+25"}),
    ("2026-01-22 09:30", "Carol Li", "carol@company.com",
     "feat: add email notification system",
     {"src/notify.py": "+60", "src/config.py": "+5"}),
    ("2026-01-25 11:00", "Alice Chen", "alice@company.com",
     "refactor: extract database layer",
     {"src/database.py": "+50", "src/models.py": "-30,+10", "src/auth.py": "-5,+3"}),
    ("2026-01-28 15:45", "Bob Wang", "bob@company.com",
     "feat: add rate limiting middleware",
     {"src/middleware.py": "+35", "src/config.py": "+8", "tests/test_middleware.py": "+30"}),
    ("2026-02-01 08:00", "Carol Li", "carol@company.com",
     "fix: notification template rendering",
     {"src/notify.py": "+20,-12", "tests/test_notify.py": "+18"}),
    ("2026-02-05 13:00", "Alice Chen", "alice@company.com",
     "refactor: switch to async payment processing",
     {"src/payment.py": "-40,+65", "src/main.py": "+10,-5", "tests/test_payment.py": "+20,-15"}),
    ("2026-02-10 17:00", "Bob Wang", "bob@company.com",
     "feat: add API key management",
     {"src/apikeys.py": "+55", "src/middleware.py": "+10", "tests/test_apikeys.py": "+35"}),
    ("2026-02-14 10:00", "Alice Chen", "alice@company.com",
     "docs: add API documentation",
     {"docs/API.md": "+45", "README.md": "+10"}),
    ("2026-02-20 14:00", "Carol Li", "carol@company.com",
     "feat: webhook support",
     {"src/webhooks.py": "+70", "src/config.py": "+3", "tests/test_webhooks.py": "+42"}),
    ("2026-03-01 09:00", "Alice Chen", "alice@company.com",
     "refactor: payment module cleanup — extract Stripe adapter",
     {"src/payment.py": "+35,-20", "src/stripe_adapter.py": "+48"}),
    ("2026-03-10 16:00", "Bob Wang", "bob@company.com",
     "fix: auth token expiry edge case",
     {"src/auth.py": "+8,-3", "tests/test_auth.py": "+12"}),
    ("2026-03-20 11:00", "Carol Li", "carol@company.com",
     "feat: notification batching and retry",
     {"src/notify.py": "+40,-15", "src/config.py": "+2", "tests/test_notify.py": "+15"}),
    ("2026-04-01 08:00", "Alice Chen", "alice@company.com",
     "refactor: middleware chain optimization",
     {"src/middleware.py": "+25,-18", "src/main.py": "+5"}),
    ("2026-04-15 13:00", "Bob Wang", "bob@company.com",
     "feat: audit logging",
     {"src/audit.py": "+42", "src/middleware.py": "+8"}),
    ("2026-04-28 10:00", "Carol Li", "carol@company.com",
     "fix: webhook signature verification",
     {"src/webhooks.py": "+12,-5", "tests/test_webhooks.py": "+8"}),
    ("2026-05-10 09:00", "Alice Chen", "alice@company.com",
     "perf: optimize database connection pooling",
     {"src/database.py": "+20,-12"}),
    ("2026-05-25 15:00", "Bob Wang", "bob@company.com",
     "feat: add GraphQL API endpoint",
     {"src/graphql.py": "+95", "src/main.py": "+8", "tests/test_graphql.py": "+55"}),
    ("2026-06-01 10:00", "Alice Chen", "alice@company.com",
     "refactor: final cleanup before v1.0",
     {"src/payment.py": "-15,+8", "src/auth.py": "-5,+2"}),
    ("2026-06-10 14:00", "Carol Li", "carol@company.com",
     "docs: deployment guide and runbook",
     {"docs/DEPLOY.md": "+60", "README.md": "+15"}),
    ("2026-06-15 09:00", "Bob Wang", "bob@company.com",
     "chore: update dependencies and CI config",
     {".github/workflows/ci.yml": "+30", "requirements.txt": "+3,-2"}),
]


def create_demo_repo() -> str:
    """Create a demo git repo and return its path."""
    repo_dir = Path(tempfile.mkdtemp(prefix="chm-demo-"))
    os.chdir(repo_dir)
    subprocess.run(["git", "init"], capture_output=True)

    for date_str, author, email, message, changes in DEMO_COMMITS:
        # Set author
        subprocess.run(["git", "config", "user.name", author])
        subprocess.run(["git", "config", "user.email", email])

        # Create/modify files
        for filepath, change_spec in changes.items():
            full_path = repo_dir / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Simple: just append lines to simulate growth
            if "+" in change_spec:
                adds = int(change_spec.split("+")[1].split(",")[0] if "," in change_spec else change_spec.split("+")[1])
                content = f"# {filepath}\n" + "\n".join(
                    f"def {Path(filepath).stem}_func_{i}(): pass"
                    for i in range(max(adds // 2, 1))
                )
                full_path.write_text(content + "\n")

        # Commit
        subprocess.run(["git", "add", "-A"], capture_output=True)
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = date_str
        env["GIT_COMMITTER_DATE"] = date_str
        subprocess.run(["git", "commit", "-m", message],
                       capture_output=True, env=env)

    return str(repo_dir)
