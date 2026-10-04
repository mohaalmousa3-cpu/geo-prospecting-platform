"""Projects (Phase 2.5): the container that owns AOIs (and, later, jobs and outputs).

AOIs saved before this migration are moved into a 'Default project' so the NOT NULL
constraint can be applied without losing data. No scientific fields.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE project (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
            description text CHECK (description IS NULL OR char_length(description) <= 500),
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE aoi ADD COLUMN project_id uuid REFERENCES project(id) ON DELETE RESTRICT")
    op.execute(
        "INSERT INTO project (name, description) SELECT 'Default project', "
        "'Created by migration 0003 for AOIs saved before projects existed' "
        "WHERE EXISTS (SELECT 1 FROM aoi)"
    )
    op.execute("UPDATE aoi SET project_id = (SELECT id FROM project ORDER BY created_at LIMIT 1)")
    op.execute("ALTER TABLE aoi ALTER COLUMN project_id SET NOT NULL")
    op.execute("CREATE INDEX aoi_project_idx ON aoi (project_id)")


def downgrade() -> None:
    op.execute("DROP INDEX aoi_project_idx")
    op.execute("ALTER TABLE aoi DROP COLUMN project_id")
    op.execute("DROP TABLE project")
