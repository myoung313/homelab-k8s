"""Postgres state: tasks, outputs, approvals, memory, and spend."""

import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          BIGSERIAL PRIMARY KEY,
    agent       TEXT NOT NULL,
    input       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'queued',  -- queued|running|done|failed|skipped
    parent_id   BIGINT REFERENCES tasks(id),
    depth       INT NOT NULL DEFAULT 0,
    source      TEXT NOT NULL DEFAULT 'manual',  -- manual|schedule|handoff|api
    result      TEXT,
    cost_usd    NUMERIC(10, 4) NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS tasks_status_idx ON tasks (status, created_at);

CREATE TABLE IF NOT EXISTS outputs (
    id         BIGSERIAL PRIMARY KEY,
    task_id    BIGINT NOT NULL REFERENCES tasks(id),
    agent      TEXT NOT NULL,
    kind       TEXT NOT NULL,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Agents never act on the outside world directly. They file approvals; a human
-- approves in the console; n8n executes approved rows and sets executed_at.
CREATE TABLE IF NOT EXISTS approvals (
    id          BIGSERIAL PRIMARY KEY,
    task_id     BIGINT NOT NULL REFERENCES tasks(id),
    agent       TEXT NOT NULL,
    action      TEXT NOT NULL,
    summary     TEXT NOT NULL,
    payload     JSONB NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at  TIMESTAMPTZ,
    executed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS memory (
    id         BIGSERIAL PRIMARY KEY,
    agent      TEXT NOT NULL,
    note       TEXT NOT NULL,
    tsv        TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', note)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS memory_tsv_idx ON memory USING GIN (tsv);
"""


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, autocommit=True)


def migrate(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA)


def create_task(conn, agent: str, input: str, source: str = "manual",
                parent_id: int | None = None, depth: int = 0) -> int:
    row = conn.execute(
        "INSERT INTO tasks (agent, input, source, parent_id, depth) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (agent, input, source, parent_id, depth),
    ).fetchone()
    return row["id"]


def claim_task(conn, task_id: int) -> dict | None:
    """Atomically move a queued task to running. Returns None if already claimed."""
    return conn.execute(
        "UPDATE tasks SET status = 'running', started_at = now() "
        "WHERE id = %s AND status = 'queued' RETURNING *",
        (task_id,),
    ).fetchone()


def add_cost(conn, task_id: int, usd: float) -> None:
    """Record spend per model call so running tasks count against today's budget."""
    conn.execute("UPDATE tasks SET cost_usd = cost_usd + %s WHERE id = %s", (round(usd, 4), task_id))


def finish_task(conn, task_id: int, status: str, result: str) -> None:
    conn.execute(
        "UPDATE tasks SET status = %s, result = %s, finished_at = now() WHERE id = %s",
        (status, result, task_id),
    )


def queued_task_ids(conn) -> list[int]:
    return [r["id"] for r in conn.execute(
        "SELECT id FROM tasks WHERE status = 'queued' ORDER BY id").fetchall()]


def spent_today(conn, agent: str | None = None) -> float:
    query = "SELECT COALESCE(SUM(cost_usd), 0) AS usd FROM tasks WHERE created_at >= date_trunc('day', now())"
    params: tuple = ()
    if agent:
        query += " AND agent = %s"
        params = (agent,)
    return float(conn.execute(query, params).fetchone()["usd"])


def save_output(conn, task_id: int, agent: str, kind: str, title: str, body: str) -> int:
    return conn.execute(
        "INSERT INTO outputs (task_id, agent, kind, title, body) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (task_id, agent, kind, title, body),
    ).fetchone()["id"]


def request_approval(conn, task_id: int, agent: str, action: str, summary: str, payload: dict) -> int:
    return conn.execute(
        "INSERT INTO approvals (task_id, agent, action, summary, payload) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (task_id, agent, action, summary, Jsonb(payload)),
    ).fetchone()["id"]


def decide_approval(conn, approval_id: int, approved: bool) -> bool:
    row = conn.execute(
        "UPDATE approvals SET status = %s, decided_at = now() "
        "WHERE id = %s AND status = 'pending' RETURNING id",
        ("approved" if approved else "rejected", approval_id),
    ).fetchone()
    return row is not None


def remember(conn, agent: str, note: str) -> None:
    conn.execute("INSERT INTO memory (agent, note) VALUES (%s, %s)", (agent, note))


def recall(conn, query: str, limit: int = 8) -> list[dict]:
    return conn.execute(
        "SELECT agent, note, created_at FROM memory "
        "WHERE tsv @@ websearch_to_tsquery('english', %s) "
        "ORDER BY ts_rank(tsv, websearch_to_tsquery('english', %s)) DESC, created_at DESC LIMIT %s",
        (query, query, limit),
    ).fetchall()


def recent_activity(conn, hours: int) -> dict:
    hours = max(1, min(hours, 24 * 14))
    window = (f"{hours} hours",)
    return {
        "tasks": conn.execute(
            "SELECT id, agent, status, source, cost_usd::float AS cost_usd, left(result, 300) AS result "
            "FROM tasks WHERE created_at >= now() - %s::interval ORDER BY id DESC LIMIT 60", window).fetchall(),
        "outputs": conn.execute(
            "SELECT id, agent, kind, title FROM outputs "
            "WHERE created_at >= now() - %s::interval ORDER BY id DESC LIMIT 40", window).fetchall(),
        "approvals": conn.execute(
            "SELECT agent, action, status, count(*) AS n FROM approvals "
            "WHERE created_at >= now() - %s::interval GROUP BY 1, 2, 3", window).fetchall(),
    }
