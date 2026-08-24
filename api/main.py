from typing import Optional
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import CONTRACT_VERSION
from fixtures_server import load_fixture, get_paged_fixture

app = FastAPI(
    title="Quiet Hours API",
    version=CONTRACT_VERSION,
    description="FastAPI backend for Quiet Hours Decision Inbox"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_contract_version_header(request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Contract-Version"] = CONTRACT_VERSION
    return response

class DecisionRespondPayload(BaseModel):
    option_id: str
    session_id: str
    interrupt_id: str
    interrupt_name: str

@app.get("/api/health")
async def get_health():
    return {
        "status": "ok",
        "contract_version": CONTRACT_VERSION
    }

@app.get("/api/decisions")
async def list_decisions(status: Optional[str] = "pending"):
    return get_paged_fixture("decisions.json", status_filter=status)

@app.get("/api/decisions/{decision_id}")
async def get_decision(decision_id: str):
    decisions = load_fixture("decisions.json")
    if isinstance(decisions, list):
        for card in decisions:
            if card.get("id") == decision_id:
                return card
    raise HTTPException(status_code=404, detail="Decision card not found")

@app.post("/api/decisions/{decision_id}/respond")
async def respond_decision(decision_id: str, payload: DecisionRespondPayload):
    return {
        "run_id": f"run_{decision_id}",
        "status": "resumed",
        "decision_id": decision_id,
        "selected_option_id": payload.option_id,
        "session_id": payload.session_id,
        "interrupt_id": payload.interrupt_id,
        "interrupt_name": payload.interrupt_name
    }

@app.get("/api/runs")
async def list_runs():
    return get_paged_fixture("runs.json")

@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    runs = load_fixture("runs.json")
    if isinstance(runs, list):
        for run in runs:
            if run.get("id") == run_id:
                return run
    return {"id": run_id, "status": "completed"}

@app.post("/api/runs")
async def trigger_run():
    return {
        "run_id": "run_demo_trigger",
        "status": "queued",
        "message": "Agent run triggered successfully"
    }

@app.get("/api/activity")
async def list_activity(autonomous: Optional[bool] = None):
    return get_paged_fixture("activity.json")

@app.get("/api/policies")
async def list_policies():
    return get_paged_fixture("policies.json")

@app.delete("/api/policies/{policy_id}")
async def revoke_policy(policy_id: str):
    return {
        "id": policy_id,
        "status": "revoked"
    }

@app.get("/api/brief/latest")
async def get_latest_brief():
    return load_fixture("daily_brief.json")