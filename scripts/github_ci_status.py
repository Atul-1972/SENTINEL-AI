"""Read GitHub Actions status using the account already held by Git Credential Manager.

Credentials stay in memory and are used only with api.github.com. This script
does not accept, print, or store tokens and makes no write requests to GitHub.
"""

import argparse
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def github_token(repository):
    result = subprocess.run(
        ["git", "-c", "credential.interactive=never", "credential", "fill"],
        input=f"protocol=https\nhost=github.com\npath={repository}.git\n\n",
        text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise SystemExit("No available GitHub credential. Sign in through Git Credential Manager or inspect the Actions page in your browser.")
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if not fields.get("password"):
        raise SystemExit("Git Credential Manager did not return a GitHub credential.")
    return fields["password"]


def api_get(route, token):
    req = urllib.request.Request(
        "https://api.github.com" + route,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sentinel-ai-ci-verification",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"GitHub API returned HTTP {error.code}. No credential values were logged.") from None


def inspect_run(repository, sha, token):
    query = urllib.parse.urlencode({"head_sha": sha, "event": "push", "per_page": 10})
    runs = api_get(f"/repos/{repository}/actions/runs?{query}", token)["workflow_runs"]
    runs = [run for run in runs if run["path"] == ".github/workflows/ci.yml"]
    if not runs:
        return {"status": "not_found", "head_sha": sha}
    run = runs[0]
    jobs = api_get(f"/repos/{repository}/actions/runs/{run['id']}/jobs?per_page=100", token)["jobs"]
    return {
        "repository": repository, "run_id": run["id"], "head_sha": run["head_sha"],
        "run_number": run["run_number"], "status": run["status"],
        "conclusion": run["conclusion"], "html_url": run["html_url"],
        "jobs": [{
            "name": job["name"], "status": job["status"], "conclusion": job["conclusion"],
            "html_url": job["html_url"],
            "failed_steps": [step["name"] for step in job["steps"] if step.get("conclusion") == "failure"],
        } for job in jobs],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="Atul-1972/SENTINEL-AI")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("Expected OWNER/REPOSITORY.")
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("Expected a full 40-character commit SHA.")
    token = github_token(args.repository)
    deadline = time.monotonic() + args.timeout
    previous = None
    while True:
        result = inspect_run(args.repository, args.sha, token)
        summary = json.dumps(result, indent=2)
        if summary != previous:
            print(summary, flush=True)
            previous = summary
        if not args.wait or result["status"] == "completed":
            break
        if time.monotonic() >= deadline:
            raise SystemExit("Timed out waiting for GitHub Actions; the remote run may still be active.")
        time.sleep(10)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(summary + "\n", encoding="utf-8")
    if result.get("conclusion") != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
