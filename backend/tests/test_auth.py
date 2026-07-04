def test_register_success(client):
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "securepassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_empty_fields(client):
    # Empty email
    response = client.post(
        "/auth/register",
        json={"email": "", "password": "securepassword123"},
    )
    assert response.status_code == 400

    # Empty password
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": ""},
    )
    assert response.status_code == 400

    # Missing fields
    response = client.post(
        "/auth/register",
        json={},
    )
    assert response.status_code == 400


def test_register_malformed_email(client):
    response = client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "securepassword123"},
    )
    assert response.status_code == 400


def test_register_duplicate_email(client):
    # Register once
    response1 = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "securepassword123"},
    )
    assert response1.status_code == 200

    # Register again with same email
    response2 = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "differentpassword"},
    )
    assert response2.status_code == 409
    assert response2.json()["detail"] == "Email already registered"


def test_login_success(client):
    # First, register
    client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "securepassword123"},
    )

    # Login
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "securepassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    # First, register
    client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "securepassword123"},
    )

    # Invalid password
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

    # Non-existent email
    response = client.post(
        "/auth/login",
        json={"email": "nonexistent@example.com", "password": "securepassword123"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_get_me_success(client):
    # Register and login to get token
    client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "securepassword123"},
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "securepassword123"},
    )
    token = login_response.json()["access_token"]

    # Call /auth/me
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


def test_get_me_unauthorized(client):
    # No token
    response = client.get("/auth/me")
    assert response.status_code == 401

    # Invalid token
    headers = {"Authorization": "Bearer invalidtoken123"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 401
