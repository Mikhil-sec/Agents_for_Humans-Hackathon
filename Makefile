# Quiet Hours — one-command entry points.
# Every target below must work on a clean clone with NO credentials.

.PHONY: help demo install agent agent-serve replay api web fixtures test lint clean

help:
	@echo "Quiet Hours"
	@echo ""
	@echo "  make demo      Seed fixtures + run agent + api + web in mock mode (no AWS needed)"
	@echo "  make install   Install all dependencies for all lanes"
	@echo "  make agent     Run the Strands agent locally (mock providers)"
	@echo "  make replay    Replay four weeks and print the autonomy curve"
	@echo "  make agent-serve  Serve the AgentCore entrypoint on :8080 (mock mode)"
	@echo "  make api       Run the FastAPI backend on :8000"
	@echo "  make web       Run the Next.js decision inbox on :3000"
	@echo "  make test      Run every lane's tests"
	@echo "  make lint      Lint every lane"

install:
	cd contracts/python && pip install -e .
	cd integrations && pip install -e .
	cd agent && pip install -e ".[dev]"
	cd api && pip install -e ".[dev]"
	cd web && npm install

demo: fixtures
	@echo "Starting Quiet Hours in mock mode..."
	@echo "  API  -> http://localhost:8000"
	@echo "  Web  -> http://localhost:3000"
	@echo "Run 'make agent' in a second terminal to trigger a daily run."

fixtures:
	python -m quiet_hours_integrations.mock.seed --out fixtures/

agent:
	cd agent && QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run

agent-serve:
	cd agent && QH_PROVIDER_MODE=mock python -m quiet_hours_agent.main

replay:
	cd agent && QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run --replay-weeks 4

api:
	cd api && QH_PROVIDER_MODE=mock uvicorn app.main:app --reload --port 8000

web:
	cd web && npm run dev

test:
	cd agent && pytest -q
	cd api && pytest -q
	cd integrations && pytest -q
	cd web && npm test --if-present

lint:
	ruff check agent api integrations contracts/python
	cd web && npm run lint

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .local/store .local/sessions sessions
	@echo "Cleaned agent state. (.local itself is kept — it holds each dev's private notes.)"
