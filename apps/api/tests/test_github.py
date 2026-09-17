import httpx
import pytest
from replayforge_api.github import GitHubClient, GitHubError, check_run_payload, parse_pr_url


def test_parse_pr_url():
    ref = parse_pr_url("https://github.com/theomthakur/replayforge-demo/pull/3")
    assert (ref.owner, ref.repo, ref.number) == ("theomthakur", "replayforge-demo", 3)
    with pytest.raises(GitHubError):
        parse_pr_url("https://gitlab.com/x/y/pull/1")


@pytest.mark.parametrize(("outcome", "conclusion"), [("pass", "success"), ("warn", "neutral"), ("block", "failure")])
def test_payload_conclusion(outcome, conclusion):
    payload = check_run_payload(
        head_sha="abc", outcome=outcome, title="t", summary="s", details_url="u", external_id="e"
    )
    assert payload["conclusion"] == conclusion


async def test_retry_updates_existing_check_instead_of_duplicating():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json={"check_runs": [{"id": 9, "external_id": "replayforge-x"}]})
        return httpx.Response(200, json={"id": 9, "html_url": "https://github.com/o/r/runs/9"})

    client = GitHubClient("t", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    ref = parse_pr_url("https://github.com/o/r/pull/1")
    payload = check_run_payload(
        head_sha="abc", outcome="warn", title="t", summary="s", details_url="u", external_id="replayforge-x"
    )
    result = await client.upsert_check_run(ref, payload)
    assert result["id"] == 9
    assert ("PATCH", "/repos/o/r/check-runs/9") in seen and not any(m == "POST" for m, _ in seen)
