"""Redis work queue plus the fleet-wide kill switch."""

import os

import redis

QUEUE_KEY = "agentos:queue"
PAUSED_KEY = "agentos:paused"


def connect() -> redis.Redis:
    return redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


def push(r: redis.Redis, task_id: int) -> None:
    r.rpush(QUEUE_KEY, task_id)


def pop(r: redis.Redis, timeout: int = 5) -> int | None:
    item = r.blpop([QUEUE_KEY], timeout=timeout)
    return int(item[1]) if item else None


def is_paused(r: redis.Redis) -> bool:
    return r.exists(PAUSED_KEY) == 1


def set_paused(r: redis.Redis, paused: bool) -> None:
    if paused:
        r.set(PAUSED_KEY, "1")
    else:
        r.delete(PAUSED_KEY)


def enqueue(conn, r: redis.Redis, agent: str, input: str, **kwargs) -> int:
    """Persist the task first so a Redis restart never loses work, then queue it."""
    from . import db

    task_id = db.create_task(conn, agent, input, **kwargs)
    push(r, task_id)
    return task_id
