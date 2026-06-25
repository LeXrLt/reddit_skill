"""
Reddit skill configuration.
Values are loaded from environment variables (via .env).
"""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── PostgreSQL ──────────────────────────────────────────────
POSTGRES_HOST     = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT     = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER     = os.getenv("POSTGRES_USER", "hub_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "hub_password")
POSTGRES_DB       = os.getenv("POSTGRES_DB", "financial_hub")

POSTGRES_READONLY_USER     = os.getenv("POSTGRES_READONLY_USER", "hub_readonly")
POSTGRES_READONLY_PASSWORD = os.getenv("POSTGRES_READONLY_PASSWORD", "hub_password")

# ── Crawler identity ────────────────────────────────────────
COMPONENT_NAME = "reddit_crawler"

# ── Reddit HTTP defaults ─────────────────────────────────────
USER_AGENT   = os.getenv("REDDIT_USER_AGENT", "script:clawdbot-reddit-readonly:v1.0.0")
MIN_DELAY_MS = int(os.getenv("REDDIT_MIN_DELAY_MS", "500"))
MAX_DELAY_MS = int(os.getenv("REDDIT_MAX_DELAY_MS", "1500"))
TIMEOUT_MS   = int(os.getenv("REDDIT_TIMEOUT_MS", "20000"))
MAX_RETRIES  = int(os.getenv("REDDIT_MAX_RETRIES", "3"))
