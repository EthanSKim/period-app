"""
Integration tests for the Web Push Subscription Management API.

Endpoints under test:
  GET  /push/vapid-public-key
  POST /push/subscribe
  DELETE /push/subscribe
  GET  /push/subscriptions
"""

from unittest.mock import MagicMock, patch

from app.core.config import settings

# ── Helpers ───────────────────────────────────────────────────────────────────


def get_auth_headers(
    client,
    email: str = "push_user@example.com",
    password: str = "password123",
) -> dict:
    """Register a user and return Bearer auth headers."""
    client.post("/auth/register", json={"email": email, "password": password})
    resp = client.post("/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_subscription_payload(
    endpoint: str = "https://fcm.googleapis.com/fcm/send/test-endpoint",
    p256dh: str = "BCtest_p256dh_key_base64_encoded_value==",
    auth: str = "test_auth_key==",
) -> dict:
    return {
        "endpoint": endpoint,
        "keys": {"p256dh": p256dh, "auth": auth},
    }


# ── VAPID public key ──────────────────────────────────────────────────────────


def test_get_vapid_public_key_no_auth_required(client) -> None:
    """VAPID public key endpoint should be publicly accessible."""
    response = client.get("/push/vapid-public-key")
    assert response.status_code == 200
    data = response.json()
    assert "public_key" in data
    assert data["public_key"] == settings.VAPID_PUBLIC_KEY
    assert len(data["public_key"]) > 10  # sanity: non-empty key


def test_get_vapid_public_key_returns_string(client) -> None:
    response = client.get("/push/vapid-public-key")
    assert response.status_code == 200
    assert isinstance(response.json()["public_key"], str)


# ── Authentication guards ─────────────────────────────────────────────────────


def test_subscribe_unauthenticated_returns_401(client) -> None:
    response = client.post("/push/subscribe", json=make_subscription_payload())
    assert response.status_code == 401


def test_unsubscribe_unauthenticated_returns_401(client) -> None:
    response = client.request(
        "DELETE",
        "/push/subscribe",
        json={"endpoint": "https://example.com/push/abc"},
    )
    assert response.status_code == 401


def test_list_subscriptions_unauthenticated_returns_401(client) -> None:
    response = client.get("/push/subscriptions")
    assert response.status_code == 401


# ── POST /push/subscribe ──────────────────────────────────────────────────────


def test_subscribe_creates_new_subscription(client) -> None:
    headers = get_auth_headers(client)
    payload = make_subscription_payload()

    response = client.post("/push/subscribe", json=payload, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert data["endpoint"] == payload["endpoint"]
    assert data["p256dh_key"] == payload["keys"]["p256dh"]
    assert data["auth_key"] == payload["keys"]["auth"]
    assert "id" in data
    assert "user_id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_subscribe_returns_201_status_code(client) -> None:
    headers = get_auth_headers(client, email="status_check@example.com")
    response = client.post(
        "/push/subscribe", json=make_subscription_payload(), headers=headers
    )
    assert response.status_code == 201


def test_subscribe_upsert_updates_keys_not_duplicate(client) -> None:
    """
    A second POST for the same endpoint must update the keys
    rather than creating a duplicate row.
    """
    headers = get_auth_headers(client, email="upsert@example.com")
    endpoint = "https://fcm.googleapis.com/fcm/send/upsert-test"

    # First subscription
    first_payload = make_subscription_payload(
        endpoint=endpoint, p256dh="original_p256dh==", auth="original_auth=="
    )
    r1 = client.post("/push/subscribe", json=first_payload, headers=headers)
    assert r1.status_code == 201
    sub_id = r1.json()["id"]

    # Second POST — same endpoint, new keys
    updated_payload = make_subscription_payload(
        endpoint=endpoint, p256dh="updated_p256dh==", auth="updated_auth=="
    )
    r2 = client.post("/push/subscribe", json=updated_payload, headers=headers)
    assert r2.status_code == 201

    data2 = r2.json()
    # Must be the SAME record (same id)
    assert data2["id"] == sub_id
    # Keys must be updated
    assert data2["p256dh_key"] == "updated_p256dh=="
    assert data2["auth_key"] == "updated_auth=="

    # Verify via list that still only one subscription
    subs = client.get("/push/subscriptions", headers=headers).json()
    assert len(subs) == 1


def test_subscribe_multiple_endpoints_same_user(client) -> None:
    """A user can have multiple active subscriptions (different endpoints)."""
    headers = get_auth_headers(client, email="multi_sub@example.com")

    endpoints = [
        "https://fcm.googleapis.com/sub/alpha",
        "https://fcm.googleapis.com/sub/beta",
        "https://fcm.googleapis.com/sub/gamma",
    ]
    for ep in endpoints:
        r = client.post(
            "/push/subscribe",
            json=make_subscription_payload(endpoint=ep),
            headers=headers,
        )
        assert r.status_code == 201

    subs = client.get("/push/subscriptions", headers=headers).json()
    assert len(subs) == 3
    returned_endpoints = {s["endpoint"] for s in subs}
    assert returned_endpoints == set(endpoints)


def test_subscriptions_are_scoped_to_user(client) -> None:
    """User A's subscriptions must not appear in User B's list."""
    headers_a = get_auth_headers(client, email="user_a_push@example.com")
    headers_b = get_auth_headers(client, email="user_b_push@example.com")

    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint="https://example.com/push/userA"),
        headers=headers_a,
    )

    subs_b = client.get("/push/subscriptions", headers=headers_b).json()
    assert subs_b == []


# ── DELETE /push/subscribe ────────────────────────────────────────────────────


def test_delete_removes_subscription(client) -> None:
    headers = get_auth_headers(client, email="delete_sub@example.com")
    endpoint = "https://fcm.googleapis.com/fcm/send/delete-me"

    # Create
    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint=endpoint),
        headers=headers,
    )

    # Delete
    response = client.request(
        "DELETE",
        "/push/subscribe",
        json={"endpoint": endpoint},
        headers=headers,
    )
    assert response.status_code == 204

    # Confirm gone
    subs = client.get("/push/subscriptions", headers=headers).json()
    assert all(s["endpoint"] != endpoint for s in subs)


def test_delete_returns_204_no_content(client) -> None:
    headers = get_auth_headers(client, email="delete_204@example.com")
    endpoint = "https://example.com/push/204"

    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint=endpoint),
        headers=headers,
    )
    response = client.request(
        "DELETE",
        "/push/subscribe",
        json={"endpoint": endpoint},
        headers=headers,
    )
    assert response.status_code == 204
    assert response.content == b""  # No Content


def test_delete_nonexistent_subscription_returns_404(client) -> None:
    headers = get_auth_headers(client, email="delete_404@example.com")
    response = client.request(
        "DELETE",
        "/push/subscribe",
        json={"endpoint": "https://example.com/push/does-not-exist"},
        headers=headers,
    )
    assert response.status_code == 404


def test_delete_only_removes_own_subscription(client) -> None:
    """User B cannot delete User A's subscription."""
    headers_a = get_auth_headers(client, email="owner_push@example.com")
    headers_b = get_auth_headers(client, email="thief_push@example.com")
    endpoint = "https://example.com/push/userA-only"

    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint=endpoint),
        headers=headers_a,
    )

    # User B tries to delete User A's subscription — should 404 (not found for B)
    response = client.request(
        "DELETE",
        "/push/subscribe",
        json={"endpoint": endpoint},
        headers=headers_b,
    )
    assert response.status_code == 404

    # User A's subscription is still there
    subs_a = client.get("/push/subscriptions", headers=headers_a).json()
    assert any(s["endpoint"] == endpoint for s in subs_a)


# ── GET /push/subscriptions ───────────────────────────────────────────────────


def test_list_subscriptions_empty_for_new_user(client) -> None:
    headers = get_auth_headers(client, email="empty_subs@example.com")
    response = client.get("/push/subscriptions", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_list_subscriptions_returns_all_for_user(client) -> None:
    headers = get_auth_headers(client, email="list_all@example.com")

    for i in range(3):
        client.post(
            "/push/subscribe",
            json=make_subscription_payload(
                endpoint=f"https://example.com/push/{i}",
                p256dh=f"key_{i}==",
                auth=f"auth_{i}==",
            ),
            headers=headers,
        )

    response = client.get("/push/subscriptions", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    for item in data:
        assert "id" in item
        assert "endpoint" in item
        assert "p256dh_key" in item
        assert "auth_key" in item
        assert "created_at" in item
        assert "updated_at" in item


# ── POST /push/send-test ──────────────────────────────────────────────────────


def test_send_test_fails_no_subscriptions(client) -> None:
    headers = get_auth_headers(client, email="no_subs_test@example.com")
    response = client.post("/push/send-test", headers=headers)
    assert response.status_code == 400
    assert "No active push subscriptions" in response.json()["detail"]


@patch("app.services.push_service.webpush")
def test_send_test_success_with_subscriptions(mock_webpush, client) -> None:
    headers = get_auth_headers(client, email="has_subs_test@example.com")

    # Create subscription
    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint="https://example.com/push/test"),
        headers=headers,
    )

    response = client.post(
        "/push/send-test",
        json={"title": "Hello", "body": "World"},
        headers=headers,
    )
    assert response.status_code == 200
    assert "Dispatched test notifications to 1/1" in response.json()["message"]
    assert mock_webpush.called


# ── run_daily_notifications_job ───────────────────────────────────────────────


@patch("app.services.scheduler.SessionLocal")
@patch("app.services.push_service.webpush")
def test_scheduler_job_scenarios(
    mock_webpush, mock_session_local, client, session
) -> None:
    mock_session_local.return_value = session
    from datetime import date, timedelta

    from app.models import NotificationLog
    from app.services.scheduler import run_daily_notifications_job

    today = date.today()

    # User 1: 1 cycle, prediction starting in 1 day, active subscription
    # (Should notify)
    headers_1 = get_auth_headers(client, email="user1@example.com")
    client.post(
        "/cycles",
        json={"start_date": (today - timedelta(days=27)).isoformat()},
        headers=headers_1,
    )
    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint="https://example.com/push/user1"),
        headers=headers_1,
    )

    # User 2: 1 cycle, prediction starting in 3 days, active subscription
    # (Should notify)
    headers_2 = get_auth_headers(client, email="user2@example.com")
    client.post(
        "/cycles",
        json={"start_date": (today - timedelta(days=25)).isoformat()},
        headers=headers_2,
    )
    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint="https://example.com/push/user2"),
        headers=headers_2,
    )

    # User 3: 1 cycle, fertile window starting in 1 day -> Should notify
    # For 1 cycle (population average 28 days), predicted next start is start_date + 28.
    # Ovulation is start_date + 28 - 14 = start_date + 14.
    # Fertile starts at ovulation - 5 = start_date + 9.
    # We want fertile_start (start_date + 9) to be today + 1 (tomorrow).
    # So start_date + 9 = today + 1 => start_date = today - 8.
    headers_3 = get_auth_headers(client, email="user3@example.com")
    client.post(
        "/cycles",
        json={"start_date": (today - timedelta(days=8)).isoformat()},
        headers=headers_3,
    )
    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint="https://example.com/push/user3"),
        headers=headers_3,
    )

    # User 4: prediction starting in 1 day, active subscription,
    # but 0 cycles -> Should NOT notify
    headers_4 = get_auth_headers(client, email="user4@example.com")
    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint="https://example.com/push/user4"),
        headers=headers_4,
    )

    # Run the job
    mock_webpush.reset_mock()
    run_daily_notifications_job()

    # Verify notifications sent to user 1, 2, 3
    # User 1: period_1_day. User 2: period_3_days. User 3: fertile_1_day.
    assert mock_webpush.call_count == 3

    # Check notification logs were created
    logs = session.query(NotificationLog).all()
    assert len(logs) == 3
    log_types = {log_entry.notification_type for log_entry in logs}
    assert log_types == {"period_1_day", "period_3_days", "fertile_1_day"}


@patch("app.services.scheduler.SessionLocal")
@patch("app.services.push_service.webpush")
def test_scheduler_job_prevents_duplicate_sends(
    mock_webpush, mock_session_local, client, session
) -> None:
    mock_session_local.return_value = session
    from datetime import date, timedelta

    from app.services.scheduler import run_daily_notifications_job

    today = date.today()
    headers = get_auth_headers(client, email="duplicate_test@example.com")

    # Log 1 cycle (prediction starting in 1 day)
    client.post(
        "/cycles",
        json={"start_date": (today - timedelta(days=27)).isoformat()},
        headers=headers,
    )
    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint="https://example.com/push/dup"),
        headers=headers,
    )

    # First run -> Should notify
    run_daily_notifications_job()
    assert mock_webpush.call_count == 1

    # Second run -> Should NOT notify (duplicate check)
    mock_webpush.reset_mock()
    run_daily_notifications_job()
    assert mock_webpush.call_count == 0


@patch("app.services.scheduler.SessionLocal")
@patch("app.services.push_service.webpush")
def test_scheduler_job_cleanup_on_410_gone(
    mock_webpush, mock_session_local, client, session
) -> None:
    mock_session_local.return_value = session
    from datetime import date, timedelta

    from pywebpush import WebPushException

    from app.models import PushSubscription
    from app.services.scheduler import run_daily_notifications_job

    today = date.today()
    headers = get_auth_headers(client, email="cleanup_test@example.com")

    # Log 1 cycle
    client.post(
        "/cycles",
        json={"start_date": (today - timedelta(days=27)).isoformat()},
        headers=headers,
    )
    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint="https://example.com/push/gone"),
        headers=headers,
    )

    # Mock webpush to throw 410 Gone Exception
    # Create mock response object
    mock_response = MagicMock()
    mock_response.status_code = 410
    mock_webpush.side_effect = WebPushException("Gone", response=mock_response)

    # Run the job
    run_daily_notifications_job()

    # The subscription should have been cleaned up/deleted
    subs = session.query(PushSubscription).all()
    # Find if subscription with endpoint "gone" still exists
    gone_sub = [s for s in subs if "gone" in s.endpoint]
    assert len(gone_sub) == 0


@patch("app.services.scheduler.SessionLocal")
@patch("app.services.push_service.webpush")
def test_scheduler_job_cleanup_on_404_not_found(
    mock_webpush, mock_session_local, client, session
) -> None:
    mock_session_local.return_value = session
    from datetime import date, timedelta

    from pywebpush import WebPushException

    from app.models import PushSubscription
    from app.services.scheduler import run_daily_notifications_job

    today = date.today()
    headers = get_auth_headers(client, email="cleanup_404@example.com")

    # Log 1 cycle
    client.post(
        "/cycles",
        json={"start_date": (today - timedelta(days=27)).isoformat()},
        headers=headers,
    )
    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint="https://example.com/push/notfound"),
        headers=headers,
    )

    # Mock webpush to throw 404 Not Found Exception
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_webpush.side_effect = WebPushException("Not Found", response=mock_response)

    # Run the job
    run_daily_notifications_job()

    # The subscription should have been cleaned up/deleted
    subs = session.query(PushSubscription).all()
    notfound_sub = [s for s in subs if "notfound" in s.endpoint]
    assert len(notfound_sub) == 0


@patch("app.services.scheduler.SessionLocal")
@patch("app.services.push_service.webpush")
def test_scheduler_job_no_cleanup_on_5xx_error(
    mock_webpush, mock_session_local, client, session
) -> None:
    mock_session_local.return_value = session
    from datetime import date, timedelta

    from pywebpush import WebPushException

    from app.models import PushSubscription
    from app.services.scheduler import run_daily_notifications_job

    today = date.today()
    headers = get_auth_headers(client, email="cleanup_500@example.com")

    # Log 1 cycle
    client.post(
        "/cycles",
        json={"start_date": (today - timedelta(days=27)).isoformat()},
        headers=headers,
    )
    client.post(
        "/push/subscribe",
        json=make_subscription_payload(endpoint="https://example.com/push/servererror"),
        headers=headers,
    )

    # Mock webpush to throw 500 Internal Server Error
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_webpush.side_effect = WebPushException("Internal Server Error", response=mock_response)

    # Run the job
    run_daily_notifications_job()

    # The subscription should NOT have been cleaned up/deleted
    subs = session.query(PushSubscription).all()
    servererror_sub = [s for s in subs if "servererror" in s.endpoint]
    assert len(servererror_sub) == 1
