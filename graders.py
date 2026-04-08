"""Deterministic task graders for admission-helpdesk-openenv.

These graders are intentionally tolerant to different evaluator payload shapes.
Each grader returns a normalized score in [0.0, 1.0].
"""

from __future__ import annotations

from typing import Any, Dict, Iterable


TASK_GRADERS: Dict[str, str] = {
    "easy_priority_routing": "graders.grade_easy_priority_routing",
    "medium_resolution": "graders.grade_medium_resolution",
    "hard_sla_queue": "graders.grade_hard_sla_queue",
}

TASK_GRADERS_COLON: Dict[str, str] = {
    "easy_priority_routing": "graders:grade_easy_priority_routing",
    "medium_resolution": "graders:grade_medium_resolution",
    "hard_sla_queue": "graders:grade_hard_sla_queue",
}


def _clamp01(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def _from_progress_snapshot(payload: Dict[str, Any]) -> float | None:
    progress = payload.get("progress")
    if not isinstance(progress, dict) or not progress:
        return None

    remaining_sla = payload.get("remaining_sla")
    if not isinstance(remaining_sla, dict):
        remaining_sla = {}

    total = 0.0
    count = 0
    for ticket_id, ticket_progress in progress.items():
        if not isinstance(ticket_progress, dict):
            continue

        score = 0.0
        score += 0.20 if bool(ticket_progress.get("priority")) else 0.0
        score += 0.20 if bool(ticket_progress.get("team")) else 0.0
        score += 0.30 if bool(ticket_progress.get("reply")) else 0.0
        # If escalation is absent, do not reward it by default.
        score += 0.10 if bool(ticket_progress.get("escalated")) else 0.0
        score += 0.20 if bool(ticket_progress.get("closed")) else 0.0

        if remaining_sla.get(ticket_id) == 0 and not bool(ticket_progress.get("closed")):
            score -= 0.10

        total += max(score, 0.0)
        count += 1

    if count == 0:
        return None
    return _clamp01(total / count)


def _extract_numeric(candidate: Any) -> float | None:
    if isinstance(candidate, (int, float)):
        return _clamp01(float(candidate))
    return None


def _extract_from_mapping(data: Dict[str, Any]) -> float | None:
    for key in ("normalized_score", "score", "final_score"):
        val = _extract_numeric(data.get(key))
        if val is not None:
            return val

    info = data.get("info")
    if isinstance(info, dict):
        for key in ("normalized_score", "score", "final_score"):
            val = _extract_numeric(info.get(key))
            if val is not None:
                return val

    nested = data.get("state")
    if isinstance(nested, dict):
        val = _extract_from_mapping(nested)
        if val is not None:
            return val

    nested = data.get("result")
    if isinstance(nested, dict):
        val = _extract_from_mapping(nested)
        if val is not None:
            return val

    trajectory = data.get("trajectory")
    if isinstance(trajectory, Iterable):
        step_rewards: list[float] = []
        for step in trajectory:
            if isinstance(step, dict):
                numeric_reward = _extract_numeric(step.get("reward"))
                if numeric_reward is not None:
                    step_rewards.append(numeric_reward)
        if step_rewards:
            return _clamp01(sum(step_rewards) / len(step_rewards))

    return _from_progress_snapshot(data)


def _extract_score(payload: Any) -> float | None:
    val = _extract_numeric(payload)
    if val is not None:
        return val

    if isinstance(payload, dict):
        return _extract_from_mapping(payload)

    # Dataclass/Pydantic-like objects.
    for attr in ("normalized_score", "score", "final_score"):
        if hasattr(payload, attr):
            val = _extract_numeric(getattr(payload, attr))
            if val is not None:
                return val

    if hasattr(payload, "info"):
        info = getattr(payload, "info")
        if isinstance(info, dict):
            val = _extract_from_mapping({"info": info})
            if val is not None:
                return val

    if hasattr(payload, "model_dump"):
        try:
            dumped = payload.model_dump()
            if isinstance(dumped, dict):
                return _extract_from_mapping(dumped)
        except Exception:
            pass

    return None


def _grade_from_inputs(task_id: str, *args: Any, **kwargs: Any) -> float:
    candidates = []
    candidates.extend(args)
    candidates.extend(kwargs.values())

    for candidate in candidates:
        score = _extract_score(candidate)
        if score is not None:
            return _clamp01(score)

    # Deterministic neutral fallback if evaluator passes unsupported payload.
    return 0.0


def grade_easy_priority_routing(*args: Any, **kwargs: Any) -> float:
    return _grade_from_inputs("easy_priority_routing", *args, **kwargs)


def grade_medium_resolution(*args: Any, **kwargs: Any) -> float:
    return _grade_from_inputs("medium_resolution", *args, **kwargs)


def grade_hard_sla_queue(*args: Any, **kwargs: Any) -> float:
    return _grade_from_inputs("hard_sla_queue", *args, **kwargs)


def grade_task(task_id: str, *args: Any, **kwargs: Any) -> float:
    if task_id == "easy_priority_routing":
        return grade_easy_priority_routing(*args, **kwargs)
    if task_id == "medium_resolution":
        return grade_medium_resolution(*args, **kwargs)
    if task_id == "hard_sla_queue":
        return grade_hard_sla_queue(*args, **kwargs)
    return 0.0
