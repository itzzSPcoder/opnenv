---
title: Admission Helpdesk OpenEnv
sdk: docker
pinned: false
---

# Admission Helpdesk OpenEnv

A real-world OpenEnv benchmark environment that simulates admissions support operations.
The agent must triage, route, and resolve student tickets while respecting policy and SLA constraints.

## Why this environment

This is not a toy game. It models an actual workflow run by admission teams:
- classify urgency (`low`, `medium`, `high`)
- assign the right queue (`admissions`, `finance`, `tech`, `hostel`)
- draft policy-safe support replies
- escalate only when needed
- close tickets only after meaningful progress

## Action Space

The environment accepts one textual command per step:
- `set_priority(low|medium|high)`
- `assign_team(admissions|finance|tech|hostel)`
- `draft_reply(<text>)`
- `escalate(<reason>)`
- `close_ticket()`
- `next_ticket()`

## Observation Space

Each step returns typed observation fields:
- `task_name`
- `objective`
- `step`
- `active_ticket_id`
- `ticket_text`
- `student_tier`
- `channel`
- `sla_minutes_left`
- `queue_remaining`
- `history`
- `echoed_message`

## Tasks and Graders

The environment includes 3 deterministic graded tasks:
1. `easy_priority_routing` (easy)
2. `medium_resolution` (medium)
3. `hard_sla_queue` (hard)

Each task returns normalized score in `[0.0, 1.0]` via `info.normalized_score`.

## Reward Design

Step rewards provide partial progress:
- positive for correct priority/team routing
- positive for high-quality policy-safe replies
- positive for required escalations
- positive for valid close actions
- penalties for unsafe wording, incorrect routing, unnecessary escalation, and SLA breaches

## Required Submission Files

- `inference.py` (root-level)
- `openenv.yaml`
- `Dockerfile`
- `README.md`

## Local Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run API server (for `/reset` / `/step` / `/state`):

```bash
uvicorn app:app --host 0.0.0.0 --port 7860
```

Run inference for one task:

```bash
set MY_ENV_V4_TASK=easy_priority_routing
set HF_TOKEN=<your_token>
python inference.py
```

Run deterministic baseline over all tasks:

```bash
python scripts/run_baseline.py
```

## Deployment

This repository includes a working `Dockerfile` suitable for Hugging Face Spaces (Docker runtime).
The container exposes port `7860` and serves the environment API with FastAPI.

## Hugging Face Space Setup (Submission Ready)

Use this exact flow to deploy quickly:

1. Create a new Space on Hugging Face.
2. Select Space SDK as Docker.
3. Name it (example: `admission-helpdesk-openenv`).
4. Push this project to that Space repository.
5. Wait for build to complete and open the Space URL.

### Option A: Connect and push with git

1. Create the Space first from UI.
2. In your local project folder, add HF remote and push:

	`git init`

	`git add .`

	`git commit -m "Initial OpenEnv submission"`

	`git remote add hf https://huggingface.co/spaces/<username>/<space-name>`

	`git push hf main`

### Automated Windows flow (recommended)

If you are short on time, use these scripts in order:

1. Create Space (Docker SDK):

```powershell
python scripts/create_hf_space.py --username <hf_username> --space <space_name> --token <hf_token>
```

2. Configure required Space variables/secrets:

```powershell
python scripts/configure_hf_space.py --username <hf_username> --space <space_name> --token <hf_token> --hf-secret <hf_token>
```

3. Commit and push code to Space:

```powershell
scripts\deploy_hf.cmd <hf_username> <space_name> "OpenEnv submission"
```

After push, wait for build completion in Space logs.

### Option B: Upload from Hugging Face UI

1. Open your Space.
2. Go to Files.
3. Upload all repository files.
4. Confirm build logs show success.

### Space Variables and Secrets

In Space settings, add these:

Variables:
- `API_BASE_URL` (example: `https://router.huggingface.co/v1`)
- `MODEL_NAME` (example: `Qwen/Qwen2.5-72B-Instruct`)
- `MY_ENV_V4_BENCHMARK` (optional, default already set)

Secrets:
- `HF_TOKEN` (or `API_KEY`)

Optional:
- `LOCAL_IMAGE_NAME` only if your inference flow uses `from_docker_image(...)`

### Quick Post-Deploy Checks

After Space is live, verify:

1. `POST /reset` returns HTTP 200.
2. `POST /step` works with a sample action payload.
3. `GET /state` returns valid JSON state.
4. Local validator script passes against your Space URL.

Sample checks:

- `curl -X POST https://<space-url>/reset -H "Content-Type: application/json" -d "{}"`
- `curl https://<space-url>/state`

## Validation

Use prevalidation script:

```bash
bash scripts/validate-submission.sh <your_hf_space_url>
```

If you are on Windows without WSL/Git Bash, run the same script from a Linux shell in CI.
