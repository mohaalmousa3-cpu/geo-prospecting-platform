"""`result.job_id` and `provenance.job_id`: ON DELETE CASCADE -> RESTRICT (owner option B, 2026-10-06).

A raw `DELETE FROM job` no longer removes result or provenance records silently; it fails with 23503 until
those rows are deleted explicitly. The application guard (`409 has_results`) stays; this is the second line.
`TRUNCATE ... CASCADE`, DROP and similar administrative operations are outside any foreign-key protection.

Upgrade re-validates existing rows (no data change). Downgrade restores CASCADE; it changes no rows and loses
nothing, but it deliberately re-opens the silent-cascade behaviour.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_TABLES = (("result", "result_job_id_fkey"), ("provenance", "provenance_job_id_fkey"))


def _replace(action: str) -> None:
    for table, name in _TABLES:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY (job_id) REFERENCES job (id) {action}"
        )


def upgrade() -> None:
    _replace("ON DELETE RESTRICT ON UPDATE RESTRICT")


def downgrade() -> None:
    _replace("ON DELETE CASCADE")
