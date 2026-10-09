"""Mission Control: a small web console for approvals, outputs, spend, and the kill switch.

Everything an agent writes is untrusted (it may echo web pages), so all of it is HTML-escaped.
"""

import base64
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import db, queue, roster as roster_mod, runner
from .avatars import CATALOG, RECRUIT, ROOMS

log = logging.getLogger(__name__)
USER = os.environ.get("CONSOLE_USER", "admin")
PASSWORD = os.environ["CONSOLE_PASSWORD"]
PORT = int(os.environ.get("CONSOLE_PORT", "8080"))
STATIC = Path(__file__).parent / "static"
PAGE_CSP = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'"
# The map is static HTML + JS; agent text reaches it only as JSON drawn on a canvas or set via textContent.
OFFICE_CSP = "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'"

STYLE = """
:root { --bg:#fff; --fg:#1d1d1f; --muted:#6b6b70; --line:#e3e3e6; --card:#f7f7f8; --accent:#2f6fde; --ok:#1f8a4c; --bad:#c23b3b; }
@media (prefers-color-scheme: dark) { :root { --bg:#151517; --fg:#ececee; --muted:#9a9aa1; --line:#2c2c30; --card:#1d1d20; --accent:#6f9cf0; --ok:#4cc27e; --bad:#ec6a6a; } }
* { box-sizing:border-box } body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.5 system-ui,sans-serif }
main { max-width:1100px; margin:0 auto; padding:16px } h1 { font-size:20px } h2 { font-size:16px; margin-top:28px }
a { color:var(--accent) } table { width:100%; border-collapse:collapse } td,th { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top }
th { color:var(--muted); font-weight:500 } .wrap { overflow-x:auto } .card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px; margin:8px 0 }
.stats { display:flex; gap:12px; flex-wrap:wrap } .stat { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 14px; min-width:140px }
.stat b { display:block; font-size:20px } pre { white-space:pre-wrap; word-break:break-word; margin:0 }
button { font:inherit; padding:5px 12px; border-radius:6px; border:1px solid var(--line); background:var(--bg); color:var(--fg); cursor:pointer }
.ok { color:var(--ok) } .bad { color:var(--bad) } select,textarea { font:inherit; width:100%; padding:6px; background:var(--bg); color:var(--fg); border:1px solid var(--line); border-radius:6px }
form.inline { display:inline }
"""


def page(title: str, body: str) -> bytes:
    return (f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)}</title><style>{STYLE}</style></head><body><main>{body}</main></body></html>").encode()


def post_button(action: str, label: str) -> str:
    return f"<form class=inline method=post action='{escape(action)}'><button>{escape(label)}</button></form>"


class Handler(BaseHTTPRequestHandler):
    roster = None      # active phase only
    roster_all = None  # every agent, so locked rooms can show what unlocks later

    def log_message(self, fmt, *args):
        log.info("%s %s", self.address_string(), fmt % args)

    # --- plumbing -----------------------------------------------------------
    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            user, _, pw = base64.b64decode(header[6:]).decode().partition(":")
        except ValueError:
            return False
        return hmac.compare_digest(user, USER) and hmac.compare_digest(pw, PASSWORD)

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin") or self.headers.get("Referer")
        return not origin or urlparse(origin).netloc == self.headers.get("Host")

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8", csp: str = PAGE_CSP) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", csp)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, to: str = "/") -> None:
        self.send_response(303)
        self.send_header("Location", to)
        self.end_headers()

    def _guard(self) -> bool:
        if self._authorized():
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="agentos"')
        self.end_headers()
        return False

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length", 0)))

    # --- routes -------------------------------------------------------------
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/healthz":
            return self._send(200, b"ok", "text/plain")
        if not self._guard():
            return
        if path == "/office":
            return self._send(200, (STATIC / "office.html").read_bytes(), csp=OFFICE_CSP)
        if path == "/office.js":
            return self._send(200, (STATIC / "office.js").read_bytes(), "text/javascript; charset=utf-8", OFFICE_CSP)
        parts = path.strip("/").split("/")
        with db.connect() as conn:
            if path == "/api/office":
                body = json.dumps(self.office_state(conn), default=str).encode()
                return self._send(200, body, "application/json")
            if path == "/":
                return self._send(200, self.dashboard(conn))
            if len(parts) == 2 and parts[0] == "outputs" and parts[1].isdigit():
                return self._send(*self.output_page(conn, int(parts[1])))
            if len(parts) == 2 and parts[0] == "tasks" and parts[1].isdigit():
                return self._send(*self.task_page(conn, int(parts[1])))
        self._send(404, page("Not found", "<h1>Not found</h1>"))

    def do_POST(self):
        if not self._guard():
            return
        path = urlparse(self.path).path
        parts = path.strip("/").split("/")
        r = queue.connect()
        with db.connect() as conn:
            if path == "/api/tasks":  # for n8n / scripts: {"agent": "...", "input": "..."}
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    return self._send(415, b'{"error":"json required"}', "application/json")
                data = json.loads(self._body() or b"{}")
                if data.get("agent") not in self.roster.agents or not data.get("input"):
                    return self._send(400, b'{"error":"unknown agent or empty input"}', "application/json")
                tid = queue.enqueue(conn, r, data["agent"], data["input"], source="api")
                return self._send(201, json.dumps({"id": tid}).encode(), "application/json")

            if not self._same_origin():
                return self._send(403, page("Forbidden", "<h1>Cross-origin request blocked</h1>"))
            if path == "/pause":
                queue.set_paused(r, True)
            elif path == "/resume":
                queue.set_paused(r, False)
            elif path == "/checkin":
                text = parse_qs(self._body().decode()).get("text", [""])[0].strip()
                if text:
                    db.add_checkin(conn, text[:1000])
            elif path == "/run":
                form = parse_qs(self._body().decode())
                agent, text = form.get("agent", [""])[0], form.get("input", [""])[0].strip()
                if agent in self.roster.agents and text:
                    queue.enqueue(conn, r, agent, text, source="manual")
            elif len(parts) == 3 and parts[0] == "approvals" and parts[1].isdigit() and parts[2] in ("approve", "reject"):
                db.decide_approval(conn, int(parts[1]), parts[2] == "approve")
            else:
                return self._send(404, page("Not found", "<h1>Not found</h1>"))
        self._redirect()

    # --- views --------------------------------------------------------------
    def office_state(self, conn) -> dict:
        return office_state(conn, self.roster, self.roster_all)

    def dashboard(self, conn) -> bytes:
        r = queue.connect()
        paused = queue.is_paused(r)
        spent = db.spent_today(conn)
        counts = {row["status"]: row["n"] for row in conn.execute(
            "SELECT status, count(*) AS n FROM tasks WHERE created_at >= now() - interval '24 hours' GROUP BY status")}
        pending = conn.execute("SELECT * FROM approvals WHERE status = 'pending' ORDER BY id").fetchall()
        outputs = conn.execute("SELECT id, agent, kind, title, created_at FROM outputs ORDER BY id DESC LIMIT 25").fetchall()
        tasks = conn.execute("SELECT id, agent, status, source, cost_usd, created_at FROM tasks ORDER BY id DESC LIMIT 25").fetchall()
        by_agent = conn.execute(
            "SELECT agent, count(*) AS n, sum(cost_usd) AS usd FROM tasks "
            "WHERE created_at >= date_trunc('day', now()) GROUP BY agent ORDER BY usd DESC").fetchall()

        stats = "".join(f"<div class=stat>{escape(k)}<b>{escape(str(v))}</b></div>" for k, v in [
            ("Spend today", f"${spent:.2f} / ${runner.GLOBAL_DAILY_BUDGET_USD:.0f}"),
            ("Pending approvals", len(pending)),
            ("Done (24h)", counts.get("done", 0)),
            ("Failed (24h)", counts.get("failed", 0)),
            ("Queued", counts.get("queued", 0) + counts.get("running", 0)),
            ("Agents", len(self.roster.agents)),
        ])
        switch = (f"<p class=bad><b>Fleet is PAUSED.</b> {post_button('/resume', 'Resume fleet')}</p>" if paused
                  else f"<p class=ok>Fleet is running. {post_button('/pause', 'Pause everything')}</p>")

        approvals = "".join(
            f"<div class=card><b>#{a['id']} · {escape(a['agent'])} → {escape(a['action'])}</b>"
            f"<p>{escape(a['summary'])}</p><pre>{escape(json.dumps(a['payload'], indent=2))}</pre><p>"
            f"{post_button(f'/approvals/{a['id']}/approve', 'Approve')} {post_button(f'/approvals/{a['id']}/reject', 'Reject')}"
            f" · <a href='/tasks/{a['task_id']}'>task #{a['task_id']}</a></p></div>"
            for a in pending) or "<p>Nothing waiting on you.</p>"

        out_rows = "".join(
            f"<tr><td><a href='/outputs/{o['id']}'>{escape(o['title'])}</a></td><td>{escape(o['kind'])}</td>"
            f"<td>{escape(o['agent'])}</td><td>{o['created_at']:%b %d %H:%M}</td></tr>" for o in outputs)
        task_rows = "".join(
            f"<tr><td><a href='/tasks/{t['id']}'>#{t['id']}</a></td><td>{escape(t['agent'])}</td>"
            f"<td class={'bad' if t['status'] == 'failed' else ''}>{escape(t['status'])}</td><td>{escape(t['source'])}</td>"
            f"<td>${t['cost_usd']:.3f}</td><td>{t['created_at']:%b %d %H:%M}</td></tr>" for t in tasks)
        spend_rows = "".join(
            f"<tr><td>{escape(s['agent'])}</td><td>{s['n']}</td><td>${s['usd']:.3f}</td>"
            f"<td>${self.roster.agents[s['agent']].budget_usd:.2f}</td></tr>"
            for s in by_agent if s["agent"] in self.roster.agents)
        options = "".join(f"<option>{escape(a)}</option>" for a in self.roster.agents)
        last = db.last_checkin(conn)
        last_line = (f"Last check-in {last['created_at']:%b %d %H:%M}: {escape(last['note'].split(': ', 1)[-1][:160])}"
                     if last else "No check-ins yet. Your accountability coach reads these.")

        return page("Mission Control", f"""
<h1>Mission Control</h1><p><a href='/office'>🏰 Open the dungeon map</a></p>{switch}<div class=stats>{stats}</div>
<h2>Waiting on you</h2>{approvals}
<h2>Daily check-in</h2>
<form method=post action=/checkin class=card><p>{last_line}</p>
<textarea name=text rows=2 placeholder="What did you get done today? e.g. approved 12 emails, sent 5 bids, 2 calls, booked 1 meeting"></textarea>
<p><button>Check in</button></p></form>
<h2>Run an agent</h2>
<form method=post action=/run class=card><select name=agent>{options}</select>
<p><textarea name=input rows=3 placeholder="What should it do?"></textarea></p><button>Queue task</button></form>
<h2>Latest outputs</h2><div class=wrap><table><tr><th>Title</th><th>Kind</th><th>Agent</th><th>When</th></tr>{out_rows}</table></div>
<h2>Latest tasks</h2><div class=wrap><table><tr><th>Task</th><th>Agent</th><th>Status</th><th>Source</th><th>Cost</th><th>When</th></tr>{task_rows}</table></div>
<h2>Spend today by agent</h2><div class=wrap><table><tr><th>Agent</th><th>Tasks</th><th>Spent</th><th>Daily cap</th></tr>{spend_rows}</table></div>
""")

    def output_page(self, conn, oid: int):
        o = conn.execute("SELECT * FROM outputs WHERE id = %s", (oid,)).fetchone()
        if not o:
            return 404, page("Not found", "<h1>Not found</h1>")
        return 200, page(o["title"], f"<p><a href='/'>← Mission Control</a></p><h1>{escape(o['title'])}</h1>"
                         f"<p>{escape(o['kind'])} · {escape(o['agent'])} · <a href='/tasks/{o['task_id']}'>task #{o['task_id']}</a></p>"
                         f"<div class=card><pre>{escape(o['body'])}</pre></div>")

    def task_page(self, conn, tid: int):
        t = conn.execute("SELECT * FROM tasks WHERE id = %s", (tid,)).fetchone()
        if not t:
            return 404, page("Not found", "<h1>Not found</h1>")
        outs = conn.execute("SELECT id, title FROM outputs WHERE task_id = %s ORDER BY id", (tid,)).fetchall()
        kids = conn.execute("SELECT id, agent, status FROM tasks WHERE parent_id = %s ORDER BY id", (tid,)).fetchall()
        links = "".join(f"<li><a href='/outputs/{o['id']}'>{escape(o['title'])}</a></li>" for o in outs) or "<li>none</li>"
        children = "".join(f"<li><a href='/tasks/{k['id']}'>#{k['id']}</a> {escape(k['agent'])} ({escape(k['status'])})</li>"
                           for k in kids) or "<li>none</li>"
        parent = f" · from <a href='/tasks/{t['parent_id']}'>#{t['parent_id']}</a>" if t["parent_id"] else ""
        return 200, page(f"Task {tid}", f"""<p><a href='/'>← Mission Control</a></p>
<h1>Task #{tid}: {escape(t['agent'])}</h1><p>{escape(t['status'])} · {escape(t['source'])} · ${t['cost_usd']:.3f}{parent}</p>
<h2>Input</h2><div class=card><pre>{escape(t['input'])}</pre></div>
<h2>Result</h2><div class=card><pre>{escape(t['result'] or '')}</pre></div>
<h2>Outputs</h2><ul>{links}</ul><h2>Handoffs</h2><ul>{children}</ul>""")


def office_state(conn, roster, roster_all) -> dict:
    """Everything the dungeon map needs, in one poll."""
    tasks = conn.execute(
        "SELECT t.id, t.agent, t.status, t.source, left(t.input, 160) AS input, t.created_at, t.finished_at, "
        "p.agent AS parent_agent FROM tasks t LEFT JOIN tasks p ON p.id = t.parent_id "
        "WHERE t.created_at >= now() - interval '24 hours' ORDER BY t.id DESC LIMIT 300").fetchall()
    pending = {r["agent"]: r["n"] for r in conn.execute(
        "SELECT agent, count(*) AS n FROM approvals WHERE status = 'pending' GROUP BY agent")}
    spend = {r["agent"]: float(r["usd"]) for r in conn.execute(
        "SELECT agent, sum(cost_usd) AS usd FROM tasks WHERE created_at >= date_trunc('day', now()) GROUP BY agent")}
    chosen = db.all_avatars(conn)
    now = datetime.now(timezone.utc)

    agents = []
    for a in roster_all.agents.values():
        mine = [t for t in tasks if t["agent"] == a.id]  # newest first
        running = next((t for t in mine if t["status"] == "running"), None)
        queued = next((t for t in mine if t["status"] == "queued"), None)
        last = next((t for t in mine if t["finished_at"]), None)
        if running:
            state, task = "working", running["input"]
        elif pending.get(a.id):
            state, task = "needs_you", f"{pending[a.id]} approval(s) waiting on you"
        elif queued:
            state, task = "queued", queued["input"]
        elif last and last["status"] == "failed" and now - last["finished_at"] < timedelta(minutes=30):
            state, task = "failed", "Last task failed"
        else:
            state, task = "idle", ""
        key = a.avatar or (chosen.get(a.id) or {}).get("avatar")
        emoji, label = CATALOG.get(key, RECRUIT)
        agents.append({
            "id": a.id, "dept": a.dept, "phase": a.phase, "active": a.id in roster.agents,
            "model": a.model, "emoji": emoji, "avatar": label,
            "reason": (chosen.get(a.id) or {}).get("reason", ""),
            "state": state, "task": task,
            "spent": round(spend.get(a.id, 0.0), 3), "budget": a.budget_usd,
        })

    rooms = []
    for dept, name, col, row in ROOMS:
        members = [a for a in agents if a["dept"] == dept]
        rooms.append({
            "dept": dept, "name": name, "col": col, "row": row,
            "active": any(a["active"] for a in members),
            "unlocks": min((a["phase"] for a in members), default=None),
        })

    return {
        "paused": queue.is_paused(queue.connect()),
        "spent": round(db.spent_today(conn), 2),
        "budget": runner.GLOBAL_DAILY_BUDGET_USD,
        "pending": sum(pending.values()),
        "rooms": rooms,
        "agents": agents,
        "events": [{
            "id": t["id"], "agent": t["agent"], "status": t["status"], "source": t["source"],
            "parent": t["parent_agent"], "input": (t["input"] or "")[:100], "at": t["created_at"],
        } for t in tasks[:40]],
    }


def main() -> None:
    Handler.roster = roster_mod.load()
    Handler.roster_all = roster_mod.load(phase=99)
    with db.connect() as conn:
        db.migrate(conn)
    log.info("console listening on :%d", PORT)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
