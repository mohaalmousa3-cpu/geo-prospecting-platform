"""Job-to-AOI/project linkage (ADR-0014 §7.1–§7.3, Phase 3a).

* `aoi UNIQUE (id, project_id)` is the target of the composite foreign key.
* `job.aoi_id` / `job.project_id` are nullable; both or neither (CHECK); every non-`noop` job has both
  (CHECK); the composite FK (MATCH SIMPLE) forces `project_id` to equal that AOI's project; RESTRICT on
  delete and update.
* `UNIQUE (id, aoi_id, project_id)` is reserved as the target of the later asset→job consistency FK (0005).

The table is not assumed to contain only `noop` rows: if rows of another type exist the migration ABORTS and
lists them (no automatic AOI assignment, deletion or guessing). Alembic runs this in one transaction, so a
failed
run leaves nothing half-applied.

Revision ID: 0004
Revises: 0003
"""

from alembic import op
from sqlalchemy import text

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_LIST_LIMIT = 20


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        text("SELECT id, type, status FROM job WHERE type <> 'noop' ORDER BY created_at, id")
    ).all()
    if rows:
        shown = ", ".join(f"{r.id} (type={r.type}, status={r.status})" for r in rows[:_LIST_LIMIT])
        more = f" and {len(rows) - _LIST_LIMIT} more" if len(rows) > _LIST_LIMIT else ""
        raise RuntimeError(
            f"migration 0004 aborted: {len(rows)} job row(s) have type <> 'noop' and no trustworthy AOI: "
            f"{shown}{more}. Delete or otherwise resolve them explicitly, then re-run."
        )
    op.execute("ALTER TABLE aoi ADD CONSTRAINT aoi_id_project_id_key UNIQUE (id, project_id)")
    op.execute("ALTER TABLE job ADD COLUMN aoi_id uuid, ADD COLUMN project_id uuid")
    op.execute(
        "ALTER TABLE job ADD CONSTRAINT job_aoi_project_both_or_neither "
        "CHECK ((aoi_id IS NULL) = (project_id IS NULL)) NOT VALID"
    )
    op.execute(
        "ALTER TABLE job ADD CONSTRAINT job_non_noop_requires_aoi "
        "CHECK (type = 'noop' OR (aoi_id IS NOT NULL AND project_id IS NOT NULL)) NOT VALID"
    )
    op.execute("ALTER TABLE job VALIDATE CONSTRAINT job_aoi_project_both_or_neither")
    op.execute("ALTER TABLE job VALIDATE CONSTRAINT job_non_noop_requires_aoi")
    op.execute(
        "ALTER TABLE job ADD CONSTRAINT job_aoi_project_fk FOREIGN KEY (aoi_id, project_id) "
        "REFERENCES aoi (id, project_id) ON DELETE RESTRICT ON UPDATE RESTRICT"
    )
    op.execute("ALTER TABLE job ADD CONSTRAINT job_id_aoi_project_key UNIQUE (id, aoi_id, project_id)")
    op.execute("CREATE INDEX job_aoi_idx ON job (aoi_id) WHERE aoi_id IS NOT NULL")


def downgrade() -> None:
    # Dropping the columns discards any AOI/project linkage of jobs (documented data loss).
    op.execute("DROP INDEX job_aoi_idx")
    op.execute("ALTER TABLE job DROP CONSTRAINT job_id_aoi_project_key")
    op.execute("ALTER TABLE job DROP CONSTRAINT job_aoi_project_fk")
    op.execute("ALTER TABLE job DROP CONSTRAINT job_non_noop_requires_aoi")
    op.execute("ALTER TABLE job DROP CONSTRAINT job_aoi_project_both_or_neither")
    op.execute("ALTER TABLE job DROP COLUMN project_id, DROP COLUMN aoi_id")
    op.execute("ALTER TABLE aoi DROP CONSTRAINT aoi_id_project_id_key")
