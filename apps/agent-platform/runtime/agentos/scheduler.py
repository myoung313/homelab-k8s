"""Fires scheduled agents on their cron and re-queues work stranded by a Redis restart."""

import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from croniter import croniter

from . import db, queue, roster as roster_mod

log = logging.getLogger(__name__)
TZ = ZoneInfo(os.environ.get("TZ", "America/New_York"))
TICK_SECONDS = 30
LAST_FIRE_KEY = "agentos:last_fire"


def main() -> None:
    roster = roster_mod.load()
    conn = db.connect()
    db.migrate(conn)
    r = queue.connect()

    # Duplicates are harmless: workers claim atomically in Postgres.
    for task_id in db.queued_task_ids(conn):
        queue.push(r, task_id)

    # The first schedule keeps the plain agent id as its key so existing timers carry over.
    entries = [(a.id if i == 0 else f"{a.id}#{i}", a.id, cron, task)
               for a in roster.agents.values() for i, (cron, task) in enumerate(a.schedules)]
    log.info("scheduler tracking %d schedules across %d agents", len(entries), len(roster.agents))

    while True:
        now = datetime.now(TZ)
        for key, agent_id, cron, task in entries:
            last = r.hget(LAST_FIRE_KEY, key)
            if last is None:
                # First sight of this schedule: start counting from now, don't backfill.
                r.hset(LAST_FIRE_KEY, key, now.isoformat())
                continue
            due = croniter(cron, datetime.fromisoformat(last)).get_next(datetime)
            if due <= now:
                r.hset(LAST_FIRE_KEY, key, now.isoformat())
                if queue.is_paused(r):
                    log.info("paused: skipping %s", key)
                    continue
                task_id = queue.enqueue(conn, r, agent_id, task, source="schedule")
                log.info("scheduled task #%d for %s", task_id, key)
        time.sleep(TICK_SECONDS)
