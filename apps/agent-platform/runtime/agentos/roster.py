"""Loads and validates the agent roster (roster.yaml)."""

import os
from dataclasses import dataclass, field, replace

import yaml
from croniter import croniter

from .avatars import CATALOG

ROSTER_PATH = os.environ.get("AGENTOS_ROSTER", "/etc/agentos/roster.yaml")
# Agents whose phase is above this stay dormant: grow the team as revenue grows.
ACTIVE_PHASE = int(os.environ.get("AGENTOS_PHASE", "1"))


@dataclass(frozen=True)
class Model:
    tier: str
    id: str
    input_per_mtok: float
    output_per_mtok: float


@dataclass(frozen=True)
class Agent:
    id: str
    dept: str
    model: str
    effort: str
    mission: str
    phase: int = 1
    schedule: str | None = None
    task: str | None = None
    web: bool = False
    budget_usd: float = 1.0
    max_turns: int = 12
    handoffs: tuple[str, ...] = field(default_factory=tuple)
    avatar: str | None = None  # owner override; otherwise the agent picks its own


@dataclass(frozen=True)
class Roster:
    house_rules: str
    models: dict[str, Model]
    agents: dict[str, Agent]


def load(path: str = ROSTER_PATH, phase: int = ACTIVE_PHASE) -> Roster:
    with open(path) as f:
        raw = yaml.safe_load(f)

    defaults = raw.get("defaults", {})
    models = {
        tier: Model(tier, m["id"], float(m["input_per_mtok"]), float(m["output_per_mtok"]))
        for tier, m in raw["models"].items()
    }

    agents: dict[str, Agent] = {}
    for a in raw["agents"]:
        agent = Agent(
            id=a["id"],
            dept=a["dept"],
            model=a.get("model", defaults.get("model", "sonnet")),
            effort=a.get("effort", defaults.get("effort", "medium")),
            mission=a["mission"].strip(),
            phase=int(a.get("phase", 1)),
            schedule=a.get("schedule"),
            task=(a.get("task") or "").strip() or None,
            web=bool(a.get("web", False)),
            budget_usd=float(a.get("budget_usd", defaults.get("budget_usd", 1.0))),
            max_turns=int(a.get("max_turns", defaults.get("max_turns", 12))),
            handoffs=tuple(a.get("handoffs", [])),
            avatar=a.get("avatar"),
        )
        if agent.id in agents:
            raise ValueError(f"duplicate agent id: {agent.id}")
        agents[agent.id] = agent

    roster = Roster(raw["house_rules"].strip(), models, agents)
    _validate(roster)

    active = {k: a for k, a in agents.items() if a.phase <= phase}
    for k, a in active.items():
        pruned = tuple(t for t in a.handoffs if t == "*" or t in active)
        active[k] = replace(a, handoffs=pruned)
    return Roster(roster.house_rules, models, active)


def _validate(roster: Roster) -> None:
    for agent in roster.agents.values():
        if agent.model not in roster.models:
            raise ValueError(f"{agent.id}: unknown model tier {agent.model!r}")
        if agent.effort not in ("low", "medium", "high", "xhigh", "max"):
            raise ValueError(f"{agent.id}: invalid effort {agent.effort!r}")
        if agent.avatar is not None and agent.avatar not in CATALOG:
            raise ValueError(f"{agent.id}: unknown avatar {agent.avatar!r}")
        if agent.web and agent.model == "haiku":
            raise ValueError(f"{agent.id}: web tools need the sonnet or opus tier")
        if agent.schedule:
            if not croniter.is_valid(agent.schedule):
                raise ValueError(f"{agent.id}: invalid cron {agent.schedule!r}")
            if not agent.task:
                raise ValueError(f"{agent.id}: scheduled agents need a default task")
        for target in agent.handoffs:
            if target != "*" and target not in roster.agents:
                raise ValueError(f"{agent.id}: unknown handoff target {target!r}")
