def get_auth_headers(client, email="test@example.com", password="password123"):
    # Register a test user
    client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    # Login and get access token
    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_cycle_success(client):
    headers = get_auth_headers(client)

    # 1. With end_date
    response = client.post(
        "/cycles",
        json={"start_date": "2026-06-01", "end_date": "2026-06-05"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["start_date"] == "2026-06-01"
    assert data["end_date"] == "2026-06-05"
    assert "id" in data
    assert "user_id" in data
    assert data["cycle_length"] is None

    # 2. Without end_date
    response = client.post(
        "/cycles",
        json={"start_date": "2026-06-15"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["start_date"] == "2026-06-15"
    assert data["end_date"] is None
    assert data["cycle_length"] is None


def test_get_cycles_sorted(client):
    headers = get_auth_headers(client)

    # Create cycles out of chronological order
    client.post(
        "/cycles",
        json={"start_date": "2026-05-01", "end_date": "2026-05-05"},
        headers=headers,
    )
    client.post(
        "/cycles",
        json={"start_date": "2026-06-01", "end_date": "2026-06-05"},
        headers=headers,
    )
    client.post(
        "/cycles",
        json={"start_date": "2026-04-01", "end_date": "2026-04-05"},
        headers=headers,
    )

    response = client.get("/cycles", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    # Check that they are ordered by start_date descending
    assert data[0]["start_date"] == "2026-06-01"
    assert data[1]["start_date"] == "2026-05-01"
    assert data[2]["start_date"] == "2026-04-01"


def test_patch_cycle_success(client):
    headers = get_auth_headers(client)

    # Create cycle
    create_resp = client.post(
        "/cycles",
        json={"start_date": "2026-06-01", "end_date": "2026-06-05"},
        headers=headers,
    )
    cycle_id = create_resp.json()["id"]

    # Patch only end_date
    patch_resp = client.patch(
        f"/cycles/{cycle_id}",
        json={"end_date": "2026-06-07"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["start_date"] == "2026-06-01"
    assert patch_resp.json()["end_date"] == "2026-06-07"

    # Patch only start_date
    patch_resp = client.patch(
        f"/cycles/{cycle_id}",
        json={"start_date": "2026-05-28"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["start_date"] == "2026-05-28"
    assert patch_resp.json()["end_date"] == "2026-06-07"

    # Patch both
    patch_resp = client.patch(
        f"/cycles/{cycle_id}",
        json={"start_date": "2026-06-02", "end_date": "2026-06-08"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["start_date"] == "2026-06-02"
    assert patch_resp.json()["end_date"] == "2026-06-08"


def test_unauthenticated_requests(client):
    # 1. POST
    response = client.post("/cycles", json={"start_date": "2026-06-01"})
    assert response.status_code == 401

    # 2. GET
    response = client.get("/cycles")
    assert response.status_code == 401

    # 3. PATCH
    response = client.patch("/cycles/1", json={"start_date": "2026-06-02"})
    assert response.status_code == 401


def test_access_control(client):
    # Create user A and user B
    headers_a = get_auth_headers(client, email="user_a@example.com")
    headers_b = get_auth_headers(client, email="user_b@example.com")

    # User A creates a cycle
    create_resp = client.post(
        "/cycles",
        json={"start_date": "2026-06-01", "end_date": "2026-06-05"},
        headers=headers_a,
    )
    cycle_id = create_resp.json()["id"]

    # User B tries to patch User A's cycle
    patch_resp = client.patch(
        f"/cycles/{cycle_id}",
        json={"end_date": "2026-06-08"},
        headers=headers_b,
    )
    assert patch_resp.status_code == 403
    assert patch_resp.json()["detail"] == "Not authorized to access this cycle"

    # Non-existent cycle
    patch_resp = client.patch(
        "/cycles/99999",
        json={"end_date": "2026-06-08"},
        headers=headers_b,
    )
    assert patch_resp.status_code == 404
    assert patch_resp.json()["detail"] == "Cycle not found"


def test_date_constraints_and_validation(client):
    headers = get_auth_headers(client)

    # 1. Invalid date format format (not YYYY-MM-DD)
    response = client.post(
        "/cycles",
        json={"start_date": "invalid-date"},
        headers=headers,
    )
    assert response.status_code == 400

    # 2. Create end_date before start_date
    response = client.post(
        "/cycles",
        json={"start_date": "2026-06-10", "end_date": "2026-06-09"},
        headers=headers,
    )
    assert response.status_code == 400

    # 3. Create end_date equal to start_date
    response = client.post(
        "/cycles",
        json={"start_date": "2026-06-10", "end_date": "2026-06-10"},
        headers=headers,
    )
    assert response.status_code == 400

    # 4. Patch end_date before start_date (using PATCH model validator validation)
    create_resp = client.post(
        "/cycles",
        json={"start_date": "2026-06-10", "end_date": "2026-06-15"},
        headers=headers,
    )
    cycle_id = create_resp.json()["id"]

    # Patch end_date <= start_date (specifically passing both)
    response = client.patch(
        f"/cycles/{cycle_id}",
        json={"start_date": "2026-06-10", "end_date": "2026-06-09"},
        headers=headers,
    )
    assert response.status_code == 400

    # Patch end_date <= start_date
    # (by updating only end_date to be before the DB's start_date)
    response = client.patch(
        f"/cycles/{cycle_id}",
        json={"end_date": "2026-06-09"},
        headers=headers,
    )
    assert response.status_code == 400

    # Patch start_date >= end_date
    # (by updating only start_date to be after the DB's end_date)
    response = client.patch(
        f"/cycles/{cycle_id}",
        json={"start_date": "2026-06-16"},
        headers=headers,
    )
    assert response.status_code == 400


def test_cycle_length_computation(client):
    headers = get_auth_headers(client)

    # Scenario A:
    # Create Cycle 1: start_date="2026-05-01", end_date="2026-05-05".
    # (Initially cycle_length is None because it's the only/last cycle)
    c1_resp = client.post(
        "/cycles",
        json={"start_date": "2026-05-01", "end_date": "2026-05-05"},
        headers=headers,
    )
    assert c1_resp.status_code == 201
    c1_id = c1_resp.json()["id"]
    assert c1_resp.json()["cycle_length"] is None

    # Create Cycle 2: start_date="2026-05-29", end_date="2026-06-02".
    c2_resp = client.post(
        "/cycles",
        json={"start_date": "2026-05-29", "end_date": "2026-06-02"},
        headers=headers,
    )
    assert c2_resp.status_code == 201
    c2_id = c2_resp.json()["id"]

    # Verify Cycle 1 length is recalculated to 28 days (2026-05-29 - 2026-05-01 = 28)
    # and Cycle 2 length is None
    cycles_resp = client.get("/cycles", headers=headers)
    cycles_data = {c["id"]: c for c in cycles_resp.json()}
    assert cycles_data[c1_id]["cycle_length"] == 28
    assert cycles_data[c2_id]["cycle_length"] is None

    # Scenario B:
    # Create a third Cycle 3: start_date="2026-06-26", end_date=None (ongoing).
    c3_resp = client.post(
        "/cycles",
        json={"start_date": "2026-06-26"},
        headers=headers,
    )
    assert c3_resp.status_code == 201
    c3_id = c3_resp.json()["id"]

    # Verify Cycle 1 length is still 28, Cycle 2 length is None
    # (Cycle 3 has no end_date), Cycle 3 is None
    cycles_resp = client.get("/cycles", headers=headers)
    cycles_data = {c["id"]: c for c in cycles_resp.json()}
    assert cycles_data[c1_id]["cycle_length"] == 28
    assert cycles_data[c2_id]["cycle_length"] is None
    assert cycles_data[c3_id]["cycle_length"] is None

    # Scenario C:
    # Patch Cycle 3's end_date to "2026-06-30".
    patch_resp = client.patch(
        f"/cycles/{c3_id}",
        json={"end_date": "2026-06-30"},
        headers=headers,
    )
    assert patch_resp.status_code == 200

    # Verify Cycle 2 length is now recalculated to 28 days
    # (2026-06-26 - 2026-05-29 = 28)
    cycles_resp = client.get("/cycles", headers=headers)
    cycles_data = {c["id"]: c for c in cycles_resp.json()}
    assert cycles_data[c1_id]["cycle_length"] == 28
    assert cycles_data[c2_id]["cycle_length"] == 28
    assert cycles_data[c3_id]["cycle_length"] is None

    # Scenario D:
    # Patch Cycle 2's start_date to "2026-05-27".
    patch_resp2 = client.patch(
        f"/cycles/{c2_id}",
        json={"start_date": "2026-05-27"},
        headers=headers,
    )
    assert patch_resp2.status_code == 200

    # Verify:
    # Cycle 1 length = 2026-05-27 - 2026-05-01 = 26 days
    # Cycle 2 length = 2026-06-26 - 2026-05-27 = 30 days
    # Cycle 3 length = None
    cycles_resp = client.get("/cycles", headers=headers)
    cycles_data = {c["id"]: c for c in cycles_resp.json()}
    assert cycles_data[c1_id]["cycle_length"] == 26
    assert cycles_data[c2_id]["cycle_length"] == 30
    assert cycles_data[c3_id]["cycle_length"] is None
