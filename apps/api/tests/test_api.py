import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "whsec")
    monkeypatch.delenv("NEBIUS_TOKEN_FACTORY_API_KEY", raising=False)
    from replayforge_api import db

    db._factory = None
    db.init_db(f"sqlite:///{tmp_path / 'test.db'}")
    from replayforge_api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def _wait(client, experiment_id, status="completed", timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/experiments/{experiment_id}").json()
        if snap["status"] in (status, "failed", "cancelled"):
            return snap
        time.sleep(0.3)
    raise AssertionError(f"experiment did not reach {status}: {snap['status']}")


def _create(client, tasks, key=None):
    suite = client.post("/api/suites", json={"path": "demo-suite.yaml"}).json()
    body = {
        "suite_id": suite["id"],
        "baseline": {"provider": "fixture", "model": "fixture/reference"},
        "candidate": {"provider": "fixture", "model": "fixture/variant"},
        "task_ids": tasks,
    }
    headers = {"Idempotency-Key": key} if key else {}
    return client.post("/api/experiments", json=body, headers=headers)


def test_health_ready_and_models_report_missing_keys(client):
    assert client.get("/health").json() == {"ok": True}
    ready = client.get("/ready").json()
    assert "NEBIUS_TOKEN_FACTORY_API_KEY" in ready["missing_configuration"]
    models = client.get("/api/models").json()
    assert models["nebius"]["configured"] is False and len(models["fixture"]) == 2


def test_idempotent_creation(client):
    first = _create(client, ["repair-slug"], key="abc").json()
    second = _create(client, ["repair-slug"], key="abc").json()
    assert first["id"] == second["id"]
    assert len(first["git_sha"]) == 40


def test_live_nebius_lane_requires_server_key(client):
    suite = client.post("/api/suites", json={"path": "demo-suite.yaml"}).json()
    response = client.post(
        "/api/experiments",
        json={
            "suite_id": suite["id"],
            "baseline": {"provider": "fixture", "model": "fixture/reference"},
            "candidate": {"provider": "nebius", "model": "unverified/model"},
            "task_ids": ["repair-slug"],
        },
    )
    assert response.status_code == 422
    assert "NEBIUS_TOKEN_FACTORY_API_KEY" in response.text


def test_full_fixture_experiment_persists_events_pairs_and_decision(client):
    experiment = _create(client, ["repair-discount", "tool-find-timeout", "repair-slug"]).json()
    assert experiment["status"] == "ready" and experiment["fixture_mode"] is True
    assert client.post(f"/api/experiments/{experiment['id']}/start").json()["started"]
    snap = _wait(client, experiment["id"])
    assert snap["status"] == "completed"
    assert len(snap["runs"]) == 6 and len(snap["pairs"]) == 3
    assert snap["decision"]["outcome"] == "block"
    regressed = {p["task_id"]: p for p in snap["pairs"]}
    assert regressed["repair-discount"]["investigation"]["category"] == "malformed_arguments"
    assert any(m["name"] == "cost_per_success_usd" and m["value"] is None for m in snap["metrics"])

    log = client.get(f"/api/experiments/{experiment['id']}/event-log").json()
    types = [e["type"] for e in log]
    assert types[0] == "experiment.created" and types[-1] == "experiment.completed"
    assert types.index("policy.evaluated") < types.index("experiment.completed")
    assert [e["seq"] for e in log] == sorted(e["seq"] for e in log)
    resumed = client.get(f"/api/experiments/{experiment['id']}/event-log", params={"after": log[5]["seq"]}).json()
    assert resumed[0]["seq"] == log[6]["seq"]

    run_id = regressed["repair-discount"]["candidate_run_id"]
    trace = client.get(f"/api/runs/{run_id}/trace").json()
    assert any(step["error_kind"] == "malformed_arguments" for step in trace["steps"])
    assert any(not grade["passed"] for grade in trace["grades"])
    report = client.get(f"/api/experiments/{experiment['id']}/report.md").text
    assert "Fixture mode" in report and "BLOCK" in report


def test_resume_does_not_duplicate_completed_runs(client):
    import asyncio

    from replayforge_api.services import orchestrator

    experiment = _create(client, ["repair-slug", "repair-cart-total"]).json()
    experiment_id = experiment["id"]
    client.post(f"/api/experiments/{experiment_id}/start")
    _wait(client, experiment_id)
    first = client.get(f"/api/experiments/{experiment_id}").json()
    # Simulate a restart mid-analysis: mark running again and resume.
    from replayforge_api.db import Experiment, session_scope

    with session_scope() as session:
        session.get(Experiment, experiment_id).status = "running"
    client.portal.call(lambda: asyncio.sleep(0))
    client.portal.start_task_soon(orchestrator._run, experiment_id)
    snap = _wait(client, experiment_id)
    assert len(snap["runs"]) == len(first["runs"]) == 4
    assert snap["decision"]["outcome"] == first["decision"]["outcome"]


def test_webhook_signature_and_dedupe(client):
    body = b'{"action":"opened"}'
    signature = "sha256=" + hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    headers = {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Delivery": "d-1",
        "X-GitHub-Event": "pull_request",
        "Content-Type": "application/json",
    }
    assert client.post("/webhooks/github", content=body, headers=headers).json()["accepted"]
    assert client.post("/webhooks/github", content=body, headers=headers).json()["duplicate"]
    bad = dict(headers, **{"X-Hub-Signature-256": "sha256=bad"})
    assert client.post("/webhooks/github", content=body, headers=bad).status_code == 401


def test_unknown_suite_path_rejected(client):
    assert client.post("/api/suites", json={"path": "../../etc/passwd"}).status_code == 404


def test_publish_requires_decision_and_token(client, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    experiment = _create(client, ["repair-slug"]).json()
    assert client.post(f"/api/experiments/{experiment['id']}/publish-github", json={}).status_code == 409
    client.post(f"/api/experiments/{experiment['id']}/start")
    _wait(client, experiment["id"])
    response = client.post(
        f"/api/experiments/{experiment['id']}/publish-github",
        json={"pull_request_url": "https://github.com/o/r/pull/1"},
    )
    assert response.status_code == 502
    snap = client.get(f"/api/experiments/{experiment['id']}").json()
    assert snap["decision"]["delivery_status"] == "failed"
