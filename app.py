from fastapi import FastAPI
from pydantic import BaseModel

from my_env_v4 import MyEnvV4Action, MyEnvV4Env, TASK_GRADERS, TASK_LIBRARY

app = FastAPI(title="Admission Helpdesk OpenEnv", version="1.0.0")
_env = MyEnvV4Env()


class ResetRequest(BaseModel):
    task_name: str | None = None


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "admission-helpdesk-openenv",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/metadata")
async def metadata() -> dict[str, str]:
    return {
        "name": "admission-helpdesk-openenv",
        "description": "Real-world admissions support environment where an agent triages, routes, replies to, and closes student support tickets under SLA constraints.",
    }


@app.get("/schema")
async def schema() -> dict[str, object]:
    return {
        "action": MyEnvV4Action.model_json_schema(),
        "observation": MyEnvV4Env.observation_schema() if hasattr(MyEnvV4Env, 'observation_schema') else {"type": "object"},
        "state": {"type": "object"},
    }


@app.post("/reset")
async def reset(payload: ResetRequest | None = None) -> dict:
    result = await _env.reset(task_name=(payload.task_name if payload else None))
    return result.model_dump()


@app.get("/tasks")
async def tasks() -> dict[str, object]:
    return {
        "tasks": [
            {
                "id": task_id,
                "difficulty": task_meta.get("difficulty", "unknown"),
                "description": task_meta.get("objective"),
                "objective": task_meta.get("objective"),
                "grader": TASK_GRADERS.get(task_id),
                "grader_fn": TASK_GRADERS.get(task_id),
                "agent_grader": TASK_GRADERS.get(task_id),
                "score_range": [0.0, 1.0],
            }
            for task_id, task_meta in TASK_LIBRARY.items()
        ]
    }


@app.post("/step")
async def step(action: MyEnvV4Action) -> dict:
    result = await _env.step(action)
    return result.model_dump()


@app.get("/state")
async def state() -> dict:
    return await _env.state()


@app.post("/close")
async def close() -> dict[str, str]:
    await _env.close()
    return {"status": "closed"}
