"""Queue consumer. Each thread pulls a task id from Redis, claims it in Postgres, and runs it."""

import logging
import os
import threading
import time

import anthropic

from . import db, queue, roster as roster_mod, runner

log = logging.getLogger(__name__)
CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "4"))


def _loop(n: int, roster) -> None:
    client = anthropic.Anthropic()
    conn = db.connect()
    r = queue.connect()
    log.info("worker thread %d ready", n)
    while True:
        if queue.is_paused(r):
            time.sleep(10)
            continue
        task_id = queue.pop(r)
        if task_id is None:
            continue
        task = db.claim_task(conn, task_id)
        if task is None:
            continue  # duplicate queue entry; another thread already ran it

        log.info("task #%d -> %s", task_id, task["agent"])
        try:
            status, result = runner.run(client, conn, r, roster, task)
        except anthropic.AuthenticationError:
            status, result = "failed", "Anthropic API key rejected. Check the agentos-secrets Secret."
        except anthropic.BadRequestError as e:
            status, result = "failed", f"Bad request: {e.message}"
        except anthropic.RateLimitError:
            status, result = "failed", "Rate limited after retries. Lower WORKER_CONCURRENCY or spread schedules."
        except anthropic.APIStatusError as e:
            status, result = "failed", f"API error {e.status_code}: {e.message}"
        except anthropic.APIConnectionError:
            status, result = "failed", "Could not reach the Anthropic API (check egress NetworkPolicy/DNS)."
        except Exception as e:  # keep the thread alive; the error is recorded on the task
            log.exception("task #%d crashed", task_id)
            status, result = "failed", f"Crashed: {e!r}"
        db.finish_task(conn, task_id, status, result)
        log.info("task #%d %s", task_id, status)


def main() -> None:
    roster = roster_mod.load()
    with db.connect() as conn:
        db.migrate(conn)
    threads = [threading.Thread(target=_loop, args=(i, roster), daemon=True) for i in range(CONCURRENCY)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
