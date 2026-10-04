"""AOI bookkeeping columns (Phase 2). No scientific fields.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE aoi ADD COLUMN area_km2 double precision NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE aoi ADD COLUMN vertex_count integer NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE aoi ADD COLUMN working_crs text NOT NULL DEFAULT 'EPSG:4326'")
    op.execute("ALTER TABLE aoi ADD COLUMN details jsonb NOT NULL DEFAULT '{}'::jsonb")
    for col in ("area_km2", "vertex_count", "working_crs"):
        op.execute(f"ALTER TABLE aoi ALTER COLUMN {col} DROP DEFAULT")
    op.execute("ALTER TABLE aoi ADD CONSTRAINT aoi_geom_valid CHECK (ST_IsValid(geom))")
    op.execute("ALTER TABLE aoi ADD CONSTRAINT aoi_area_positive CHECK (area_km2 > 0)")
    op.execute(
        "ALTER TABLE aoi ADD CONSTRAINT aoi_source_known CHECK "
        "(source IN ('point_radius','rectangle','polygon','geojson','kml','kmz','shapefile'))"
    )


def downgrade() -> None:
    for c in ("aoi_source_known", "aoi_area_positive", "aoi_geom_valid"):
        op.execute(f"ALTER TABLE aoi DROP CONSTRAINT {c}")
    for col in ("details", "working_crs", "vertex_count", "area_km2"):
        op.execute(f"ALTER TABLE aoi DROP COLUMN {col}")
