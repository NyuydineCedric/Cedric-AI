from tests.conftest import auth_headers, register_and_login


def test_register_returns_profile_without_password(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "a@test.com", "full_name": "A Student", "password": "password123"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "a@test.com"
    assert "password" not in body
    assert "hashed_password" not in body


def test_duplicate_email_rejected(client):
    payload = {"email": "dup@test.com", "full_name": "Dup", "password": "password123"}
    client.post("/api/auth/register", json=payload)
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 409


def test_login_wrong_password_rejected(client):
    client.post(
        "/api/auth/register",
        json={"email": "b@test.com", "full_name": "B", "password": "password123"},
    )
    r = client.post("/api/auth/login", json={"email": "b@test.com", "password": "wrongpass"})
    assert r.status_code == 401


def test_login_unknown_email_rejected(client):
    r = client.post("/api/auth/login", json={"email": "nobody@test.com", "password": "x"})
    assert r.status_code == 401


def test_me_requires_a_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code in (401, 403)


def test_me_rejects_garbage_token(client):
    r = client.get("/api/auth/me", headers=auth_headers("not-a-real-token"))
    assert r.status_code == 401


def test_me_returns_the_logged_in_user(client):
    token = register_and_login(client, "student@test.com")
    r = client.get("/api/auth/me", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["email"] == "student@test.com"


def test_password_too_short_rejected(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "short@test.com", "full_name": "Short", "password": "abc"},
    )
    assert r.status_code == 422
