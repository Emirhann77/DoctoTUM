"""SupabaseStore and the directory against a fake PostgREST (no network)."""

from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException

from backend.models.schemas import PharmacyOrderItem
from backend.services import directory
from backend.store import base, supabase
from backend.tests.conftest import ALICE

RX = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


@pytest.fixture
def fake(monkeypatch):
    """Route SupabaseStore's HTTP through a handler the test supplies."""
    monkeypatch.setenv("SUPABASE_URL", "https://mine.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    seen: list[httpx.Request] = []

    def install(handler):
        def record(request):
            seen.append(request)
            return handler(request)

        monkeypatch.setattr(supabase, "_client", httpx.Client(transport=httpx.MockTransport(record)))
        return supabase.SupabaseStore(ALICE, "user-token")

    install.seen = seen
    return install


def reply(status, body=None, **kwargs):
    return lambda request: httpx.Response(status, json=body, **kwargs)


def test_requests_act_as_the_user_not_the_service_role(fake):
    store = fake(reply(200, []))
    store.list_orders()
    request = fake.seen[0]
    assert request.headers["authorization"] == "Bearer user-token"
    assert request.headers["apikey"] == "anon"
    assert f"user_id=eq.{ALICE}" in str(request.url)


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (409, {"code": "23505"}, base.Conflict),
        (409, {"code": "23503"}, base.NotFound),
        (403, {"code": "42501"}, base.NotFound),
        (500, {"message": "boom"}, base.Unavailable),
        (429, {}, base.Unavailable),
        (400, ["not", "a", "dict"], HTTPException),
    ],
    ids=["duplicate", "foreign-key", "rls-denied", "server-error", "throttled", "odd-body"],
)
def test_database_errors_map_to_the_right_failure(fake, status, body, expected):
    store = fake(reply(status, body))
    with pytest.raises(expected):
        store.list_orders()


@pytest.mark.parametrize("status,body,http", [
    (401, {"code": "PGRST301", "message": "JWT expired"}, 401),
    (400, {"code": "23514"}, 422),
    (400, {"code": "22P02"}, 422),
])
def test_expired_token_and_bad_input_keep_their_meaning(fake, status, body, http):
    store = fake(reply(status, body))
    with pytest.raises(HTTPException) as err:
        store.list_orders()
    assert err.value.status_code == http


def test_network_failure_and_garbage_success_are_unavailable(fake):
    def down(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(base.Unavailable):
        fake(down).list_orders()
    with pytest.raises(base.Unavailable):
        fake(lambda r: httpx.Response(200, content=b"<html>")).list_orders()


def test_prescription_ids_are_normalised_before_comparison(fake):
    def handler(request):
        if request.method == "GET":
            assert RX in str(request.url)
            return httpx.Response(200, json=[{"id": RX}])
        sent = __import__("json").loads(request.content)
        assert sent[0]["prescription_id"] == RX
        return httpx.Response(201, json=[{
            "id": "0a0a0a0a-0a0a-4a0a-8a0a-0a0a0a0a0a0a", "medication_name": "Lisinopril", "quantity": 1,
            "status": "requested", "prescription_id": RX, "notes": None, "created_at": "2026-11-18T10:00:00+00:00"}])

    store = fake(handler)
    orders = store.create_orders([PharmacyOrderItem(medication_name="Lisinopril", prescription_id=RX.upper())])
    assert orders[0].prescription_id == RX


@pytest.mark.parametrize("bad", ["nope", "", "1); drop", "eq.1,id.neq.2"])
def test_non_uuid_ids_never_reach_the_database(fake, bad):
    store = fake(reply(200, []))
    for call in (store.cancel_appointment, store.cancel_order, store.end_alert):
        with pytest.raises(base.NotFound):
            call(bad)
    assert fake.seen == []


def test_cancel_order_distinguishes_missing_from_too_late(fake):
    row = {"id": RX, "medication_name": "x", "quantity": 1, "status": "shipped",
           "prescription_id": None, "notes": None, "created_at": "2026-11-18T10:00:00+00:00"}
    with pytest.raises(base.Conflict):
        fake(lambda r: httpx.Response(200, json=[] if r.method == "PATCH" else [row])).cancel_order(RX)
    with pytest.raises(base.NotFound):
        fake(reply(200, [])).cancel_order(RX)


def test_only_bookings_are_listed_and_cancellable(fake):
    store = fake(reply(200, []))
    store.list_appointments()
    assert "status=eq.queued" in str(fake.seen[0].url)
    with pytest.raises(base.NotFound):
        store.cancel_appointment(RX)
    assert "status=eq.queued" in str(fake.seen[1].url)


# --- directory --------------------------------------------------------------


def test_directory_serves_the_last_good_list_during_an_outage(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://mine.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    rows = [{"id": RX, "display_name": "Dr. A", "specialty": "Cardiology", "is_available": True,
             "languages": ["German"], "city": "Munich", "country": "Germany"}]
    state = {"up": True, "calls": 0}

    def get(*args, **kwargs):
        state["calls"] += 1
        if not state["up"]:
            raise httpx.ConnectError("down")
        return httpx.Response(200, json=rows, request=httpx.Request("GET", args[0]))

    monkeypatch.setattr(directory.httpx, "get", get)
    assert [d.name for d in directory.list_specialists()] == ["Dr. A"]
    assert directory.list_specialists() and state["calls"] == 1  # cached

    state["up"] = False
    monkeypatch.setattr(directory, "_TTL_SECONDS", 0)
    assert [d.name for d in directory.list_specialists()] == ["Dr. A"]  # stale beats nothing


def test_directory_without_any_data_reports_unavailable(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://mine.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    with pytest.raises(base.Unavailable):  # service key missing
        directory.list_specialists()
