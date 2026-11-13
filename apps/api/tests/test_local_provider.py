import pytest
from fastapi import HTTPException
from replayforge_api.routes.api import LaneBody, _allowed_lane, models


async def test_local_models_are_listed_without_inference(monkeypatch):
    monkeypatch.setenv("REPLAYFORGE_LOCAL_MODELS", " qwen2.5:3b, llama3.2:latest ")
    monkeypatch.delenv("NEBIUS_TOKEN_FACTORY_API_KEY", raising=False)
    response = await models()
    assert [entry["model"] for entry in response["local"]] == ["qwen2.5:3b", "llama3.2:latest"]


async def test_local_lane_requires_allowlisted_model_and_loopback(monkeypatch):
    monkeypatch.setenv("REPLAYFORGE_LOCAL_MODELS", "qwen2.5:3b")
    monkeypatch.setenv("REPLAYFORGE_LOCAL_BASE_URL", "http://127.0.0.1:11434/v1")
    await _allowed_lane(LaneBody(provider="local", model="qwen2.5:3b"))
    with pytest.raises(HTTPException) as missing:
        await _allowed_lane(LaneBody(provider="local", model="other"))
    assert missing.value.status_code == 422
    monkeypatch.setenv("REPLAYFORGE_LOCAL_BASE_URL", "http://example.org/v1")
    with pytest.raises(HTTPException) as unsafe:
        await _allowed_lane(LaneBody(provider="local", model="qwen2.5:3b"))
    assert unsafe.value.status_code == 422
