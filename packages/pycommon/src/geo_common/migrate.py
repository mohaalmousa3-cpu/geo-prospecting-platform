"""`python -m geo_common.migrate` — apply migrations using the shared settings."""

from geo_common.config import get_settings
from geo_common.db import upgrade_head

if __name__ == "__main__":
    upgrade_head(get_settings().database_url)
