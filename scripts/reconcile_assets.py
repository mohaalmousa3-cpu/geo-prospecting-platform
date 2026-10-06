#!/usr/bin/env python3
"""`make reconcile-assets`: drain pending tombstones, then REPORT (never repair or delete) inconsistencies.

Report-only by design (ADR-0014 §8): there is no delete mode for orphan files, no age rule and no flag that
enables one. Exit code 0 always means "the report was produced"; findings are listed, not enforced.
"""

from __future__ import annotations

import sys

from geo_common.assets_pg import drain_tombstones, reconcile_report
from geo_common.config import get_settings
from geo_common.db import make_engine
from geo_common.storage import LocalStorage


def main() -> int:
    s = get_settings()
    engine = make_engine(s.database_url, pool_size=1)
    storage = LocalStorage(s.STORAGE_LOCAL_PATH)
    drained = drain_tombstones(engine, storage)
    rep = reconcile_report(engine, storage)
    print(f"tombstones: removed={drained.removed} failed={drained.failed} remaining={rep.pending_tombstones}")
    print(f"unreferenced files (report only, nothing deleted): {len(rep.unreferenced_files)}")
    for k in rep.unreferenced_files:
        print(f"  {k}")
    print(f"asset rows whose file is missing (report only, nothing repaired): {len(rep.rows_missing_file)}")
    for i in rep.rows_missing_file:
        print(f"  asset {i}")
    stale = [x for x in rep.staging_files if x[2]]
    print(f"staging files: {len(rep.staging_files)} ({len(stale)} older than 24 h; report only)")
    for name, age, _ in rep.staging_files:
        print(f"  {name} age={int(age)}s")
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
