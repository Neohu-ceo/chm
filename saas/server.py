#!/usr/bin/env python3
"""Production WSGI server for Lighthouse Analytics SaaS.

Uses waitress (pure Python, production-ready) instead of Flask dev server.
Start with: python server.py
"""

import os
import sys

# Ensure the saas directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

from waitress import serve
from app import app

PORT = int(os.getenv("PORT", "5001"))
HOST = os.getenv("HOST", "0.0.0.0")
THREADS = int(os.getenv("THREADS", "4"))

# Production config — no debug, no reloader
app.config["DEBUG"] = False
app.config["ENV"] = "production"

print(f"""
╔══════════════════════════════════════════════╗
║  🏠  Lighthouse Analytics — Production      ║
║                                              ║
║  Server:  waitress (production WSGI)         ║
║  Host:    {HOST}:{PORT}                       ║
║  Threads: {THREADS}                                ║
║  Status:  Starting...                        ║
╚══════════════════════════════════════════════╝
""")

if __name__ == "__main__":
    serve(app, host=HOST, port=PORT, threads=THREADS)
