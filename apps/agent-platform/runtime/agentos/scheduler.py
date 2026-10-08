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

    scheduled = [a for a in roster.agents.values() if a.schedule]
    log.info("scheduler tracking %d of %d agents", len(scheduled), len(roster.agents))

    while True:
        now = datetime.now(TZ)
        for agent in scheduled:
            last = r.hget(LAST_FIRE_KEY, agent.id)
            if last is None:
                # First sight of this agent: start counting from now, don't backfill.
                r.hset(LAST_FIRE_KEY, agent.id, now.isoformat())
                continue
            due = croniter(agent.schedule, datetime.fromisoformat(last)).get_next(datetime)
            if due <= now:
                r.hset(LAST_FIRE_KEY, agent.id, now.isoformat())
                if queue.is_paused(r):
                    log.info("paused: skipping %s", agent.id)
                    continue
                task_id = queue.enqueue(conn, r, agent.id, agent.task, source="schedule")
                log.info("scheduled task #%d for %s", task_id, agent.id)
        time.sleep(TICK_SECONDS)
