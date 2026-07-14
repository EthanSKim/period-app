"""
Integration tests for the Web Push Subscription Management API.

Endpoints under test:
  GET  /push/vapid-public-key
  POST /push/subscribe
  DELETE /push/subscribe
  GET  /push/subscriptions
"""

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
