"""Owner notifications: Slack incoming webhook (Block Kit) when configured, mirrored into outputs by the caller."""

import json
import logging
import os
import re
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
CONSOLE_URL = os.environ.get("CONSOLE_URL", "http://agents.home.arpa").rstrip("/")
TZ = ZoneInfo(os.environ.get("TZ", "America/New_York"))

PRIORITY = {
    "info": ("📣", "Update"),
    "action": ("❗", "Needs you"),
    "urgent": ("🚨", "Urgent"),
}

# Slack Block Kit limits: header 150 chars, section text 3000, 50 blocks per message, button text 75.
HEADER_MAX, SECTION_MAX, BUTTON_MAX, FALLBACK_MAX = 150, 2800, 70, 300


def mrkdwn(text: str) -> str:
    """Make agent-written Markdown safe and readable as Slack mrkdwn.

    Agent text can echo web pages, so Slack control sequences are escaped (a stray <!channel> or <@user>
    would otherwise ping people), then common Markdown is converted to Slack's dialect.
    """
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"^#{1,6}\s*(.+?)\s*$", r"*\1*", text, flags=re.M)      # headings -> bold line
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)                          # **bold** -> *bold*
    text = re.sub(r"__(.+?)__", r"*\1*", text)
    text = re.sub(r"^\s*[-*+]\s+", "• ", text, flags=re.M)                  # bullets
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"<\2|\1>", text)  # [t](url) -> <url|t>
    return text.strip()


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _chunks(text: str, limit: int = SECTION_MAX, max_chunks: int = 6) -> list[str]:
    """Split long text at paragraph or line breaks so each piece fits one section block."""
    out, rest = [], text
    while rest and len(out) < max_chunks:
        if len(rest) <= limit:
            out.append(rest)
            rest = ""
            break
        cut = max(rest.rfind("\n\n", 0, limit), rest.rfind("\n", 0, limit), rest.rfind(" ", 0, limit))
        cut = cut if cut > limit // 2 else limit
        out.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        out[-1] = _clip(out[-1], limit - 1) + "…"
    return out


def _header(text: str) -> dict:
    return {"type": "header", "text": {"type": "plain_text", "text": _clip(text, HEADER_MAX), "emoji": True}}


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _context(*parts: str) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": p} for p in parts[:10]]}


def _button(label: str, url: str, primary: bool = False) -> dict:
    btn = {"type": "button", "text": {"type": "plain_text", "text": _clip(label, BUTTON_MAX), "emoji": True}, "url": url}
    if primary:
        btn["style"] = "primary"
    return btn


def _now() -> str:
    return datetime.now(TZ).strftime("%a %b %d, %-I:%M %p")


def post(payload: dict) -> bool:
    """POST a Block Kit payload. Returns False when Slack isn't configured or the post fails."""
    if not SLACK_WEBHOOK_URL:
        return False
    req = urllib.request.Request(SLACK_WEBHOOK_URL, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except OSError as e:  # URLError, HTTPError and timeouts are all OSErrors
        log.warning("slack post failed: %s", e)
        return False


def owner_blocks(agent: str, message: str, priority: str = "info") -> dict:
    icon, label = PRIORITY.get(priority, PRIORITY["info"])
    blocks = [_header(f"{icon} {agent}")]
    blocks += [_section(c) for c in _chunks(mrkdwn(message))]
    blocks.append(_context(f"*{label}*", _now(), "AgentOS"))
    blocks.append({"type": "actions", "elements": [
        _button("Open Mission Control", CONSOLE_URL, primary=priority != "info")]})
    return {"text": _clip(f"{icon} {agent}: {message}", FALLBACK_MAX), "blocks": blocks}


def approval_blocks(agent: str, pending: list[dict]) -> dict:
    n = len(pending)
    blocks = [_header(f"❗ {agent} needs your approval ({n})")]
    for a in pending[:8]:
        blocks.append(_section(f"*#{a['id']} · {mrkdwn(a['action'])}*\n{_clip(mrkdwn(a['summary']), 600)}"))
    if n > 8:
        blocks.append(_context(f"…and {n - 8} more in Mission Control"))
    blocks.append(_context("*Needs you*", _now(), "AgentOS"))
    blocks.append({"type": "actions", "elements": [_button("Review and approve", f"{CONSOLE_URL}/#approvals", primary=True)]})
    return {"text": _clip(f"❗ {agent} needs your approval ({n}): {pending[0]['summary']}", FALLBACK_MAX), "blocks": blocks}


def failure_blocks(agent: str, task_id: int, result: str) -> dict:
    blocks = [
        _header(f"💥 {agent}: task #{task_id} failed"),
        _section(_clip(mrkdwn(result), 1200)),
        _context("*Failed*", _now(), "AgentOS"),
        {"type": "actions", "elements": [_button("Open task", f"{CONSOLE_URL}/tasks/{task_id}")]},
    ]
    return {"text": _clip(f"💥 {agent} task #{task_id} failed: {result}", FALLBACK_MAX), "blocks": blocks}


def owner(agent: str, message: str, priority: str = "info") -> bool:
    return post(owner_blocks(agent, message, priority))


def task_finished(conn, task: dict, status: str, result: str) -> None:
    """Runtime-level alerts the owner always wants: new approvals and failures."""
    from . import db

    pending = db.approvals_for_task(conn, task["id"])
    if pending:
        post(approval_blocks(task["agent"], pending))
    if status == "failed":
        post(failure_blocks(task["agent"], task["id"], result))
