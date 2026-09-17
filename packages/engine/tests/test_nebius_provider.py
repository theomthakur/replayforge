import json

import httpx
import pytest
from benchtrace.providers import ProviderConfig, ProviderError
from benchtrace.trace import Message, ToolDefinition, TraceRequest
from replayforge.providers.nebius import NebiusTokenFactoryProvider, is_nvidia_model

CATALOG = {
    "data": [
        {"id": "nvidia/Example-Nemotron-Model", "owned_by": "nvidia"},
        {"id": "meta-llama/Example-Llama", "owned_by": "meta"},
        {"id": "custom/allowlisted", "owned_by": "someone"},
    ]
}


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_catalog_filters_nvidia_and_allowlist(monkeypatch):
    monkeypatch.setenv("REPLAYFORGE_NVIDIA_MODEL_ALLOWLIST", "custom/allowlisted")

    def handler(request):
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.url.path.endswith("/models")
        return httpx.Response(200, json=CATALOG)

    provider = NebiusTokenFactoryProvider("test-key", base_url="https://example.test/v1/", client=_client(handler))
    catalog = await provider.list_models()
    assert [m.id for m in catalog.nvidia] == ["nvidia/Example-Nemotron-Model", "custom/allowlisted"]


async def test_catalog_requires_key():
    provider = NebiusTokenFactoryProvider(
        "", base_url="https://example.test/v1/", client=_client(lambda r: httpx.Response(200))
    )
    with pytest.raises(ProviderError):
        await provider.list_models()


async def test_completion_normalizes_tool_calls_and_usage():
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "nvidia/Example-Nemotron-Model"
        assert body["tools"][0]["function"]["name"] == "read_file"
        return httpx.Response(
            200,
            json={
                "id": "req-123",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": '{"path": "shop/cart.py"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30},
            },
        )

    provider = NebiusTokenFactoryProvider("k", base_url="https://example.test/v1/", client=_client(handler))
    request = TraceRequest(
        messages=[Message(role="user", content="hi")],
        tools=[ToolDefinition(name="read_file", description="d", parameters={"type": "object"})],
    )
    result = await provider.complete(request, "nvidia/Example-Nemotron-Model")
    assert result.response.provider_response_id == "req-123"
    assert result.response.tool_calls[0].arguments == {"path": "shop/cart.py"}
    assert result.usage.input_tokens == 120 and result.usage.output_tokens == 30
    assert result.pricing_known is False  # no Nebius price in the snapshot: cost stays unknown


async def test_transient_errors_retry_terminal_errors_do_not():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503 if calls["n"] == 1 else 400, text="nope")

    async def no_sleep(_):
        return None

    provider = NebiusTokenFactoryProvider(
        "k",
        base_url="https://example.test/v1/",
        client=_client(handler),
        config=ProviderConfig(max_retries=3, sleeper=no_sleep),
    )
    with pytest.raises(ProviderError) as error:
        await provider.complete(TraceRequest(messages=[Message(role="user", content="x")]), "m")
    assert calls["n"] == 2 and error.value.status_code == 400


def test_nvidia_detection():
    assert is_nvidia_model("nvidia/anything", None, set())
    assert not is_nvidia_model("meta/llama", "meta", set())
