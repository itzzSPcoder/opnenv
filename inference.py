#!/usr/bin/env python3
"""OpenEnv inference script template.

This script is designed to satisfy the OpenEnv submission contract:
- Reads model/env settings from environment variables.
- Uses OpenAI Client for LLM calls.
- Emits strict [START]/[STEP]/[END] stdout lines.
"""

import asyncio
import os
import re
import textwrap
from typing import Any, List, Optional

# MANDATORY vars for most leaderboard setups.
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME") or os.getenv("IMAGE_NAME")

# Allowed defaults (per requirement).
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")

TASK_NAME = os.getenv("MY_ENV_V4_TASK", "easy_priority_routing")
BENCHMARK = os.getenv("MY_ENV_V4_BENCHMARK", "admission_helpdesk_v1")

MAX_STEPS = int(os.getenv("MAX_STEPS", "12"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "150"))
SUCCESS_SCORE_THRESHOLD = float(os.getenv("SUCCESS_SCORE_THRESHOLD", "0.70"))
USE_LLM = os.getenv("USE_LLM", "1").strip().lower() not in {"0", "false", "no"}

MAX_TOTAL_REWARD = max(float(MAX_STEPS), 1.0)

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an admissions helpdesk triage agent.
    Output exactly one command in one line using one of these formats:
    - set_priority(low|medium|high)
    - assign_team(admissions|finance|tech|hostel)
    - draft_reply(<clear policy-safe response>)
    - escalate(<reason>)
    - close_ticket()
    - next_ticket()
    Rules:
    - No markdown, no backticks, no explanations.
    - Prefer routing and a useful policy-safe reply before closing.
    """
).strip()


def _to_bool_str(value: bool) -> str:
    return "true" if value else "false"


def _sanitize_single_line(value: str) -> str:
    return " ".join((value or "").split())


def _format_error(err: Optional[str]) -> str:
    if err is None or err == "":
        return "null"
    return _sanitize_single_line(err)


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    print(
        "[STEP] "
        f"step={step} "
        f"action={_sanitize_single_line(action)} "
        f"reward={reward:.2f} "
        f"done={_to_bool_str(done)} "
        f"error={_format_error(error)}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={_to_bool_str(success)} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


def build_user_prompt(step: int, last_echoed: str, last_reward: float, history: List[str]) -> str:
    history_block = "\n".join(history[-4:]) if history else "None"
    return textwrap.dedent(
        f"""
        Step: {step}
        Last echoed message: {last_echoed!r}
        Last reward: {last_reward:.2f}
        Recent history:
        {history_block}

        Return only your next action text.
        """
    ).strip()


def _load_openai_client_class() -> Any:
    from openai import OpenAI

    return OpenAI


def _load_env_classes() -> Any:
    from my_env_v4 import MyEnvV4Action, MyEnvV4Env

    return MyEnvV4Action, MyEnvV4Env


def _infer_team(ticket_text: str) -> str:
    text = ticket_text.lower()
    if any(k in text for k in ["refund", "fee", "loan"]):
        return "finance"
    if any(k in text for k in ["crash", "login", "error", "portal"]):
        return "tech"
    if "hostel" in text and "crash" not in text:
        return "hostel"
    return "admissions"


def _infer_priority(ticket_text: str) -> str:
    text = ticket_text.lower()
    if any(k in text for k in ["urgent", "tomorrow", "36 hours", "visa", "deadline"]):
        return "high"
    if any(k in text for k in ["refund", "crash", "paid twice"]):
        return "medium"
    return "low"


def _heuristic_reply(ticket_text: str) -> str:
    text = ticket_text.lower()
    if "refund" in text or "paid twice" in text:
        return "draft_reply(We will process your refund after receipt verification. Please share payment receipt and transaction ID. Expected timeline is 5-7 working days.)"
    if "visa" in text or "letter" in text:
        return "draft_reply(We have marked this as priority. Our admissions team will review your visa letter request and share the signed letter on priority timeline today.)"
    if "crash" in text or "portal" in text:
        return "draft_reply(We identified the issue. Please share screenshot and browser details so tech team can apply fix quickly.)"
    if "loan" in text:
        return "draft_reply(As per policy, loan documents can be submitted after provisional admission confirmation. Please upload required documents within the timeline.)"
    return "draft_reply(We will review your documents before the deadline. Please confirm your documents are uploaded and our team will complete review quickly.)"


def _heuristic_action(step: int, last_echoed: str) -> str:
    text = (last_echoed or "").lower()

    pr_done = "priority_done=true" in text
    team_done = "team_done=true" in text
    reply_done = "reply_done=true" in text
    escalated = "escalated=true" in text
    closed = "closed=true" in text

    ticket_match = re.search(r"ticket\s+[^:]+:\s*(.*?)\s*\|\s*sla=", text)
    ticket_text = ticket_match.group(1) if ticket_match else text

    if closed:
        return "next_ticket()"
    if not pr_done:
        return f"set_priority({_infer_priority(ticket_text)})"
    if not team_done:
        return f"assign_team({_infer_team(ticket_text)})"
    if ("visa" in ticket_text or "signed admission letter" in ticket_text) and not escalated:
        return "escalate(urgent visa letter processing required)"
    if not reply_done:
        return _heuristic_reply(ticket_text)
    return "close_ticket()"


def get_model_message(
    client: Optional[Any], step: int, last_echoed: str, last_reward: float, history: List[str]
) -> str:
    if client is None:
        return _heuristic_action(step, last_echoed)

    user_prompt = build_user_prompt(step, last_echoed, last_reward, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        if not text:
            return _heuristic_action(step, last_echoed)
        # Enforce single-line action payload in logs and env action.
        return _sanitize_single_line(text)
    except Exception:
        return _heuristic_action(step, last_echoed)


def _extract_last_error(result: Any) -> Optional[str]:
    info = getattr(result, "info", None)
    if isinstance(info, dict):
        value = info.get("last_action_error")
        if value is None:
            return None
        return str(value)
    return None


async def _create_env() -> Any:
    _, my_env_cls = _load_env_classes()
    if LOCAL_IMAGE_NAME:
        return await my_env_cls.from_docker_image(LOCAL_IMAGE_NAME)
    return await my_env_cls.from_local()


async def main() -> None:
    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False
    env = None
    client: Optional[Any] = None
    last_info: dict[str, Any] = {}

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    try:
        action_cls, _ = _load_env_classes()
        env = await _create_env()
        try:
            result = await env.reset(task_name=TASK_NAME)
        except TypeError:
            result = await env.reset()
        last_echoed = getattr(result.observation, "echoed_message", "")
        last_reward = 0.0
        last_info = dict(getattr(result, "info", {}) or {})

        should_use_llm = USE_LLM and bool(API_KEY)
        if API_KEY and API_KEY.lower().startswith("dummy"):
            should_use_llm = False

        if should_use_llm:
            try:
                openai_cls = _load_openai_client_class()
                client = openai_cls(base_url=API_BASE_URL, api_key=API_KEY)
            except Exception:
                client = None

        for step in range(1, MAX_STEPS + 1):
            if bool(getattr(result, "done", False)):
                break

            action_text = get_model_message(client, step, last_echoed, last_reward, history)

            try:
                result = await env.step(action_cls(action=action_text))
                reward = float(getattr(result, "reward", 0.0) or 0.0)
                done = bool(getattr(result, "done", False))
                error = _extract_last_error(result)
                last_info = dict(getattr(result, "info", {}) or {})
            except Exception as exc:
                reward = 0.0
                done = True
                error = str(exc)

            rewards.append(reward)
            steps_taken = step
            last_echoed = getattr(getattr(result, "observation", None), "echoed_message", "")
            last_reward = reward

            log_step(step=step, action=action_text, reward=reward, done=done, error=error)
            history.append(f"step={step} action={action_text!r} reward={reward:.2f}")

            if done:
                break

        info_score = last_info.get("normalized_score")
        if isinstance(info_score, (int, float)):
            score = min(max(float(info_score), 0.0), 1.0)
        else:
            raw_score = sum(rewards) / MAX_TOTAL_REWARD
            score = min(max(raw_score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception:
        raw_score = sum(rewards) / MAX_TOTAL_REWARD if MAX_TOTAL_REWARD > 0 else 0.0
        score = min(max(raw_score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        if env is not None:
            try:
                await env.close()
            except Exception:
                pass
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


if __name__ == "__main__":
    asyncio.run(main())
