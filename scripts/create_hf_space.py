#!/usr/bin/env python3
"""Create a Hugging Face Docker Space for this submission."""

from __future__ import annotations

import argparse
import os

from huggingface_hub import HfApi


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Hugging Face Docker Space")
    parser.add_argument("--username", required=True, help="Hugging Face username or org")
    parser.add_argument("--space", required=True, help="Space name")
    parser.add_argument("--token", default=os.getenv("HF_TOKEN"), help="HF token (or set HF_TOKEN env)")
    parser.add_argument("--private", action="store_true", help="Create private space")
    args = parser.parse_args()

    args.token = (args.token or "").strip()

    if not args.token:
        raise SystemExit("Missing --token (or set HF_TOKEN)")

    repo_id = f"{args.username}/{args.space}"
    api = HfApi(token=args.token)

    api.create_repo(
        repo_id=repo_id,
        repo_type="space",
        space_sdk="docker",
        private=args.private,
        exist_ok=True,
    )

    print(f"Space ready: https://huggingface.co/spaces/{repo_id}")


if __name__ == "__main__":
    main()
