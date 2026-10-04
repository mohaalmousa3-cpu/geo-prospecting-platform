"""Database helpers: engine factory and programmatic migrations."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine


def make_engine(url: str, *, pool_size: int = 5) -> Engine:
    return create_engine(url, pool_pre_ping=True, pool_size=pool_size, future=True)


def _alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade_head(url: str, revision: str = "head") -> None:
    command.upgrade(_alembic_config(url), revision)


def downgrade_base(url: str, revision: str = "base") -> None:
    command.downgrade(_alembic_config(url), revision)
