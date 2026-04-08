#!/usr/bin/env python3
"""Create a GitHub repository via API and optionally make it private."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description="Create GitHub repository")
    parser.add_argument("--token", required=True, help="GitHub PAT with repo scope")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--description", default="OpenEnv submission repository")
    parser.add_argument("--private", action="store_true", help="Create private repo")
    args = parser.parse_args()

    token = args.token.strip()
    payload = {
        "name": args.repo,
        "description": args.description,
        "private": args.private,
        "auto_init": False,
    }

    req = urllib.request.Request(
        "https://api.github.com/user/repos",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "openenv-deployer",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print(body.get("html_url", "Repository created"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 422 and "name already exists" in detail.lower():
            print("Repository already exists, continuing.")
            return
        raise SystemExit(f"GitHub API error {exc.code}: {detail}")


if __name__ == "__main__":
    main()
