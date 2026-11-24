"""鉴权：注册唯一性、密码校验、JWT 登录。"""


def test_register_success(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "alice"
    assert "password_hash" not in body


def test_register_duplicate_username_conflict(client):
    payload = {"username": "bob", "email": "bob@example.com", "password": "password123"}
    client.post("/api/auth/register", json=payload)
    resp = client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "other@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_login_wrong_password_rejected(client):
    client.post(
        "/api/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "carol", "password": "wrong-pass"}
    )
    assert resp.status_code == 401


def test_login_success_returns_token(client):
    client.post(
        "/api/auth/register",
        json={"username": "dave", "email": "dave@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "dave", "password": "password123"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
