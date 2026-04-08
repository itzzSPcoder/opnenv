#!/usr/bin/env python3
"""Configure Hugging Face Space variables/secrets for this OpenEnv project."""

from __future__ import annotations

import argparse
import os

from huggingface_hub import HfApi


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure Hugging Face Space variables/secrets")
    parser.add_argument("--username", required=True, help="Hugging Face username or org")
    parser.add_argument("--space", required=True, help="Space name")
    parser.add_argument("--token", default=os.getenv("HF_TOKEN"), help="HF token (or set HF_TOKEN env)")
    parser.add_argument("--api-base-url", default=os.getenv("API_BASE_URL", "https://router.huggingface.co/v1"))
    parser.add_argument("--model-name", default=os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct"))
    parser.add_argument("--hf-secret", default=os.getenv("HF_TOKEN") or os.getenv("API_KEY"))
    args = parser.parse_args()

    args.token = (args.token or "").strip()
    args.hf_secret = (args.hf_secret or "").strip() if args.hf_secret else None

    if not args.token:
        raise SystemExit("Missing --token (or set HF_TOKEN)")

    repo_id = f"{args.username}/{args.space}"
    api = HfApi(token=args.token)

    api.add_space_variable(repo_id=repo_id, key="API_BASE_URL", value=args.api_base_url)
    api.add_space_variable(repo_id=repo_id, key="MODEL_NAME", value=args.model_name)

    if args.hf_secret:
        api.add_space_secret(repo_id=repo_id, key="HF_TOKEN", value=args.hf_secret)

    print(f"Configured variables for space: {repo_id}")


if __name__ == "__main__":
    main()
