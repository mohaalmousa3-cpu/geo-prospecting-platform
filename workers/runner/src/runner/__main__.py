from __future__ import annotations

import logging
import os
import signal
import socket
import uuid

from geo_common.config import get_settings
from geo_common.db import make_engine
from geo_common.logging_setup import configure_logging
from geo_common.queue_pg import PostgresJobQueue
from runner.loop import Runner


def main() -> None:
    s = get_settings()
    configure_logging(s.LOG_LEVEL)
    queue = PostgresJobQueue(
        make_engine(s.database_url, pool_size=2),
        max_queued_jobs=s.MAX_QUEUED_JOBS,
        default_max_attempts=s.JOB_MAX_ATTEMPTS,
    )
    runner = Runner(
        queue,
        worker_id=f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}",
        lease_seconds=s.JOB_LEASE_SECONDS,
        poll_interval=s.WORKER_POLL_INTERVAL_SECONDS,
        job_timeout=s.JOB_TIMEOUT_SECONDS,
    )
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: runner.stop_event.set())
    if s.WORKER_CONCURRENCY != 1:
        logging.getLogger("runner").warning("WORKER_CONCURRENCY>1 not supported in Phase 1; running 1")
    runner.run_forever()


if __name__ == "__main__":
    main()
