"""Staged data assets, storage tombstones, nullable provenance link (ADR-0014 §7.1–§7.2, §8; CP3).

* `provenance.job_id` becomes NULLable (owner decision, option A, 2026-10-05). `result.job_id` stays
  NOT NULL: result rows are scientific-result records and always need a job. Staged assets may carry
  provenance without a job link where the model allows it. This relaxes no rule about scientific
  results.
* `data_asset`: inputs, not results (no confidence/score/interpretation). Foreign keys are immediate
  (non-deferrable) and RESTRICT; `(job_id, kind, request_hash)` is unique for job-bound assets only
  (idempotency of the publication request, not scientific deduplication); `storage_key` is unique and
  immutable (trigger).
* `storage_tombstone`: keys of files whose rows were deleted, awaiting post-commit cleanup.

Downgrade refuses (and says why) if it would destroy or invalidate data.

Revision ID: 0005
Revises: 0004
"""

from alembic import op
from sqlalchemy import text

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE provenance ALTER COLUMN job_id DROP NOT NULL")
    op.execute(
        """
        CREATE TABLE data_asset (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id uuid NOT NULL,
            aoi_id uuid NOT NULL,
            job_id uuid,
            kind text NOT NULL,
            storage_key text NOT NULL,
            media_type text NOT NULL,
            size_bytes bigint NOT NULL,
            sha256 text NOT NULL,
            request_hash text NOT NULL,
            provenance_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT data_asset_kind_known CHECK (kind IN ('scene_catalog', 'dem_clip', 'user_vector')),
            CONSTRAINT data_asset_size_nonnegative CHECK (size_bytes >= 0),
            CONSTRAINT data_asset_sha256_hex CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT data_asset_request_hash_format CHECK (request_hash ~ '^v[0-9]+:[0-9a-f]{64}$'),
            CONSTRAINT data_asset_storage_key_key UNIQUE (storage_key),
            CONSTRAINT data_asset_provenance_key UNIQUE (provenance_id),
            CONSTRAINT data_asset_provenance_fk FOREIGN KEY (provenance_id)
                REFERENCES provenance (id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            CONSTRAINT data_asset_aoi_project_fk FOREIGN KEY (aoi_id, project_id)
                REFERENCES aoi (id, project_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            CONSTRAINT data_asset_job_fk FOREIGN KEY (job_id, aoi_id, project_id)
                REFERENCES job (id, aoi_id, project_id) ON DELETE RESTRICT ON UPDATE RESTRICT
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX data_asset_job_request_key ON data_asset (job_id, kind, request_hash) "
        "WHERE job_id IS NOT NULL"
    )
    op.execute("CREATE INDEX data_asset_aoi_idx ON data_asset (aoi_id)")
    op.execute("CREATE INDEX data_asset_job_idx ON data_asset (job_id) WHERE job_id IS NOT NULL")
    op.execute(
        """
        CREATE FUNCTION data_asset_storage_key_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.storage_key IS DISTINCT FROM OLD.storage_key THEN
                RAISE EXCEPTION 'data_asset.storage_key is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER data_asset_storage_key_immutable BEFORE UPDATE OF storage_key ON data_asset "
        "FOR EACH ROW EXECUTE FUNCTION data_asset_storage_key_immutable()"
    )
    op.execute(
        """
        CREATE TABLE storage_tombstone (
            storage_key text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            last_error text,
            CONSTRAINT storage_tombstone_pkey PRIMARY KEY (storage_key)
        )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    counts = bind.execute(
        text(
            "SELECT (SELECT count(*) FROM data_asset), (SELECT count(*) FROM storage_tombstone), "
            "(SELECT count(*) FROM provenance WHERE job_id IS NULL)"
        )
    ).one()
    if any(counts):
        raise RuntimeError(
            f"migration 0005 downgrade aborted: it would destroy {counts[0]} data_asset row(s) and "
            f"{counts[1]} storage_tombstone row(s) (their files would become orphans) and cannot "
            f"restore "
            f"NOT NULL on provenance.job_id while {counts[2]} provenance row(s) have no job. "
            "Delete the assets through the API (which drains tombstones) and the job-less "
            "provenance rows, "
            "then re-run."
        )
    op.execute("DROP TABLE storage_tombstone")
    op.execute("DROP TRIGGER data_asset_storage_key_immutable ON data_asset")
    op.execute("DROP FUNCTION data_asset_storage_key_immutable()")
    op.execute("DROP TABLE data_asset")
    op.execute("ALTER TABLE provenance ALTER COLUMN job_id SET NOT NULL")
