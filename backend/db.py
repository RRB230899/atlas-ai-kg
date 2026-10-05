"""Postgres connection shared by the API, the ingestion scripts and the indexers.

Settings come from the environment. The documented names are the DB_* ones in
.env.example. The older POSTGRES_* names are still read first, so an existing
local .env keeps working.
"""
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def _setting(legacy_name: str, name: str, default: str | None = None) -> str | None:
    return os.getenv(legacy_name) or os.getenv(name) or default


def get_conn():
    return psycopg2.connect(
        dbname=_setting("POSTGRES_DBNAME", "DB_NAME", "atlas"),
        user=_setting("POSTGRES_USER", "DB_USER", "postgres"),
        password=_setting("POSTGRES_PASSWORD", "DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
    )
