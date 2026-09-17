import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "shop.json"
DEFAULT_TIMEOUT_SECONDS = 42


def load_settings() -> dict[str, object]:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)
