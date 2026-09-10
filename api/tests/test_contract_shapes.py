"""Every route returns something the frozen contract can parse.

This is the test that catches a `/fixtures` regeneration or a careless refactor
turning the wire format into something `contracts/typescript/index.ts` no longer
describes. It parses responses back through the pydantic models rather than
asserting on hand-written keys, so it fails on a *missing* field too, not just a
wrong one.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from quiet_hours_contracts import (
    CONTRACT_VERSION,
    ActivityEntry,
    DailyBrief,
    DecisionCard,
    Household,
    Policy,
    Run,
)

PAGED = [
    ("/api/decisions?status=all", DecisionCard),
    ("/api/runs", Run),
    ("/api/activity", ActivityEntry),
    ("/api/policies", Policy),
]


@pytest.mark.parametrize("path,model", PAGED)
def test_paged_routes_return_contract_models(client: TestClient, path: str, model: type) -> None:
    body = client.get(path).json()
    assert body["contract_version"] == CONTRACT_VERSION
    assert "next_cursor" in body
    assert body["items"], f"{path} served an empty page - run `make fixtures`"
    for item in body["items"]:
        model.model_validate(item)


def test_health_carries_the_contract_version(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["contract_version"] == CONTRACT_VERSION
    assert body["backend"] == "fixtures"


def test_every_response_carries_the_version_header(client: TestClient) -> None:
    for path in ("/api/health", "/api/policies", "/api/brief/latest"):
        assert client.get(path).headers["X-Contract-Version"] == CONTRACT_VERSION


def test_single_decision_round_trips(client: TestClient, pending_card: dict) -> None:
    body = client.get(f"/api/decisions/{pending_card['decision_id']}").json()
    card = DecisionCard.model_validate(body)
    assert card.decision_id == pending_card["decision_id"]


def test_single_run_round_trips(client: TestClient) -> None:
    run_id = client.get("/api/runs").json()["items"][0]["run_id"]
    Run.model_validate(client.get(f"/api/runs/{run_id}").json())


def test_brief_round_trips(client: TestClient) -> None:
    DailyBrief.model_validate(client.get("/api/brief/latest").json())


def test_household_round_trips(client: TestClient) -> None:
    household = Household.model_validate(client.get("/api/household").json())
    assert household.timezone, "the web app needs a timezone to render UTC timestamps"


def test_decision_cards_can_always_be_explained(client: TestClient) -> None:
    """`why_asking` and evidence are what make the agent accountable. A card
    without them renders as an arbitrary demand, so they are checked here rather
    than trusted to the fixture."""
    for item in client.get("/api/decisions?status=all").json()["items"]:
        card = DecisionCard.model_validate(item)
        assert card.why_asking.strip()
        assert card.evidence
        assert len(card.options) >= 2


def test_always_options_preview_the_policy_they_create(client: TestClient) -> None:
    """Autonomy is never granted invisibly: any `*_always` option must say, in
    plain English, what rule it would write."""
    for item in client.get("/api/decisions?status=all").json()["items"]:
        for option in DecisionCard.model_validate(item).options:
            if option.choice.value.endswith("_always"):
                assert option.creates_policy_preview, (
                    f"{item['decision_id']} offers {option.choice.value} with no preview"
                )
