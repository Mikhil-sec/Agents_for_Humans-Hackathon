"""Answering a card: the one write path in the product.

The behaviour pinned here is the behaviour the demo depends on. A card that stays
in the inbox after being answered, or an `approve_always` that grants autonomy
without writing the rule it promised, breaks the story the whole product tells.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def _answer(card: dict, choice: str, **extra) -> dict:
    return {
        "decision_id": card["decision_id"],
        "choice": choice,
        "edited_params": None,
        "snooze_until": None,
        "note": None,
        "responded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        **extra,
    }


def test_approve_resolves_the_card_and_empties_the_inbox(
    client: TestClient, pending_card: dict
) -> None:
    before = len(client.get("/api/decisions?status=pending").json()["items"])

    result = client.post(
        f"/api/decisions/{pending_card['decision_id']}/respond",
        json=_answer(pending_card, "approve"),
    )
    assert result.status_code == 200
    assert result.json()["run_id"] == pending_card["run_id"]

    after = client.get("/api/decisions?status=pending").json()["items"]
    assert len(after) == before - 1

    card = client.get(f"/api/decisions/{pending_card['decision_id']}").json()
    assert card["status"] == "resolved"
    assert card["resolved_at"] is not None


def test_approve_always_creates_exactly_the_policy_it_previewed(
    client: TestClient, pending_card: dict
) -> None:
    option = next(o for o in pending_card["options"] if o["choice"] == "approve_always")
    before = {p["policy_id"] for p in client.get("/api/policies").json()["items"]}

    client.post(
        f"/api/decisions/{pending_card['decision_id']}/respond",
        json=_answer(pending_card, "approve_always"),
    )

    policies = client.get("/api/policies").json()["items"]
    created = [p for p in policies if p["policy_id"] not in before]
    assert len(created) == 1
    # The user agreed to these exact words. The policies page must not show them
    # different ones.
    assert created[0]["description"] == option["creates_policy_preview"]
    assert created[0]["effect"] == "auto_approve"
    assert created[0]["created_from_decision_id"] == pending_card["decision_id"]


def test_plain_approve_grants_no_autonomy(client: TestClient, pending_card: dict) -> None:
    """The difference between `approve` and `approve_always` is the entire
    product thesis. `approve` must teach the agent nothing."""
    before = len(client.get("/api/policies").json()["items"])
    client.post(
        f"/api/decisions/{pending_card['decision_id']}/respond",
        json=_answer(pending_card, "approve"),
    )
    assert len(client.get("/api/policies").json()["items"]) == before


def test_answering_writes_a_non_autonomous_activity_row(
    client: TestClient, pending_card: dict
) -> None:
    client.post(
        f"/api/decisions/{pending_card['decision_id']}/respond",
        json=_answer(pending_card, "deny"),
    )
    decided = client.get("/api/activity?autonomous=false").json()["items"]
    row = next(e for e in decided if e["decision_id"] == pending_card["decision_id"])
    assert row["was_autonomous"] is False
    assert row["rationale"]


def test_answering_twice_is_rejected(client: TestClient, pending_card: dict) -> None:
    body = _answer(pending_card, "approve")
    client.post(f"/api/decisions/{pending_card['decision_id']}/respond", json=body)
    second = client.post(f"/api/decisions/{pending_card['decision_id']}/respond", json=body)
    assert second.status_code == 409
    assert second.json()["error"] == "decision_not_pending"


def test_a_choice_the_card_never_offered_is_rejected(
    client: TestClient, pending_card: dict
) -> None:
    """A choice with no branch on the other side of the interrupt would strand
    the run, so it never reaches the agent."""
    offered = {o["choice"] for o in pending_card["options"]}
    absent = next(c for c in ("snooze", "edit", "deny_always") if c not in offered)
    result = client.post(
        f"/api/decisions/{pending_card['decision_id']}/respond",
        json=_answer(pending_card, absent),
    )
    assert result.status_code == 400
    assert result.json()["error"] == "invalid_choice"


def test_snooze_keeps_the_card_pending(client: TestClient, pending_card: dict) -> None:
    offered = {o["choice"] for o in pending_card["options"]}
    if "snooze" not in offered:
        # The fixture card does not offer it; the backend behaviour is still worth
        # pinning, so drive it through the backend directly.
        from quiet_hours_contracts import DecisionResponse

        from app.backends import get_backend

        backend = get_backend()
        card = backend.get_decision(pending_card["decision_id"])
        later = datetime.now(UTC) + timedelta(days=1)
        backend.respond(
            card,
            DecisionResponse(
                decision_id=card.decision_id,
                choice="snooze",
                snooze_until=later,
                responded_at=datetime.now(UTC),
            ),
        )
        assert card.status.value == "pending"
        assert card.resolved_at is None
        return

    client.post(
        f"/api/decisions/{pending_card['decision_id']}/respond",
        json=_answer(pending_card, "snooze"),
    )
    card = client.get(f"/api/decisions/{pending_card['decision_id']}").json()
    assert card["status"] == "pending"


def test_unknown_decision_is_a_stable_error_code(client: TestClient) -> None:
    result = client.get("/api/decisions/dec_nope")
    assert result.status_code == 404
    body = result.json()
    assert body["error"] == "decision_not_found"
    assert body["contract_version"]


def test_body_id_must_match_the_url(client: TestClient, pending_card: dict) -> None:
    body = _answer(pending_card, "approve")
    body["decision_id"] = "dec_somethingelse"
    result = client.post(f"/api/decisions/{pending_card['decision_id']}/respond", json=body)
    assert result.status_code == 400


def test_malformed_body_is_a_contract_error_not_a_500(
    client: TestClient, pending_card: dict
) -> None:
    result = client.post(
        f"/api/decisions/{pending_card['decision_id']}/respond",
        json={"choice": "approve"},
    )
    assert result.status_code == 422
    assert result.json()["error"] == "invalid_request"


def test_unknown_status_filter_is_rejected(client: TestClient) -> None:
    result = client.get("/api/decisions?status=banana")
    assert result.status_code == 400
    assert result.json()["error"] == "invalid_choice"


def test_opaque_strands_ids_are_echoed_untouched(client: TestClient, pending_card: dict) -> None:
    """`session_id`, `interrupt_id` and `interrupt_name` belong to Strands. The
    API may carry them; it may not tidy them up."""
    card = client.get(f"/api/decisions/{pending_card['decision_id']}").json()
    for field in ("session_id", "interrupt_id", "interrupt_name"):
        assert card[field] == pending_card[field]
