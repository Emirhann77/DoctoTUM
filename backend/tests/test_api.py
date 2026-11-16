"""Route behaviour on the in-memory store. test_live.py repeats the core of this
against a real Supabase project."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.store import base, memory
from backend.tests.conftest import ALICE, BOB


def future(days: int = 3, hour: int = 9) -> str:
    d = (datetime.now(tz=timezone.utc) + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return d.isoformat()


def book(client, headers, **over):
    body = {"specialist_id": "1", "start_time": future(), "reason": "Check-up", **over}
    return client.post("/api/appointments", json=body, headers=headers)


# --- appointments -----------------------------------------------------------


def test_book_then_list_then_cancel(client, alice):
    r = book(client, alice)
    assert r.status_code == 201
    appt = r.json()
    assert appt["specialist_name"] == "Dr. Ayşe Yılmaz"
    assert appt["reason"] == "Check-up"

    assert [a["id"] for a in client.get("/api/appointments", headers=alice).json()] == [appt["id"]]
    assert client.delete(f"/api/appointments/{appt['id']}", headers=alice).status_code == 200
    assert client.get("/api/appointments", headers=alice).json() == []


def test_client_supplied_user_id_is_ignored(client, alice, bob):
    assert book(client, alice, user_id=BOB).status_code == 201
    assert client.get("/api/appointments", headers=bob).json() == []
    assert len(client.get("/api/appointments", headers=alice).json()) == 1


def test_cannot_see_or_cancel_someone_elses_appointment(client, alice, bob):
    appt = book(client, alice).json()
    assert client.get("/api/appointments", headers=bob).json() == []
    assert client.delete(f"/api/appointments/{appt['id']}", headers=bob).status_code == 404
    assert len(client.get("/api/appointments", headers=alice).json()) == 1


@pytest.mark.parametrize(
    "over,status",
    [
        ({"start_time": "2020-01-01T09:00:00Z"}, 422),
        ({"start_time": future(days=800)}, 422),
        ({"start_time": "2030-01-01T09:00:00"}, 422),  # no timezone
        ({"start_time": "tomorrow"}, 422),
        ({"specialist_id": "999"}, 404),
        ({"specialist_id": ""}, 422),
        ({"reason": "x" * 501}, 422),
    ],
    ids=["past", "too-far", "naive", "not-a-date", "unknown-doctor", "empty-doctor", "long-reason"],
)
def test_booking_validation(client, alice, over, status):
    assert book(client, alice, **over).status_code == status
    assert client.get("/api/appointments", headers=alice).json() == []


def test_same_time_twice_is_a_conflict_until_cancelled(client, alice):
    first = book(client, alice).json()
    assert book(client, alice, specialist_id="3").status_code == 409
    client.delete(f"/api/appointments/{first['id']}", headers=alice)
    assert book(client, alice, specialist_id="3").status_code == 201


def test_cancelling_twice_or_unknown_is_404(client, alice):
    appt = book(client, alice).json()
    assert client.delete(f"/api/appointments/{appt['id']}", headers=alice).status_code == 200
    assert client.delete(f"/api/appointments/{appt['id']}", headers=alice).status_code == 404
    assert client.delete("/api/appointments/nope", headers=alice).status_code == 404


# --- prescriptions and pharmacy ---------------------------------------------


def test_new_account_has_no_prescriptions_or_orders(client, alice):
    assert client.get("/api/prescriptions", headers=alice).json() == []
    assert client.get("/api/pharmacy/orders", headers=alice).json() == []
    assert client.get("/api/appointments", headers=alice).json() == []


def test_patients_cannot_create_prescriptions(client, alice):
    r = client.post("/api/prescriptions", json={"medication": "Oxycodone", "dosage": "x"}, headers=alice)
    assert r.status_code == 405


def test_refill_order_flow(client, alice, bob):
    rx = memory.issue_prescription(ALICE, "Lisinopril 10mg", "1 daily", "Morning", "Dr. Ayşe Yılmaz")
    listed = client.get("/api/prescriptions", headers=alice).json()
    assert [p["medication"] for p in listed] == ["Lisinopril 10mg"]
    assert client.get("/api/prescriptions", headers=bob).json() == []

    r = client.post(
        "/api/pharmacy/orders",
        json={"items": [{"medication_name": "Lisinopril 10mg", "prescription_id": rx.id, "quantity": 2}]},
        headers=alice,
    )
    assert r.status_code == 201
    order = r.json()[0]
    assert (order["status"], order["quantity"]) == ("requested", 2)
    assert client.get("/api/pharmacy/orders", headers=bob).json() == []

    assert client.post(f"/api/pharmacy/orders/{order['id']}/cancel", headers=bob).status_code == 404
    assert client.post(f"/api/pharmacy/orders/{order['id']}/cancel", headers=alice).json()["status"] == "cancelled"
    assert client.post(f"/api/pharmacy/orders/{order['id']}/cancel", headers=alice).status_code == 409


def test_cannot_order_against_someone_elses_prescription(client, alice, bob):
    rx = memory.issue_prescription(ALICE, "Lisinopril 10mg", "1 daily", "Morning", "Dr. A")
    r = client.post(
        "/api/pharmacy/orders",
        json={"items": [{"medication_name": "Lisinopril 10mg", "prescription_id": rx.id}]},
        headers=bob,
    )
    assert r.status_code == 404
    assert client.get("/api/pharmacy/orders", headers=bob).json() == []


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{"medication_name": ""}],
        [{"medication_name": "Ibuprofen", "quantity": 0}],
        [{"medication_name": "Ibuprofen", "quantity": 11}],
        [{"medication_name": "Ibuprofen"}] * 11,
    ],
    ids=["empty", "blank-name", "zero", "too-many-units", "too-many-items"],
)
def test_order_validation(client, alice, items):
    assert client.post("/api/pharmacy/orders", json={"items": items}, headers=alice).status_code == 422


# --- emergency --------------------------------------------------------------


def test_sos_is_logged_and_never_claims_dispatch(client, alice, bob):
    r = client.post("/api/emergency/start", json={"symptoms": "SOS", "location": {"city": "Munich"}}, headers=alice)
    assert r.status_code == 201
    alert = r.json()
    assert alert["status"] == "active"
    assert alert["dispatched"] is False
    assert alert["emergency_number"] == "112"

    assert client.post("/api/emergency/end", json={"alert_id": alert["alert_id"]}, headers=bob).status_code == 404
    ended = client.post("/api/emergency/end", json={"alert_id": alert["alert_id"]}, headers=alice)
    assert ended.json()["status"] == "cancelled"


def test_sos_works_with_an_empty_body(client, alice):
    assert client.post("/api/emergency/start", json={}, headers=alice).status_code == 201


# --- failures ---------------------------------------------------------------


def test_store_outage_is_a_503_with_a_plain_message(client, alice, monkeypatch):
    def down(self):
        raise base.Unavailable()

    monkeypatch.setattr(memory.MemoryStore, "list_appointments", down)
    r = client.get("/api/appointments", headers=alice)
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"].lower()


# --- AI ---------------------------------------------------------------------


def test_chat_runs_in_mock_mode_and_screens_emergencies_first(client, alice):
    r = client.post("/api/ai_assistant/chat", json={"user_message": "nefes alamıyorum", "language": "tr"}, headers=alice)
    assert r.status_code == 200
    assert r.json()["recommendation"] == "emergency"


def test_chat_is_rate_limited_per_user(client, alice, bob):
    for _ in range(30):
        assert client.post("/api/ai_assistant/chat", json={"user_message": "headache"}, headers=alice).status_code == 200
    assert client.post("/api/ai_assistant/chat", json={"user_message": "headache"}, headers=alice).status_code == 429
    assert client.post("/api/ai_assistant/chat", json={"user_message": "headache"}, headers=bob).status_code == 200


def test_chat_rejects_oversized_messages(client, alice):
    r = client.post("/api/ai_assistant/chat", json={"user_message": "x" * 2001}, headers=alice)
    assert r.status_code == 422
