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

# `make demo` is the judge's entry point and the README sends them straight to
# http://localhost:3000 afterwards -- so it has to actually serve something.
# It used to print these three lines and exit, which left that browser tab blank.
#
# `$(MAKE) -j2 api web` runs both targets in parallel. Deliberately not shell
# backgrounding with `&` and `wait`: -j is make's own job control, so one Ctrl+C
# stops both and there is no process-group trap to get subtly wrong.
demo: fixtures
	@echo ""
	@echo "Starting Quiet Hours in mock mode. No AWS account, no credentials."
	@echo "  API  -> http://localhost:8000"
	@echo "  Web  -> http://localhost:3000     <- open this"
	@echo ""
	@echo "The web app takes 10-20 seconds to compile on a cold start."
	@echo "Run 'make agent' in a second terminal to trigger a daily run."
	@echo "Ctrl+C stops both."
	@echo ""
	@$(MAKE) -j2 api web

# /fixtures is produced in two stages, and both must run in this order.
#
#   1. Lane C's seeder writes the RAW household world -- inbox, transactions,
#      calendar, merchant history, and the scenario manifest. Anchored to a fixed
#      reference date so a re-seed a year from now produces the same world.
#   2. Lane A's exporter runs the agent for real against that world and writes the
#      DERIVED records Lane B renders -- decisions, activity, policies, runs and
#      the daily brief. Generated rather than hand-written, so they cannot drift
#      out of contract.
#
# This was `seed || export` while Lane C's seeder was a stub that raised. It
# writes files now, so the fallback was dead code hiding a real ordering: the
# exporter is downstream of the seeder, not an alternative to it.
fixtures:
	python -m quiet_hours_integrations.mock.seed --out fixtures/
	python -m quiet_hours_agent.export_fixtures --out fixtures/

agent:
	cd agent && QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run

agent-serve:
	cd agent && QH_PROVIDER_MODE=mock python -m quiet_hours_agent.main

replay:
	cd agent && QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run --replay-weeks 4

# **No `VAR=value` prefix here, deliberately.** That is POSIX syntax, and GNU
# Make on Windows uses cmd.exe as its shell unless sh.exe is on PATH — so this
# target worked from Git Bash, macOS and Linux, and on a native Windows shell
# died with "'QH_PROVIDER_MODE' is not recognized", taking `make demo` with it
# and rendering every screen's error state. Found by Diya, 11 Sept.
#
# The fix is a deletion rather than a rewrite because nothing in /api reads
# QH_PROVIDER_MODE. The API's switch is QH_BACKEND, which already defaults to
# `fixtures` in api/app/config.py, so mock mode is what an unset environment
# gets. The other targets below keep the prefix: they are Lane A entry points
# that genuinely read it, and `make agent` is not on the judge's path.
api:
	cd api && uvicorn main:app --reload --port 8000

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
