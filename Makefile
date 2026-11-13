.PHONY: install test lint web-test web-build api web fixture-run live-smoke

install:
	uv sync --python 3.12 --all-packages
	cd apps/web && npm ci

test:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/ruff check apps packages
	.venv/bin/ruff format --check apps packages

web-test:
	cd apps/web && npx tsc -b --noEmit && npx vitest run

web-build:
	cd apps/web && npm run build

api:
	.venv/bin/uvicorn replayforge_api.main:app --host 127.0.0.1 --port 8000

web:
	cd apps/web && npx vite --port 5173

fixture-run:
	.venv/bin/replayforge run --suite fixtures/suites/demo-suite.yaml --baseline fixture:fixture/reference --candidate fixture:fixture/variant --out data/runs/fixture-$$(date +%Y%m%d-%H%M%S)-$$$$

live-smoke:
	.venv/bin/python scripts/live_smoke.py
