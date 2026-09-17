"""GitHub release gate: check runs and verified, deduplicated webhooks.

Uses a fine-grained token (GITHUB_TOKEN) with checks:write on the demo repository. A GitHub App
installation token can be substituted later without changing the check-run payload.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

import httpx
from replayforge.policy import GITHUB_CONCLUSION

API = "https://api.github.com"
PR_URL = re.compile(r"^https://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/pull/(?P<number>\d+)/?$")


class GitHubError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PullRequestRef:
    owner: str
    repo: str
    number: int


def parse_pr_url(url: str) -> PullRequestRef:
    match = PR_URL.match(url.strip())
    if not match:
        raise GitHubError("expected a URL like https://github.com/owner/repo/pull/123")
    return PullRequestRef(match["owner"], match["repo"], int(match["number"]))


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def check_run_payload(
    *, head_sha: str, outcome: str, title: str, summary: str, details_url: str, external_id: str
) -> dict:
    return {
        "name": "ReplayForge migration gate",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": GITHUB_CONCLUSION[outcome],
        "external_id": external_id,
        "details_url": details_url,
        "output": {"title": title[:250], "summary": summary[:60000]},
    }


class GitHubClient:
    def __init__(self, token: str, client: httpx.AsyncClient | None = None) -> None:
        if not token:
            raise GitHubError("GITHUB_TOKEN is not set")
        self._client = client or httpx.AsyncClient(timeout=20.0)
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def pull_request_head(self, ref: PullRequestRef) -> str:
        response = await self._client.get(
            f"{API}/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}", headers=self._headers
        )
        if response.is_error:
            raise GitHubError(f"GitHub returned {response.status_code} for the pull request")
        return str(response.json()["head"]["sha"])

    async def find_existing_check(self, ref: PullRequestRef, head_sha: str, external_id: str) -> dict | None:
        response = await self._client.get(
            f"{API}/repos/{ref.owner}/{ref.repo}/commits/{head_sha}/check-runs",
            headers=self._headers,
            params={"check_name": "ReplayForge migration gate"},
        )
        if response.is_error:
            return None
        for run in response.json().get("check_runs", []):
            if run.get("external_id") == external_id:
                return run
        return None

    async def upsert_check_run(self, ref: PullRequestRef, payload: dict) -> dict:
        """Create the check once per experiment; retries update the same check instead of duplicating."""

        existing = await self.find_existing_check(ref, payload["head_sha"], payload["external_id"])
        if existing:
            response = await self._client.patch(
                f"{API}/repos/{ref.owner}/{ref.repo}/check-runs/{existing['id']}",
                headers=self._headers,
                json={k: v for k, v in payload.items() if k != "head_sha"},
            )
        else:
            response = await self._client.post(
                f"{API}/repos/{ref.owner}/{ref.repo}/check-runs", headers=self._headers, json=payload
            )
        if response.is_error:
            raise GitHubError(f"GitHub returned {response.status_code}: {response.text[:200]}")
        return response.json()

    async def aclose(self) -> None:
        await self._client.aclose()
