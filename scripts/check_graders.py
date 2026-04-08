"""Local smoke test for task graders.

Validates that each declared grader exists, runs, and returns scores in [0.0, 1.0].
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from typing import Dict, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from my_env_v4 import MyEnvV4Action, MyEnvV4Env, TASK_GRADERS

SCRIPTED_ACTIONS: Dict[str, List[str]] = {
    "easy_priority_routing": [
        "set_priority(high)",
        "assign_team(admissions)",
        "draft_reply(Deadline noted. We will review your documents before deadline.)",
        "close_ticket()",
    ],
    "medium_resolution": [
        "set_priority(medium)",
        "assign_team(finance)",
        "draft_reply(Refund timeline is shared after receipt verification and refund ticket review.)",
        "close_ticket()",
    ],
    "hard_sla_queue": [
        "set_priority(high)",
        "assign_team(admissions)",
        "draft_reply(Visa letter request marked priority; letter processing timeline shared now.)",
        "escalate(urgent visa letter manual approval)",
        "close_ticket()",
        "set_priority(medium)",
        "assign_team(tech)",
        "draft_reply(Please share screenshot of issue and we will provide a fix timeline.)",
        "close_ticket()",
        "set_priority(low)",
        "assign_team(finance)",
        "draft_reply(Policy allows documents upload with timeline after provisional confirmation.)",
        "close_ticket()",
    ],
}
def _import_callable(path: str):
    if ":" in path:
        mod, fn = path.split(":", 1)
    else:
        mod, fn = path.rsplit(".", 1)
    module = importlib.import_module(mod)
    return getattr(module, fn)


async def _run() -> None:
    for task_id, grader_path in TASK_GRADERS.items():
        if not grader_path:
            raise ValueError(f"task {task_id} has no grader field")

        grader = _import_callable(str(grader_path))

        env = MyEnvV4Env()
        initial = await env.reset(task_name=task_id)
        initial_state = await env.state()
        initial_score = float(grader(initial_state, initial))

        result = initial
        for action in SCRIPTED_ACTIONS.get(task_id, []):
            result = await env.step(MyEnvV4Action(action=action))
            if result.done:
                break

        final_state = await env.state()
        final_score = float(grader(final_state, result))

        await env.close()

        if not (0.0 <= initial_score <= 1.0):
            raise ValueError(f"grader out of range before rollout for {task_id}: {initial_score}")
        if not (0.0 <= final_score <= 1.0):
            raise ValueError(f"grader out of range after rollout for {task_id}: {final_score}")

        print(
            f"task={task_id} grader={grader_path} initial={initial_score:.4f} final={final_score:.4f}"
        )

    print("grader smoke-check passed")


if __name__ == "__main__":
    asyncio.run(_run())
