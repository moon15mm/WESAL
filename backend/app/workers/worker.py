"""Outbox worker: delivers email/SMS/WhatsApp/push notifications with retries.

    python -m app.workers.worker
Several replicas can run in parallel (rows are claimed with FOR UPDATE SKIP LOCKED)."""
from __future__ import annotations

import logging
import signal
import time

from app.core.db import system_session
from app.main import configure_logging  # noqa: F401  (configures JSON logging)
from app.modules.notifications.service import deliver_pending

log = logging.getLogger("wesal.worker")
_running = True


def _stop(*_):
    global _running
    _running = False


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("worker started")
    while _running:
        try:
            with system_session() as db:
                n = deliver_pending(db)
        except Exception:  # noqa: BLE001
            log.exception("delivery loop failed")
            n = 0
        time.sleep(0.5 if n else 3)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
