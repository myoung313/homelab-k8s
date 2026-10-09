"""Entry point: python -m agentos {worker|scheduler|console|validate|run AGENT "INPUT"}"""

import logging
import os
import sys

USAGE = 'usage: python -m agentos {worker|scheduler|console|validate|run AGENT "INPUT"}'


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "worker":
        from .worker import main as run
        run()
    elif cmd == "scheduler":
        from .scheduler import main as run
        run()
    elif cmd == "console":
        from .console import main as run
        run()
    elif cmd == "validate":
        from collections import Counter
        from .roster import ACTIVE_PHASE, load
        roster = load(sys.argv[2] if len(sys.argv) > 2 else os.environ.get("AGENTOS_ROSTER", "roster.yaml"), phase=99)
        phases = Counter(a.phase for a in roster.agents.values())
        active = [a for a in roster.agents.values() if a.phase <= ACTIVE_PHASE]
        print(f"roster ok: {len(roster.agents)} agents, by phase {dict(sorted(phases.items()))}")
        print(f"AGENTOS_PHASE={ACTIVE_PHASE}: {len(active)} active, "
              f"{sum(1 for a in active if a.schedules)} scheduled, "
              f"max daily spend ${sum(a.budget_usd for a in active):.2f}")
    elif cmd == "run" and len(sys.argv) == 4:
        from . import db, queue
        with db.connect() as conn:
            print(f"queued task #{queue.enqueue(conn, queue.connect(), sys.argv[2], sys.argv[3])}")
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()
