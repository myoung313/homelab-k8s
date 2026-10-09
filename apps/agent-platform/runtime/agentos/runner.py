"""Runs one task for one agent: the Claude tool-use loop with budgets and approval gates."""

import json
import logging
import os
from datetime import date

import anthropic

from . import db, notify, queue
from .avatars import CATALOG
from .roster import Agent, Model, Roster

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_HANDOFF_DEPTH = 3
MAX_HANDOFFS_PER_TASK = 5
MAX_NOTIFICATIONS_PER_DAY = 4  # per agent, so nobody spams the owner's phone
GLOBAL_DAILY_BUDGET_USD = float(os.environ.get("GLOBAL_DAILY_BUDGET_USD", "15"))
WEB_SEARCH_USD = 0.01  # per search request

WEB_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
]

CLIENT_TOOLS = [
    {
        "name": "save_output",
        "description": "Save a finished deliverable (report, draft, plan, code, list) for the human to review in the console.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "description": "Short type label, e.g. report, email-draft, script, lead-list."},
                "title": {"type": "string"},
                "body": {"type": "string", "description": "The full deliverable, in Markdown."},
            },
            "required": ["kind", "title", "body"],
            "additionalProperties": False,
        },
    },
    {
        "name": "request_approval",
        "description": (
            "Ask the human to approve an action that touches the outside world: sending an email or DM, "
            "publishing content, spending money, contacting a client, or deploying. Nothing happens until a "
            "human approves it; then the automation layer executes it."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Machine-readable action, e.g. send_email, publish_post, create_invoice."},
                "summary": {"type": "string", "description": "One or two sentences the human reads before approving."},
                "payload_json": {"type": "string", "description": "JSON object with everything needed to execute the action."},
            },
            "required": ["action", "summary", "payload_json"],
            "additionalProperties": False,
        },
    },
    {
        "name": "handoff",
        "description": "Queue a task for a teammate agent. Give complete instructions; they cannot see this conversation.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Teammate agent id."},
                "instructions": {"type": "string"},
            },
            "required": ["agent", "instructions"],
            "additionalProperties": False,
        },
    },
    {
        "name": "remember",
        "description": "Store a durable fact or lesson in shared team memory (client preferences, what worked, what failed).",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"note": {"type": "string"}},
            "required": ["note"],
            "additionalProperties": False,
        },
    },
    {
        "name": "recall",
        "description": "Full-text search shared team memory.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "recent_activity",
        "description": "Read-only view of the team's recent tasks (with result previews, spend), outputs, and approval decisions.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"hours": {"type": "integer", "description": "Look-back window, 1-336."}},
            "required": ["hours"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_owner",
        "description": (
            "Message the owner directly (Slack when configured, always visible in Mission Control). Use only for "
            "what they must see today: a plan, a blocker, a decision, or a result. Keep it short and specific."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Plain text, under 1,200 characters. Lead with the point."},
                "priority": {"type": "string", "enum": ["info", "action", "urgent"]},
            },
            "required": ["message", "priority"],
            "additionalProperties": False,
        },
    },
    {
        "name": "team_metrics",
        "description": (
            "Measured numbers for a look-back window: per-agent tasks, success/failure, average run time and cost, "
            "outputs, approval volume and turnaround, and how often the owner checked in."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "Look-back window, 1-90."}},
            "required": ["days"],
            "additionalProperties": False,
        },
    },
    {
        "name": "choose_avatar",
        "description": "Pick the avatar that represents you on the owner's dungeon map of the team. Choose once.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "avatar": {"type": "string", "enum": sorted(CATALOG)},
                "reason": {"type": "string", "description": "One short sentence on why it fits your role."},
            },
            "required": ["avatar", "reason"],
            "additionalProperties": False,
        },
    },
]


class TaskContext:
    def __init__(self, conn, r, roster: Roster, agent: Agent, task: dict):
        self.conn, self.r, self.roster, self.agent, self.task = conn, r, roster, agent, task
        self.handoffs = 0

    def execute(self, name: str, args: dict) -> tuple[str, bool]:
        """Returns (result text, is_error)."""
        if name == "save_output":
            oid = db.save_output(self.conn, self.task["id"], self.agent.id, args["kind"], args["title"], args["body"])
            return f"Saved as output #{oid}.", False

        if name == "request_approval":
            try:
                payload = json.loads(args["payload_json"])
            except json.JSONDecodeError as e:
                return f"payload_json is not valid JSON: {e}", True
            if not isinstance(payload, dict):
                return "payload_json must be a JSON object.", True
            aid = db.request_approval(self.conn, self.task["id"], self.agent.id, args["action"], args["summary"], payload)
            return f"Approval #{aid} filed. Do not assume it will be approved.", False

        if name == "handoff":
            target = args["agent"]
            if target not in self.roster.agents:
                return f"{target!r} is not on the active team.", True
            if "*" not in self.agent.handoffs and target not in self.agent.handoffs:
                return f"You may only hand off to: {', '.join(self.agent.handoffs) or 'nobody'}.", True
            if self.task["depth"] >= MAX_HANDOFF_DEPTH or self.handoffs >= MAX_HANDOFFS_PER_TASK:
                return "Handoff limit reached; save your work with save_output instead.", True
            self.handoffs += 1
            tid = queue.enqueue(self.conn, self.r, target, args["instructions"], source="handoff",
                                parent_id=self.task["id"], depth=self.task["depth"] + 1)
            return f"Queued task #{tid} for {target}.", False

        if name == "remember":
            db.remember(self.conn, self.agent.id, args["note"])
            return "Stored.", False

        if name == "recall":
            rows = db.recall(self.conn, args["query"])
            if not rows:
                return "No matching memories.", False
            return "\n".join(f"- [{r['agent']} {r['created_at']:%Y-%m-%d}] {r['note']}" for r in rows), False

        if name == "recent_activity":
            return json.dumps(db.recent_activity(self.conn, int(args["hours"])), default=str), False

        if name == "notify_owner":
            if db.notifications_today(self.conn, self.agent.id) >= MAX_NOTIFICATIONS_PER_DAY:
                return "Daily notification limit reached; put this in save_output instead.", True
            message, priority = args["message"][:1200], args["priority"]
            db.save_output(self.conn, self.task["id"], self.agent.id, "notification",
                           f"[{priority}] {message[:70]}", message)
            if notify.owner(self.agent.id, message, priority):
                return "Sent to the owner on Slack.", False
            return "Slack isn't configured; the message is in Mission Control under Latest outputs.", False

        if name == "team_metrics":
            return json.dumps(db.team_metrics(self.conn, int(args["days"])), default=str), False

        if name == "choose_avatar":
            if args["avatar"] not in CATALOG:
                return f"Pick one of: {', '.join(sorted(CATALOG))}.", True
            if not db.set_avatar(self.conn, self.agent.id, args["avatar"], args["reason"]):
                return "You already have an avatar; only the owner can change it.", False
            return f"You are now the {CATALOG[args['avatar']][1]}.", False

        return f"Unknown tool {name!r}.", True


def system_prompt(roster: Roster, agent: Agent) -> str:
    # Stable across runs so the prefix caches; volatile details go in the user turn.
    directory = "\n".join(f"- {a.id} ({a.dept})" for a in roster.agents.values())
    allowed = "any teammate" if "*" in agent.handoffs else (", ".join(agent.handoffs) or "nobody")
    return (
        f"{roster.house_rules}\n\n"
        f"# Your role: {agent.id} ({agent.dept} department)\n{agent.mission}\n\n"
        f"# Team directory\n{directory}\n\n"
        f"You may hand off to: {allowed}."
    )


def estimate_cost(model: Model, usage) -> float:
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    usd = (
        usage.input_tokens * model.input_per_mtok
        + cache_write * model.input_per_mtok * 1.25
        + cache_read * model.input_per_mtok * 0.1
        + usage.output_tokens * model.output_per_mtok
    ) / 1_000_000
    server_tools = getattr(usage, "server_tool_use", None)
    if server_tools is not None:
        usd += (getattr(server_tools, "web_search_requests", 0) or 0) * WEB_SEARCH_USD
    return usd


def _create(client: anthropic.Anthropic, model: Model, agent: Agent, system, tools, messages):
    params = dict(
        model=model.id,
        max_tokens=16000,
        system=system,
        tools=tools,
        messages=messages,
        output_config={"effort": agent.effort},
    )
    if model.tier == "haiku":
        return client.messages.create(**params)
    # Opus/Sonnet: if a safety classifier declines, let the API re-run on its recommended fallback.
    return client.beta.messages.create(**params, betas=[FALLBACK_BETA], fallbacks="default")


def run(client: anthropic.Anthropic, conn, r, roster: Roster, task: dict) -> tuple[str, str]:
    """Returns (status, result)."""
    agent = roster.agents.get(task["agent"])
    if agent is None:
        return "failed", f"Agent {task['agent']!r} is not in the roster."
    model = roster.models[agent.model]

    if db.spent_today(conn) >= GLOBAL_DAILY_BUDGET_USD:
        return "skipped", "Global daily budget reached."
    if db.spent_today(conn, agent.id) >= agent.budget_usd:
        return "skipped", f"{agent.id} daily budget (${agent.budget_usd:.2f}) reached."

    ctx = TaskContext(conn, r, roster, agent, task)
    system = [{"type": "text", "text": system_prompt(roster, agent), "cache_control": {"type": "ephemeral"}}]
    tools = CLIENT_TOOLS + (WEB_TOOLS if agent.web else [])
    content = f"Task #{task['id']} (source: {task['source']}, date: {date.today().isoformat()})\n\n{task['input']}"
    if agent.avatar is None and db.get_avatar(conn, agent.id) is None:
        content += ("\n\n(Housekeeping: you don't have an avatar yet on the owner's dungeon map of the team. "
                    "Call choose_avatar once, picking whatever fits your role and personality.)")
    messages = [{"role": "user", "content": content}]

    response = None
    for _ in range(agent.max_turns):
        response = _create(client, model, agent, system, tools, messages)
        db.add_cost(conn, task["id"], estimate_cost(model, response.usage))

        if response.stop_reason == "refusal":
            return "failed", "Model declined this task."

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "pause_turn":
            continue  # a long server-side tool turn; re-send to let it finish
        if response.stop_reason != "tool_use":
            break

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            text, is_error = ctx.execute(block.name, block.input)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": text, "is_error": is_error})
        messages.append({"role": "user", "content": results})

        if db.spent_today(conn, agent.id) >= agent.budget_usd:
            return "done", "Stopped early: daily budget reached mid-task. Partial work is in outputs."
    else:
        return "done", f"Stopped after {agent.max_turns} turns. Partial work is in outputs."

    final = "".join(b.text for b in response.content if b.type == "text").strip()
    return "done", final or "(no summary)"
