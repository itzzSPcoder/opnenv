"""Admissions Helpdesk OpenEnv environment.

This environment simulates real-world admission support operations where an
agent triages, routes, and resolves student tickets under SLA constraints.
"""

from __future__ import annotations

import copy
import os
import re
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class TicketCase(BaseModel):
    ticket_id: str
    text: str
    student_tier: str
    channel: str
    intent: str
    required_priority: Literal["low", "medium", "high"]
    required_team: Literal["admissions", "finance", "tech", "hostel"]
    must_include_terms: List[str] = Field(default_factory=list)
    forbidden_terms: List[str] = Field(default_factory=list)
    needs_escalation: bool = False
    starting_sla_minutes: int = 120


class MyEnvV4Action(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Agent command as text, e.g. set_priority(high), assign_team(finance), "
            "draft_reply(Please upload your marksheet), escalate(urgent manual check), "
            "close_ticket(), next_ticket()."
        ),
    )


class MyEnvV4Observation(BaseModel):
    task_name: str
    objective: str
    step: int
    active_ticket_id: str
    ticket_text: str
    student_tier: str
    channel: str
    sla_minutes_left: int
    queue_remaining: int
    history: List[str] = Field(default_factory=list)
    echoed_message: str


class MyEnvV4Result(BaseModel):
    observation: MyEnvV4Observation
    reward: float
    done: bool
    info: Dict[str, object] = Field(default_factory=dict)


TASK_LIBRARY: Dict[str, Dict[str, object]] = {
    "easy_priority_routing": {
        "objective": "Classify urgency and route a single ticket to the right support team.",
        "tickets": [
            TicketCase(
                ticket_id="E-101",
                text=(
                    "I submitted my JEE score and transcript 5 days ago but my dashboard still says "
                    "documents pending. Last date for confirmation is tomorrow."
                ),
                student_tier="domestic",
                channel="email",
                intent="application_document_review",
                required_priority="high",
                required_team="admissions",
                must_include_terms=["deadline", "documents", "review"],
                forbidden_terms=["guarantee", "ignore"],
                needs_escalation=False,
                starting_sla_minutes=60,
            )
        ],
    },
    "medium_resolution": {
        "objective": "Route correctly and provide a policy-safe actionable response before closing.",
        "tickets": [
            TicketCase(
                ticket_id="M-204",
                text=(
                    "I paid my acceptance fee twice due to payment gateway retry. Please help with refund "
                    "timeline and required proof."
                ),
                student_tier="domestic",
                channel="chat",
                intent="duplicate_payment_refund",
                required_priority="medium",
                required_team="finance",
                must_include_terms=["refund", "receipt", "timeline"],
                forbidden_terms=["guarantee", "immediate"],
                needs_escalation=False,
                starting_sla_minutes=90,
            )
        ],
    },
    "hard_sla_queue": {
        "objective": "Handle a queue of mixed tickets under SLA pressure with correct escalation decisions.",
        "tickets": [
            TicketCase(
                ticket_id="H-301",
                text=(
                    "I am an international applicant and my visa interview is in 36 hours. I still have not "
                    "received the signed admission letter."
                ),
                student_tier="international",
                channel="email",
                intent="urgent_visa_letter",
                required_priority="high",
                required_team="admissions",
                must_include_terms=["visa", "letter", "priority"],
                forbidden_terms=["wait", "ignore"],
                needs_escalation=True,
                starting_sla_minutes=40,
            ),
            TicketCase(
                ticket_id="H-302",
                text=(
                    "My hostel allocation page crashes after login. I cannot select room preference."
                ),
                student_tier="domestic",
                channel="chat",
                intent="hostel_portal_issue",
                required_priority="medium",
                required_team="tech",
                must_include_terms=["issue", "screenshot", "fix"],
                forbidden_terms=["ignore"],
                needs_escalation=False,
                starting_sla_minutes=80,
            ),
            TicketCase(
                ticket_id="H-303",
                text=(
                    "I need to know whether education loan documents can be uploaded after provisional "
                    "admission confirmation."
                ),
                student_tier="domestic",
                channel="email",
                intent="loan_document_policy",
                required_priority="low",
                required_team="finance",
                must_include_terms=["policy", "documents", "timeline"],
                forbidden_terms=["guarantee"],
                needs_escalation=False,
                starting_sla_minutes=120,
            ),
        ],
    },
}


class MyEnvV4Env:
    def __init__(self, max_steps: int = 12) -> None:
        self._max_steps = max_steps
        self._closed = False
        self._last_action_error: Optional[str] = None

        self._task_name = "easy_priority_routing"
        self._objective = ""
        self._tickets: List[TicketCase] = []
        self._active_index = 0
        self._step_count = 0
        self._history: List[str] = []
        self._total_reward = 0.0

        self._progress: Dict[str, Dict[str, bool]] = {}
        self._remaining_sla: Dict[str, int] = {}

    @classmethod
    async def from_docker_image(cls, _image_name: str) -> "MyEnvV4Env":
        return cls(max_steps=int(os.getenv("MAX_STEPS", "12")))

    @classmethod
    async def from_local(cls) -> "MyEnvV4Env":
        return cls(max_steps=int(os.getenv("MAX_STEPS", "12")))

    async def reset(self) -> MyEnvV4Result:
        self._closed = False
        self._step_count = 0
        self._history = []
        self._total_reward = 0.0
        self._last_action_error = None

        task_name = os.getenv("MY_ENV_V4_TASK", "easy_priority_routing")
        if task_name not in TASK_LIBRARY:
            task_name = "easy_priority_routing"
            self._last_action_error = "unknown task, defaulted to easy_priority_routing"

        self._task_name = task_name
        task_data = TASK_LIBRARY[task_name]
        self._objective = str(task_data["objective"])
        self._tickets = copy.deepcopy(task_data["tickets"])
        self._active_index = 0

        self._progress = {
            t.ticket_id: {
                "priority": False,
                "team": False,
                "reply": False,
                "escalated": False,
                "closed": False,
            }
            for t in self._tickets
        }
        self._remaining_sla = {t.ticket_id: int(t.starting_sla_minutes) for t in self._tickets}

        return MyEnvV4Result(
            observation=self._build_observation("Environment reset"),
            reward=0.0,
            done=False,
            info=self._build_info(),
        )

    async def step(self, action: MyEnvV4Action) -> MyEnvV4Result:
        if self._closed:
            return MyEnvV4Result(
                observation=self._build_observation("Environment already closed"),
                reward=0.0,
                done=True,
                info=self._build_info(error="environment is closed"),
            )

        self._step_count += 1
        command = (action.action or "").strip()
        current = self._current_ticket()
        reward, err = self._apply_action(command, current)

        self._remaining_sla[current.ticket_id] = max(0, self._remaining_sla[current.ticket_id] - 8)
        if self._remaining_sla[current.ticket_id] == 0 and not self._progress[current.ticket_id]["closed"]:
            reward -= 0.08
            err = err or "SLA breached for active ticket"

        self._total_reward += reward
        self._last_action_error = err

        self._history.append(
            f"step={self._step_count} ticket={current.ticket_id} action={command} reward={reward:+.2f}"
        )

        done = self._is_done()
        observation = self._build_observation(command)

        return MyEnvV4Result(
            observation=observation,
            reward=float(round(reward, 4)),
            done=done,
            info=self._build_info(),
        )

    async def state(self) -> Dict[str, object]:
        return {
            "task_name": self._task_name,
            "objective": self._objective,
            "step": self._step_count,
            "max_steps": self._max_steps,
            "active_ticket": self._current_ticket().model_dump(),
            "progress": copy.deepcopy(self._progress),
            "remaining_sla": copy.deepcopy(self._remaining_sla),
            "total_reward": round(self._total_reward, 4),
            "normalized_score": round(self._compute_score(), 4),
            "done": self._is_done(),
            "last_action_error": self._last_action_error,
        }

    async def close(self) -> None:
        self._closed = True

    def _apply_action(self, command: str, ticket: TicketCase) -> Tuple[float, Optional[str]]:
        parsed = self._parse_action(command)
        if parsed is None:
            return -0.06, "invalid action format"

        kind, value = parsed
        progress = self._progress[ticket.ticket_id]
        reward = 0.0
        error: Optional[str] = None

        if kind == "set_priority":
            if value == ticket.required_priority:
                reward += 0.18
                progress["priority"] = True
            else:
                reward -= 0.05
                error = f"wrong priority, expected {ticket.required_priority}"

        elif kind == "assign_team":
            if value == ticket.required_team:
                reward += 0.22
                progress["team"] = True
            else:
                reward -= 0.07
                error = f"wrong team, expected {ticket.required_team}"

        elif kind == "draft_reply":
            if len(value) < 20:
                reward -= 0.05
                error = "reply too short"
            else:
                text = value.lower()
                bad = [w for w in ticket.forbidden_terms if w in text]
                if bad:
                    reward -= 0.20
                    error = f"unsafe reply term used: {bad[0]}"
                else:
                    matched = sum(1 for w in ticket.must_include_terms if w in text)
                    ratio = matched / max(len(ticket.must_include_terms), 1)
                    if ratio >= 1.0:
                        reward += 0.25
                        progress["reply"] = True
                    elif ratio >= 0.5:
                        reward += 0.10
                    else:
                        reward -= 0.03
                        error = "reply missing key policy terms"

        elif kind == "escalate":
            if ticket.needs_escalation and len(value) >= 8:
                reward += 0.16
                progress["escalated"] = True
            elif ticket.needs_escalation:
                reward -= 0.05
                error = "escalation reason too weak"
            else:
                reward -= 0.12
                error = "unnecessary escalation"

        elif kind == "close_ticket":
            if progress["closed"]:
                reward -= 0.02
                error = "ticket already closed"
            else:
                required_done = progress["priority"] and progress["team"] and progress["reply"]
                escalation_ok = (not ticket.needs_escalation) or progress["escalated"]
                if required_done and escalation_ok:
                    reward += 0.30
                    progress["closed"] = True
                    self._move_to_next_open_ticket()
                else:
                    reward -= 0.09
                    error = "cannot close before routing and quality response"

        elif kind == "next_ticket":
            if len(self._tickets) <= 1:
                reward -= 0.01
            else:
                self._active_index = (self._active_index + 1) % len(self._tickets)
                reward += 0.01

        else:
            reward -= 0.06
            error = "unknown action"

        reward = max(min(reward, 1.0), -1.0)
        return reward, error

    def _move_to_next_open_ticket(self) -> None:
        for idx, item in enumerate(self._tickets):
            if not self._progress[item.ticket_id]["closed"]:
                self._active_index = idx
                return

    def _parse_action(self, command: str) -> Optional[Tuple[str, str]]:
        text = command.strip().lower()
        if not text:
            return None

        m = re.match(r"^(set_priority|assign_team|draft_reply|escalate|close_ticket|next_ticket)\s*\((.*)\)\s*$", text)
        if m:
            return m.group(1), m.group(2).strip()

        if ":" in text:
            left, right = text.split(":", 1)
            left = left.strip()
            right = right.strip()
            if left in {
                "set_priority",
                "assign_team",
                "draft_reply",
                "escalate",
                "close_ticket",
                "next_ticket",
            }:
                return left, right

        if text in {"close_ticket", "next_ticket"}:
            return text, ""

        return None

    def _current_ticket(self) -> TicketCase:
        return self._tickets[self._active_index]

    def _build_observation(self, agent_message: str) -> MyEnvV4Observation:
        ticket = self._current_ticket()
        queue_remaining = sum(1 for t in self._tickets if not self._progress[t.ticket_id]["closed"])
        snapshot = self._progress[ticket.ticket_id]
        echoed_message = (
            f"Ticket {ticket.ticket_id}: {ticket.text} | SLA={self._remaining_sla[ticket.ticket_id]}m | "
            f"priority_done={snapshot['priority']} team_done={snapshot['team']} "
            f"reply_done={snapshot['reply']} escalated={snapshot['escalated']} closed={snapshot['closed']}"
        )
        return MyEnvV4Observation(
            task_name=self._task_name,
            objective=self._objective,
            step=self._step_count,
            active_ticket_id=ticket.ticket_id,
            ticket_text=ticket.text,
            student_tier=ticket.student_tier,
            channel=ticket.channel,
            sla_minutes_left=self._remaining_sla[ticket.ticket_id],
            queue_remaining=queue_remaining,
            history=self._history[-6:],
            echoed_message=echoed_message if agent_message else ticket.text,
        )

    def _compute_score(self) -> float:
        if not self._tickets:
            return 0.0

        total = 0.0
        for t in self._tickets:
            p = self._progress[t.ticket_id]
            ticket_score = 0.0
            ticket_score += 0.20 if p["priority"] else 0.0
            ticket_score += 0.20 if p["team"] else 0.0
            ticket_score += 0.30 if p["reply"] else 0.0
            if t.needs_escalation:
                ticket_score += 0.10 if p["escalated"] else 0.0
            else:
                ticket_score += 0.10 if not p["escalated"] else 0.0
            ticket_score += 0.20 if p["closed"] else 0.0

            if self._remaining_sla[t.ticket_id] == 0 and not p["closed"]:
                ticket_score -= 0.10

            total += max(ticket_score, 0.0)

        return min(max(total / len(self._tickets), 0.0), 1.0)

    def _is_done(self) -> bool:
        all_closed = all(self._progress[t.ticket_id]["closed"] for t in self._tickets)
        return all_closed or self._step_count >= self._max_steps

    def _build_info(self, error: Optional[str] = None) -> Dict[str, object]:
        return {
            "task_name": self._task_name,
            "normalized_score": round(self._compute_score(), 4),
            "last_action_error": error if error is not None else self._last_action_error,
        }
