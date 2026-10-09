"""Owner notifications: Slack incoming webhook when configured, always mirrored into outputs."""

import json
import logging
import os
import urllib.request

log = logging.getLogger(__name__)
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
CONSOLE_URL = os.environ.get("CONSOLE_URL", "http://agents.home.arpa").rstrip("/")
ICONS = {"info": "📣", "action": "❗", "urgent": "🚨"}


def slack(text: str) -> bool:
    """Post plain text to Slack. Returns False when Slack isn't configured or the post fails."""
    if not SLACK_WEBHOOK_URL:
        return False
    body = json.dumps({"text": text[:3500]}).encode()
    req = urllib.request.Request(SLACK_WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except OSError as e:  # URLError, HTTPError and timeouts are all OSErrors
        log.warning("slack post failed: %s", e)
        return False


def owner(agent: str, message: str, priority: str = "info") -> bool:
    return slack(f"{ICONS.get(priority, '📣')} *{agent}*\n{message}\n<{CONSOLE_URL}|Open Mission Control>")


def task_finished(conn, task: dict, status: str, result: str) -> None:
    """Runtime-level alerts the owner always wants: new approvals and failures."""
    from . import db

    pending = db.approvals_for_task(conn, task["id"])
    if pending:
        lines = "\n".join(f"• #{a['id']} {a['action']}: {a['summary'][:160]}" for a in pending[:5])
        more = f"\n…and {len(pending) - 5} more" if len(pending) > 5 else ""
        slack(f"❗ *{task['agent']}* needs your approval ({len(pending)})\n{lines}{more}\n<{CONSOLE_URL}|Review in Mission Control>")
    if status == "failed":
        slack(f"💥 *{task['agent']}* task #{task['id']} failed\n{result[:300]}\n<{CONSOLE_URL}/tasks/{task['id']}|Open task>")
