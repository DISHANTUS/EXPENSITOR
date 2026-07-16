"""User-settings endpoint tests (success + failure)."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

SETTINGS = "/api/v1/users/me/settings"


async def _auth_headers(client: AsyncClient, email: str = "settings@example.com") -> dict[str, str]:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123", "full_name": "S"},
    )
    tokens = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_get_default_settings(client: AsyncClient):
    headers = await _auth_headers(client)
    resp = await client.get(SETTINGS, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_currency"] == "INR"
    assert Decimal(str(body["starting_balance"])) == Decimal("0")
    assert body["monthly_threshold"] is None
    assert body["monthly_income_estimate"] is None
    assert body["preferred_ai_tone"] == "balanced"
    assert body["notification_preferences"]["threshold_alerts"] is True


async def test_update_settings_success(client: AsyncClient):
    headers = await _auth_headers(client)
    payload = {
        "base_currency": "JPY",
        "monthly_threshold": "50000.00",
        "starting_balance": "1000.50",
        "monthly_income_estimate": "80000",
        "preferred_ai_tone": "strict",
        "notification_preferences": {
            "threshold_alerts": False,
            "weekly_summary": True,
            "planned_expense_reminders": False,
            "monthly_report": True,
        },
    }
    resp = await client.patch(SETTINGS, headers=headers, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_currency"] == "JPY"
    assert Decimal(str(body["monthly_threshold"])) == Decimal("50000.00")
    assert Decimal(str(body["starting_balance"])) == Decimal("1000.50")
    assert body["preferred_ai_tone"] == "strict"
    assert body["notification_preferences"]["threshold_alerts"] is False


async def test_update_lowercase_currency_is_normalized(client: AsyncClient):
    headers = await _auth_headers(client)
    resp = await client.patch(SETTINGS, headers=headers, json={"base_currency": "usd"})
    assert resp.status_code == 200
    assert resp.json()["base_currency"] == "USD"


async def test_update_persists(client: AsyncClient):
    headers = await _auth_headers(client)
    await client.patch(SETTINGS, headers=headers, json={"base_currency": "EUR"})
    resp = await client.get(SETTINGS, headers=headers)
    assert resp.json()["base_currency"] == "EUR"


async def test_clear_nullable_field(client: AsyncClient):
    headers = await _auth_headers(client)
    await client.patch(SETTINGS, headers=headers, json={"monthly_threshold": "500"})
    resp = await client.patch(SETTINGS, headers=headers, json={"monthly_threshold": None})
    assert resp.status_code == 200
    assert resp.json()["monthly_threshold"] is None


async def test_update_unsupported_currency(client: AsyncClient):
    headers = await _auth_headers(client)
    resp = await client.patch(SETTINGS, headers=headers, json={"base_currency": "XXX"})
    assert resp.status_code == 422


async def test_update_negative_threshold(client: AsyncClient):
    headers = await _auth_headers(client)
    resp = await client.patch(SETTINGS, headers=headers, json={"monthly_threshold": "-10"})
    assert resp.status_code == 422


async def test_update_invalid_tone(client: AsyncClient):
    headers = await _auth_headers(client)
    resp = await client.patch(SETTINGS, headers=headers, json={"preferred_ai_tone": "aggressive"})
    assert resp.status_code == 422


async def test_update_rejects_unknown_field(client: AsyncClient):
    headers = await _auth_headers(client)
    resp = await client.patch(SETTINGS, headers=headers, json={"unknown_field": 1})
    assert resp.status_code == 422


async def test_settings_requires_auth(client: AsyncClient):
    resp = await client.get(SETTINGS)
    assert resp.status_code == 401


async def test_selected_voice_round_trip_and_clear(client: AsyncClient):
    headers = await _auth_headers(client, email="voice@example.com")
    # Default: no chosen voice.
    body = (await client.get(SETTINGS, headers=headers)).json()
    assert body["selected_voice"] is None and body["voice_locale"] is None

    # Choose a device voice.
    resp = await client.patch(SETTINGS, headers=headers,
                              json={"selected_voice": "en-us-x-sfg#female_1-local", "voice_locale": "en-US"})
    assert resp.status_code == 200
    assert resp.json()["selected_voice"] == "en-us-x-sfg#female_1-local"
    assert resp.json()["voice_locale"] == "en-US"

    # Clearing with an empty string falls back to the system default.
    resp = await client.patch(SETTINGS, headers=headers, json={"selected_voice": "", "voice_locale": None})
    assert resp.json()["selected_voice"] is None


async def test_free_time_preferences_round_trip(client: AsyncClient):
    """Regression guard: NotificationPreferences is a strict (extra=forbid)
    schema, so a new preference key needs an explicit field or every PATCH
    carrying it 422s with "Extra inputs are not permitted" — caught live via
    the mobile Settings screen, not by the original schema addition."""
    headers = await _auth_headers(client, email="freetime@example.com")
    resp = await client.patch(SETTINGS, headers=headers,
                              json={"notification_preferences": {"free_time_weekday": "evening"}})
    assert resp.status_code == 200
    prefs = resp.json()["notification_preferences"]
    assert prefs["free_time_weekday"] == "evening"
    assert prefs["free_time_weekend"] is None
    # Existing bool prefs still default correctly alongside the new fields.
    assert prefs["speak_celebrations"] is True

    resp2 = await client.patch(SETTINGS, headers=headers,
                               json={"notification_preferences": {**prefs, "free_time_weekend": "afternoon"}})
    assert resp2.status_code == 200
    assert resp2.json()["notification_preferences"]["free_time_weekday"] == "evening"
    assert resp2.json()["notification_preferences"]["free_time_weekend"] == "afternoon"
