#!/usr/bin/env python3
"""Run deterministic baseline over all tasks and print reproducible scores."""

import os
import re
import subprocess
import sys
from pathlib import Path

TASKS = ["easy_priority_routing", "medium_resolution", "hard_sla_queue"]
END_RE = re.compile(r"^\[END\].*score=(?P<score>[0-9]+(?:\.[0-9]+)?)")


def run_task(repo_root: Path, task_name: str) -> float:
    env = os.environ.copy()
    env.setdefault("MY_ENV_V4_TASK", task_name)
    env.setdefault("TEMPERATURE", "0.0")
    env.setdefault("MAX_STEPS", "12")
    env.setdefault("USE_LLM", "0")
    env.setdefault("HF_TOKEN", env.get("HF_TOKEN", "dummy-key-for-local-baseline"))

    proc = subprocess.run(
        [sys.executable, str(repo_root / "inference.py")],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    output = proc.stdout.splitlines()
    for line in reversed(output):
        m = END_RE.match(line.strip())
        if m:
            return float(m.group("score"))

    raise RuntimeError(f"No [END] score found for task {task_name}. Output:\n{proc.stdout}\n{proc.stderr}")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scores = {}
    for task in TASKS:
        score = run_task(repo_root, task)
        scores[task] = score
        print(f"[BASELINE] task={task} score={score:.2f}")

    avg = sum(scores.values()) / len(scores)
    print(f"[BASELINE] average_score={avg:.2f}")


if __name__ == "__main__":
    main()
