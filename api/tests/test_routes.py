"""Runs, activity, policies, the brief, paging and the digest template."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from quiet_hours_contracts import DailyBrief, Household

from app.digest import format_money, render_html, render_text, subject_for


def test_activity_filter_splits_the_one_trail(client: TestClient) -> None:
    everything = client.get("/api/activity").json()["items"]
    silent = client.get("/api/activity?autonomous=true").json()["items"]
    decided = client.get("/api/activity?autonomous=false").json()["items"]
    assert len(silent) + len(decided) == len(everything)
    assert all(e["was_autonomous"] for e in silent)
    assert not any(e["was_autonomous"] for e in decided)


def test_activity_is_newest_first(client: TestClient) -> None:
    stamps = [e["occurred_at"] for e in client.get("/api/activity").json()["items"]]
    assert stamps == sorted(stamps, reverse=True)


def test_every_activity_row_explains_itself(client: TestClient) -> None:
    """No silent unexplained behaviour - root AGENTS.md, product rule 4."""
    for entry in client.get("/api/activity").json()["items"]:
        assert entry["rationale"].strip()
        assert entry["summary"].strip()


def test_revoking_a_policy_removes_it_from_the_active_list(client: TestClient) -> None:
    policy = client.get("/api/policies").json()["items"][0]
    result = client.delete(f"/api/policies/{policy['policy_id']}")
    assert result.status_code == 200
    assert result.json()["revoked_at"] is not None

    active = {p["policy_id"] for p in client.get("/api/policies").json()["items"]}
    assert policy["policy_id"] not in active

    everything = {
        p["policy_id"] for p in client.get("/api/policies?include_revoked=true").json()["items"]
    }
    assert policy["policy_id"] in everything, "a revoked rule stays in the trail"


def test_revoking_twice_is_idempotent(client: TestClient) -> None:
    policy_id = client.get("/api/policies").json()["items"][0]["policy_id"]
    first = client.delete(f"/api/policies/{policy_id}").json()
    second = client.delete(f"/api/policies/{policy_id}").json()
    assert first["revoked_at"] == second["revoked_at"]


def test_revoking_an_unknown_policy_is_a_stable_error(client: TestClient) -> None:
    result = client.delete("/api/policies/pol_nope")
    assert result.status_code == 404
    assert result.json()["error"] == "policy_not_found"


def test_trigger_run_returns_a_run(client: TestClient) -> None:
    result = client.post("/api/runs")
    assert result.status_code == 200
    run = result.json()
    assert run["trigger"] == "manual"
    assert client.get(f"/api/runs/{run['run_id']}").status_code == 200


def test_unknown_run_is_a_stable_error(client: TestClient) -> None:
    result = client.get("/api/runs/run_nope")
    assert result.status_code == 404
    assert result.json()["error"] == "run_not_found"


def test_run_stream_narrates_then_completes(client: TestClient) -> None:
    run_id = client.get("/api/runs").json()["items"][0]["run_id"]
    with client.stream("GET", f"/api/runs/{run_id}/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert body.count("event: run.progress") >= 3
    assert "event: run.completed" in body or "event: run.waiting" in body
    payloads = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert all(p["run_id"] == run_id for p in payloads)


def test_run_stream_reports_a_missing_run_on_an_open_stream(client: TestClient) -> None:
    """`EventSource` cannot read the body of a failed handshake, so a missing run
    arrives as an error frame rather than a 404."""
    with client.stream("GET", "/api/runs/run_nope/stream") as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "event: error" in body
    assert "run_not_found" in body


def test_paging_walks_the_whole_activity_trail(client: TestClient) -> None:
    seen: list[str] = []
    cursor = None
    for _ in range(20):
        url = f"/api/activity?limit=3{f'&cursor={cursor}' if cursor else ''}"
        page = client.get(url).json()
        assert len(page["items"]) <= 3
        seen += [e["entry_id"] for e in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert cursor is None, "paging never terminated"
    assert len(seen) == len(set(seen))
    assert len(seen) == len(client.get("/api/activity").json()["items"])


def test_malformed_cursor_is_a_contract_error(client: TestClient) -> None:
    result = client.get("/api/activity?cursor=notanumber")
    assert result.status_code == 400
    assert result.json()["error"] == "invalid_request"


def test_brief_reflects_the_pending_inbox(client: TestClient) -> None:
    brief = DailyBrief.model_validate(client.get("/api/brief/latest").json())
    pending = client.get("/api/decisions?status=pending").json()["items"]
    assert set(brief.pending_decision_ids) == {c["decision_id"] for c in pending}


def test_brief_headline_goes_quiet_once_the_inbox_is_empty(client: TestClient) -> None:
    for card in client.get("/api/decisions?status=pending").json()["items"]:
        client.post(
            f"/api/decisions/{card['decision_id']}/respond",
            json={
                "decision_id": card["decision_id"],
                "choice": "approve",
                "responded_at": "2026-09-04T09:00:00Z",
            },
        )
    brief = client.get("/api/brief/latest").json()
    assert brief["headline"] == "Nothing needs you today"
    assert brief["pending_decision_ids"] == []


# -- the digest email -------------------------------------------------------


def _brief_and_household(client: TestClient) -> tuple[DailyBrief, Household]:
    return (
        DailyBrief.model_validate(client.get("/api/brief/latest").json()),
        Household.model_validate(client.get("/api/household").json()),
    )


def test_format_money_matches_the_typescript_helper() -> None:
    from quiet_hours_contracts import Money

    assert format_money(Money(amount_minor=1799, currency="GBP")) == "£17.99"
    assert format_money(Money(amount_minor=16420, currency="GBP")) == "£164.20"
    assert format_money(Money(amount_minor=15000, currency="GBP")) == "£150"
    assert format_money(None) == ""


def test_digest_subject_says_what_happened(client: TestClient) -> None:
    brief, _ = _brief_and_household(client)
    subject = subject_for(brief)
    assert subject.startswith("Quiet Hours:")
    assert "report" not in subject.lower()


def test_digest_renders_html_and_text(client: TestClient) -> None:
    brief, household = _brief_and_household(client)
    html = render_html(brief, household, app_url="http://localhost:3000")
    text = render_text(brief, household, app_url="http://localhost:3000")
    assert brief.headline in html
    assert brief.headline in text
    # Email HTML: tables and inline styles only.
    assert "display:flex" not in html
    assert "<link" not in html


def test_digest_preview_route_renders(client: TestClient) -> None:
    result = client.get("/api/brief/latest/preview")
    assert result.status_code == 200
    assert result.headers["content-type"].startswith("text/html")
    assert "Quiet Hours" in result.text
    assert client.get("/api/brief/latest/preview.txt").status_code == 200


def test_digest_never_sends_without_explicit_configuration(monkeypatch) -> None:
    """There is no route that sends mail, and `send_digest` refuses rather than
    silently doing nothing when it is not configured."""
    import pytest

    from app.digest import send_digest

    monkeypatch.delenv("QH_DIGEST_TO", raising=False)
    monkeypatch.delenv("QH_SES_SENDER", raising=False)
    with pytest.raises(RuntimeError):
        send_digest(
            DailyBrief(
                brief_id="brf_x",
                household_id="hh_demo",
                run_id="run_x",
                generated_at="2026-09-04T08:00:00Z",
                headline="Nothing needs you today",
            ),
            Household(
                household_id="hh_demo",
                display_name="Test",
                created_at="2026-09-04T08:00:00Z",
            ),
        )
