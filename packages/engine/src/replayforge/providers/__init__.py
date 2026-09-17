"""Provider construction for baseline and candidate lanes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from benchtrace.providers import Provider, ProviderConfig, provider_for_model
from benchtrace.providers.pricing import PricingTable, load_pricing_file

from replayforge.cassettes.schema import Cassette
from replayforge.providers.fixture import FIXTURE_PROFILES, FixtureProvider
from replayforge.providers.nebius import Catalog, CatalogModel, NebiusTokenFactoryProvider


@dataclass(frozen=True, slots=True)
class LaneConfig:
    """``provider`` is one of fixture | nebius | benchtrace (any benchtrace model prefix)."""

    provider: str
    model: str
    temperature: float | None = 0.0
    seed: int | None = 7
    max_tokens: int | None = 2048
    pricing_file: str | None = None

    def label(self) -> str:
        return f"{self.provider}:{self.model}"


def build_provider(
    lane: LaneConfig,
    *,
    cassette: Cassette,
    solutions_dir: Path,
    max_concurrency: int = 3,
) -> Provider:
    pricing: PricingTable | None = load_pricing_file(lane.pricing_file) if lane.pricing_file else None
    config = ProviderConfig(max_concurrency=max_concurrency, pricing_table=pricing)
    if lane.provider == "fixture":
        if lane.model not in FIXTURE_PROFILES:
            raise ValueError(f"unknown fixture profile {lane.model!r}; choose one of {sorted(FIXTURE_PROFILES)}")
        return FixtureProvider(
            cassette,
            solutions_dir,
            config=ProviderConfig(max_retries=0, max_concurrency=max_concurrency),
        )
    if lane.provider == "nebius":
        return NebiusTokenFactoryProvider(config=config)
    if lane.provider == "benchtrace":
        return provider_for_model(lane.model, max_concurrency=max_concurrency)
    raise ValueError(f"unknown provider {lane.provider!r}")


__all__ = [
    "Catalog",
    "CatalogModel",
    "FixtureProvider",
    "FIXTURE_PROFILES",
    "LaneConfig",
    "NebiusTokenFactoryProvider",
    "build_provider",
]
