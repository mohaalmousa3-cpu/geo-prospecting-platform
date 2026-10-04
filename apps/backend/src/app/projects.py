"""Project persistence. A project is a named container for AOIs (and, later, jobs and outputs)."""

# ruff: noqa: S608  (f-strings interpolate only the module constant _COLS; all values are bound)

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

_ADVISORY_KEY = 7_000_003  # serialises count+insert so MAX_PROJECTS cannot be overshot

_COLS = (
    "p.id, p.name, p.description, p.created_at, "
    "(SELECT count(*) FROM aoi a WHERE a.project_id = p.id)::int AS aoi_count"
)


class ProjectLimitReachedError(Exception):
    def __init__(self, limit: int) -> None:
        super().__init__(f"project limit reached: MAX_PROJECTS={limit}")
        self.limit = limit


class ProjectNotFoundError(Exception):
    pass


class ProjectNotEmptyError(Exception):
    def __init__(self, aoi_count: int) -> None:
        super().__init__(f"project still contains {aoi_count} AOI(s)")
        self.aoi_count = aoi_count


class ProjectRepository:
    def __init__(self, engine: Engine, max_projects: int) -> None:
        self._engine = engine
        self._max = max_projects

    def create(self, name: str, description: str | None) -> dict[str, Any]:
        with self._engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_KEY})
            if conn.execute(text("SELECT count(*) FROM project")).scalar_one() >= self._max:
                raise ProjectLimitReachedError(self._max)
            new_id = conn.execute(
                text("INSERT INTO project (name, description) VALUES (:n, :d) RETURNING id"),
                {"n": name, "d": description},
            ).scalar_one()
            row = conn.execute(text(f"SELECT {_COLS} FROM project p WHERE p.id=:i"), {"i": new_id}).one()
        return dict(row._mapping)

    def get(self, project_id: UUID) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT {_COLS} FROM project p WHERE p.id=:i"), {"i": project_id}
            ).first()
        return None if row is None else dict(row._mapping)

    def list(self) -> tuple[list[dict[str, Any]], int]:
        with self._engine.connect() as conn:
            rows = conn.execute(text(f"SELECT {_COLS} FROM project p ORDER BY p.created_at, p.id")).all()
        items = [dict(r._mapping) for r in rows]
        return items, len(items)

    def exists(self, project_id: UUID) -> bool:
        with self._engine.connect() as conn:
            return (
                conn.execute(text("SELECT 1 FROM project WHERE id=:i"), {"i": project_id}).first() is not None
            )

    def delete(self, project_id: UUID, *, delete_aois: bool) -> None:
        """Delete a project. Refuses (ProjectNotEmptyError) unless `delete_aois` when AOIs remain."""
        with self._engine.begin() as conn:
            if (
                conn.execute(text("SELECT 1 FROM project WHERE id=:i FOR UPDATE"), {"i": project_id}).first()
                is None
            ):
                raise ProjectNotFoundError(str(project_id))
            n = conn.execute(
                text("SELECT count(*) FROM aoi WHERE project_id=:i"), {"i": project_id}
            ).scalar_one()
            if n and not delete_aois:
                raise ProjectNotEmptyError(n)
            conn.execute(text("DELETE FROM aoi WHERE project_id=:i"), {"i": project_id})
            conn.execute(text("DELETE FROM project WHERE id=:i"), {"i": project_id})
