"""Nebius Token Factory: OpenAI-compatible inference plus live model-catalog discovery.

No model identifier is hardcoded. Candidates come from the account's live ``/models`` response,
filtered to NVIDIA entries by provider metadata or an explicit allowlist, and are validated with a
small completion before an experiment may use them.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from benchtrace.providers import OpenAICompatibleProvider, ProviderConfig, ProviderError
from benchtrace.trace import Message, TraceRequest

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


@dataclass(frozen=True, slots=True)
class CatalogModel:
    id: str
    owned_by: str | None
    is_nvidia: bool
    raw: dict[str, object]


@dataclass(frozen=True, slots=True)
class Catalog:
    fetched_at: datetime
    base_url: str
    models: tuple[CatalogModel, ...]

    @property
    def nvidia(self) -> tuple[CatalogModel, ...]:
        return tuple(m for m in self.models if m.is_nvidia)


def _allowlist() -> set[str]:
    raw = os.environ.get("REPLAYFORGE_NVIDIA_MODEL_ALLOWLIST", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def is_nvidia_model(model_id: str, owned_by: str | None, allowlist: set[str] | None = None) -> bool:
    allowed = _allowlist() if allowlist is None else allowlist
    if model_id in allowed:
        return True
    lowered = model_id.lower()
    return lowered.startswith("nvidia/") or "nemotron" in lowered or (owned_by or "").lower() == "nvidia"


class NebiusTokenFactoryProvider(OpenAICompatibleProvider):
    """Token Factory adapter conforming to benchtrace's Provider interface."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        config: ProviderConfig | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("NEBIUS_TOKEN_FACTORY_API_KEY", "")
        url = base_url or os.environ.get("NEBIUS_TOKEN_FACTORY_BASE_URL") or DEFAULT_BASE_URL
        super().__init__(name="nebius", base_url=url, api_key=key, client=client, config=config)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def list_models(self) -> Catalog:
        if not self.api_key:
            raise ProviderError("NEBIUS_TOKEN_FACTORY_API_KEY is not set", retryable=False)
        try:
            response = await self._client.get(
                f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"}
            )
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise ProviderError(str(error), retryable=True) from error
        if response.is_error:
            raise ProviderError(
                f"model catalog returned HTTP {response.status_code}",
                status_code=response.status_code,
                retryable=response.status_code >= 500,
            )
        payload = response.json()
        entries = payload.get("data", []) if isinstance(payload, dict) else []
        allow = _allowlist()
        models = tuple(
            CatalogModel(
                id=str(item.get("id")),
                owned_by=item.get("owned_by"),
                is_nvidia=is_nvidia_model(str(item.get("id")), item.get("owned_by"), allow),
                raw=item,
            )
            for item in entries
            if isinstance(item, dict) and item.get("id")
        )
        return Catalog(fetched_at=datetime.now(UTC), base_url=self.base_url, models=models)

    async def validate_model(self, model: str) -> dict[str, object]:
        """Run a tiny completion and return the evidence needed to mark a model ready."""

        started = time.perf_counter()
        result = await self.complete(
            TraceRequest(
                messages=[Message(role="user", content="Reply with the single word: ready")],
                max_tokens=8,
                temperature=0.0,
            ),
            model,
        )
        return {
            "model": model,
            "ok": True,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "provider_response_id": result.response.provider_response_id,
            "finish_reason": result.response.finish_reason,
            "usage": result.usage.model_dump(),
        }
