import argparse
import json

import httpx
import pytest
from benchtrace.trace import Message, ToolDefinition, TraceRequest
from replayforge.cli import _run
from replayforge.providers import LaneConfig, build_provider


def test_local_provider_rejects_non_loopback(monkeypatch, suite):
    monkeypatch.setenv("REPLAYFORGE_LOCAL_BASE_URL", "http://example.com/v1")
    with pytest.raises(ValueError, match="loopback"):
        build_provider(LaneConfig("local", "model"), cassette=suite.cassette, solutions_dir=suite.source_path.parent)


async def test_local_provider_sends_tools_and_preserves_usage(monkeypatch, suite):
    monkeypatch.setenv("REPLAYFORGE_LOCAL_BASE_URL", "http://127.0.0.1:11434/v1")
    provider = build_provider(
        LaneConfig("local", "test-model"), cassette=suite.cassette, solutions_dir=suite.source_path.parent
    )
    await provider.aclose()

    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["tools"][0]["function"]["name"] == "read_file"
        return httpx.Response(
            200,
            json={
                "id": "local-test",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {"name": "read_file", "arguments": '{"path":"README.md"}'},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )

    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await provider.complete(
            TraceRequest(
                messages=[Message(role="user", content="read")],
                tools=[ToolDefinition(name="read_file", description="read", parameters={"type": "object"})],
            ),
            "test-model",
        )
        assert result.response.tool_calls[0].arguments == {"path": "README.md"}
        assert result.usage.input_tokens == 5
        assert not result.pricing_known
    finally:
        await provider.aclose()


async def test_cli_refuses_existing_output_without_touching_it(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    trace = output / "traces-baseline.jsonl"
    trace.write_text("prior evidence\n")
    args = argparse.Namespace(suite="fixtures/suites/demo-suite.yaml", out=str(output))
    assert await _run(args) == 1
    assert trace.read_text() == "prior evidence\n"
