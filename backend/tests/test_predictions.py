"""
Integration tests for GET /predictions endpoint.
Uses the TestClient + in-memory SQLite database from conftest.py.

Covers both v1 (basic predictions) and v2 (predicted_range, high confidence)
scenarios.
"""

from datetime import date, timedelta


def get_auth_headers(
    client,
    email: str = "pred@example.com",
    password: str = "password123",
) -> dict:
    """Register a user and return Bearer auth headers."""
    client.post("/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_cycle(
    client, headers: dict, start_date: str, end_date: str | None = None
) -> dict:
    payload: dict = {"start_date": start_date}
    if end_date is not None:
        payload["end_date"] = end_date
    resp = client.post("/cycles", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Authentication guard
# ---------------------------------------------------------------------------


def test_unauthenticated_request_returns_401(client) -> None:
    response = client.get("/predictions")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 0 cycles → defaults
# ---------------------------------------------------------------------------


def test_zero_cycles_returns_default_prediction(client) -> None:
    headers = get_auth_headers(client)
    response = client.get("/predictions", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["average_cycle_length"] == 28.0
    assert data["confidence"] == "low"
    assert data["basis"] == "default"
    assert data["current_cycle_day"] is None
    assert data["predicted_next_period_start"] is None
    assert data["predicted_range"] is None


# ---------------------------------------------------------------------------
# 1 cycle → limited_data
# ---------------------------------------------------------------------------


def test_one_cycle_returns_limited_data_prediction(client) -> None:
    headers = get_auth_headers(client)
    start = "2026-05-23"
    create_cycle(client, headers, start_date=start, end_date="2026-05-28")

    response = client.get("/predictions", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["average_cycle_length"] == 28.0
    assert data["confidence"] == "low"
    assert data["basis"] == "limited_data"

    # current_cycle_day and predicted_next_period_start must be present
    assert data["current_cycle_day"] is not None
    assert data["predicted_next_period_start"] is not None

    # predicted should be start_date + 28 days
    start_date_obj = date(2026, 5, 23)
    expected_next = (start_date_obj + timedelta(days=28)).isoformat()
    assert data["predicted_next_period_start"] == expected_next

    # 1 cycle → no range
    assert data["predicted_range"] is None


# ---------------------------------------------------------------------------
# 3+ cycles → personal_average + predicted_range present
# ---------------------------------------------------------------------------


def test_three_cycles_returns_personal_average_prediction(client) -> None:
    headers = get_auth_headers(client)

    # gaps: Jan 1 → Jan 31 = 30 days, Jan 31 → Feb 28 = 28 days → mean = 29.0
    create_cycle(client, headers, start_date="2026-01-01", end_date="2026-01-05")
    create_cycle(client, headers, start_date="2026-01-31", end_date="2026-02-04")
    create_cycle(client, headers, start_date="2026-02-28", end_date="2026-03-04")

    response = client.get("/predictions", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["average_cycle_length"] == 29.0
    assert data["confidence"] == "medium"
    assert data["basis"] == "personal_average"

    # predicted_next_period_start = 2026-02-28 + 29 days = 2026-03-29
    assert data["predicted_next_period_start"] == "2026-03-29"
    assert data["current_cycle_day"] is not None

    # 3 cycles → 2 gaps → predicted_range must be present
    assert data["predicted_range"] is not None
    pr = data["predicted_range"]
    assert pr["earliest"] is not None
    assert pr["latest"] is not None
    # Earliest must be ≤ predicted, latest must be ≥ predicted
    assert pr["earliest"] <= data["predicted_next_period_start"]
    assert pr["latest"] >= data["predicted_next_period_start"]


# ---------------------------------------------------------------------------
# 2 cycles → limited_data with blended average
# ---------------------------------------------------------------------------


def test_two_cycles_blends_with_population_default(client) -> None:
    headers = get_auth_headers(client, email="two_cycles@example.com")

    # gap = 30 days → blended = (30 + 28) / 2 = 29.0
    create_cycle(client, headers, start_date="2026-01-01", end_date="2026-01-05")
    create_cycle(client, headers, start_date="2026-01-31", end_date="2026-02-04")

    response = client.get("/predictions", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["average_cycle_length"] == 29.0
    assert data["confidence"] == "low"
    assert data["basis"] == "limited_data"
    # 2 cycles → 1 gap → no range
    assert data["predicted_range"] is None


# ---------------------------------------------------------------------------
# 6+ cycles → weighted average + high confidence
# ---------------------------------------------------------------------------


def test_six_uniform_cycles_returns_high_confidence(client) -> None:
    headers = get_auth_headers(client, email="six_cycles@example.com")

    # 6 cycles with uniform 28-day gaps → std_dev = 0 → 'high'
    d0 = date(2026, 1, 1)
    for i in range(6):
        start = (d0 + timedelta(days=28 * i)).isoformat()
        end = (d0 + timedelta(days=28 * i + 4)).isoformat()
        create_cycle(client, headers, start_date=start, end_date=end)

    response = client.get("/predictions", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["confidence"] == "high"
    assert data["basis"] == "personal_average"
    assert data["average_cycle_length"] == 28.0

    # Range must be present with offset = 2 (std_dev = 0)
    assert data["predicted_range"] is not None
    pr = data["predicted_range"]
    assert pr["earliest"] is not None
    assert pr["latest"] is not None

    predicted = date.fromisoformat(data["predicted_next_period_start"])
    assert date.fromisoformat(pr["earliest"]) == predicted - timedelta(days=2)
    assert date.fromisoformat(pr["latest"]) == predicted + timedelta(days=2)


def test_six_variable_cycles_confidence_medium_not_high(client) -> None:
    headers = get_auth_headers(client, email="six_var@example.com")

    # 6 cycles with highly variable gaps (alternating 20 and 36)
    # → std_dev >> 2 → confidence stays 'medium'
    d0 = date(2026, 1, 1)
    gaps = [0, 20, 56, 76, 112, 132]
    for _i, offset in enumerate(gaps):
        start = (d0 + timedelta(days=offset)).isoformat()
        end = (d0 + timedelta(days=offset + 4)).isoformat()
        create_cycle(client, headers, start_date=start, end_date=end)

    response = client.get("/predictions", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["confidence"] == "medium"
    assert data["predicted_range"] is not None


def test_predicted_range_format_in_response(client) -> None:
    """Verify predicted_range serialises to {earliest, latest} date strings."""
    headers = get_auth_headers(client, email="range_format@example.com")

    # 3 uniform cycles → range present
    d0 = date(2026, 1, 1)
    for i in range(3):
        start = (d0 + timedelta(days=28 * i)).isoformat()
        end = (d0 + timedelta(days=28 * i + 4)).isoformat()
        create_cycle(client, headers, start_date=start, end_date=end)

    response = client.get("/predictions", headers=headers)
    assert response.status_code == 200

    data = response.json()
    pr = data["predicted_range"]
    assert isinstance(pr, dict)
    assert "earliest" in pr
    assert "latest" in pr
    # Should be ISO date strings (YYYY-MM-DD)
    for field in ("earliest", "latest"):
        val = pr[field]
        assert val is not None
        assert len(val) == 10
        date.fromisoformat(val)  # raises if not a valid date string


# ---------------------------------------------------------------------------
# Timezone insensitivity (today query param)
# ---------------------------------------------------------------------------


def test_timezone_insensitivity(client) -> None:
    import os
    import time

    headers = get_auth_headers(client, email="tz_test@example.com")

    # Log 3 cycles to establish a personal average
    # gaps: Jan 1 -> Jan 31 = 30 days, Jan 31 -> Feb 28 = 28 days -> mean = 29.0
    create_cycle(client, headers, start_date="2026-01-01", end_date="2026-01-05")
    create_cycle(client, headers, start_date="2026-01-31", end_date="2026-02-04")
    create_cycle(client, headers, start_date="2026-02-28", end_date="2026-03-04")

    # Mocks different system timezones (e.g. UTC, UTC+9, UTC-8)
    timezones = ["UTC", "Asia/Tokyo", "America/New_York", "GMT-8", "GMT+9"]
    original_tz = os.environ.get("TZ")

    results = []
    try:
        for tz in timezones:
            os.environ["TZ"] = tz
            time.tzset()

            # Using a fixed reference today date as a query parameter
            response = client.get("/predictions?today=2026-03-15", headers=headers)
            assert response.status_code == 200
            results.append(response.json())

        # Assert predictions remain completely identical and timezone-insensitive
        first_result = results[0]
        for res in results[1:]:
            assert res == first_result
    finally:
        if original_tz is not None:
            os.environ["TZ"] = original_tz
        else:
            os.environ.pop("TZ", None)
        time.tzset()


# ---------------------------------------------------------------------------
# v3: Ovulation & fertile window — response structure
# ---------------------------------------------------------------------------


def test_zero_cycles_ovulation_fields_are_none(client) -> None:
    headers = get_auth_headers(client, email="ov_zero@example.com")
    response = client.get("/predictions", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["predicted_ovulation_date"] is None
    assert data["fertile_window_start"] is None
    assert data["fertile_window_end"] is None


def test_one_cycle_ovulation_fields_present(client) -> None:
    headers = get_auth_headers(client, email="ov_one@example.com")
    create_cycle(client, headers, start_date="2026-01-01", end_date="2026-01-05")

    response = client.get("/predictions?today=2026-01-15", headers=headers)
    assert response.status_code == 200

    data = response.json()
    # predicted_next_period_start = 2026-01-01 + 28 = 2026-01-29
    assert data["predicted_next_period_start"] == "2026-01-29"
    # ovulation = 2026-01-29 - 14 = 2026-01-15
    assert data["predicted_ovulation_date"] == "2026-01-15"
    # fertile_window_start = 2026-01-15 - 5 = 2026-01-10
    assert data["fertile_window_start"] == "2026-01-10"
    # fertile_window_end = 2026-01-15 + 1 = 2026-01-16
    assert data["fertile_window_end"] == "2026-01-16"


def test_three_cycles_ovulation_fields_match_prediction(client) -> None:
    headers = get_auth_headers(client, email="ov_three@example.com")

    # gaps: 30, 28 -> avg = 29.0
    # predicted next = 2026-02-28 + 29 = 2026-03-29
    create_cycle(client, headers, start_date="2026-01-01", end_date="2026-01-05")
    create_cycle(client, headers, start_date="2026-01-31", end_date="2026-02-04")
    create_cycle(client, headers, start_date="2026-02-28", end_date="2026-03-04")

    response = client.get("/predictions?today=2026-03-01", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["predicted_next_period_start"] == "2026-03-29"
    # ovulation = 2026-03-29 - 14 = 2026-03-15
    assert data["predicted_ovulation_date"] == "2026-03-15"
    # fertile_window_start = 2026-03-15 - 5 = 2026-03-10
    assert data["fertile_window_start"] == "2026-03-10"
    # fertile_window_end = 2026-03-15 + 1 = 2026-03-16
    assert data["fertile_window_end"] == "2026-03-16"


def test_past_ovulation_date_returned_not_suppressed(client) -> None:
    """A past ovulation date must appear in the response, not be filtered to None."""
    headers = get_auth_headers(client, email="ov_past@example.com")
    # Cycle started 2026-01-01 -> predicted next = 2026-01-29
    # ovulation = 2026-01-15 (in the past relative to today=2026-02-10)
    create_cycle(client, headers, start_date="2026-01-01", end_date="2026-01-05")

    response = client.get("/predictions?today=2026-02-10", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["predicted_next_period_start"] == "2026-01-29"
    assert data["predicted_ovulation_date"] == "2026-01-15"
    assert data["predicted_ovulation_date"] is not None
    assert data["fertile_window_start"] is not None
    assert data["fertile_window_end"] is not None


def test_ovulation_fields_are_iso_date_strings(client) -> None:
    """Verify all three ovulation/fertile fields serialise as YYYY-MM-DD strings."""
    headers = get_auth_headers(client, email="ov_fmt@example.com")
    create_cycle(client, headers, start_date="2026-03-01", end_date="2026-03-05")

    response = client.get("/predictions?today=2026-03-10", headers=headers)
    assert response.status_code == 200

    data = response.json()
    from datetime import date

    fields = ("predicted_ovulation_date", "fertile_window_start", "fertile_window_end")
    for field in fields:
        val = data[field]
        assert val is not None, f"{field} should not be None"
        assert len(val) == 10, f"{field} should be YYYY-MM-DD format"
        date.fromisoformat(val)  # raises ValueError if invalid
