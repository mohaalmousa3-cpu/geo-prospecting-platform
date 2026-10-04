"""Initial schema: PostGIS, aoi, job (the queue), result, provenance.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(
        """
        CREATE TABLE aoi (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name text NOT NULL,
            geom geometry(Polygon, 4326) NOT NULL,
            source text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX aoi_geom_gix ON aoi USING gist (geom)")
    op.execute(
        """
        CREATE TABLE job (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            type text NOT NULL,
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','running','succeeded','failed','cancelled','insufficient_data')),
            priority integer NOT NULL DEFAULT 0,
            payload jsonb NOT NULL DEFAULT '{}'::jsonb,
            attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            max_attempts integer NOT NULL DEFAULT 2 CHECK (max_attempts >= 1),
            locked_by text,
            lease_expires_at timestamptz,
            cancel_requested boolean NOT NULL DEFAULT false,
            error text,
            created_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz,
            finished_at timestamptz
        )
        """
    )
    op.execute("CREATE INDEX job_claim_idx ON job (priority DESC, created_at) WHERE status = 'queued'")
    op.execute("CREATE INDEX job_lease_idx ON job (lease_expires_at) WHERE status = 'running'")
    op.execute(
        """
        CREATE TABLE result (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id uuid NOT NULL REFERENCES job(id) ON DELETE CASCADE,
            kind text NOT NULL,
            envelope jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE provenance (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id uuid NOT NULL REFERENCES job(id) ON DELETE CASCADE,
            record jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS provenance")
    op.execute("DROP TABLE IF EXISTS result")
    op.execute("DROP TABLE IF EXISTS job")
    op.execute("DROP TABLE IF EXISTS aoi")
