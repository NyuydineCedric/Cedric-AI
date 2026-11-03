from tests.conftest import auth_headers


def test_create_and_list_memory(client, student_token):
    r = client.post(
        "/api/memory",
        headers=auth_headers(student_token),
        json={"category": "goal", "content": "Pass finals"},
    )
    assert r.status_code == 201

    r = client.get("/api/memory", headers=auth_headers(student_token))
    assert len(r.json()) == 1
    assert r.json()[0]["content"] == "Pass finals"


def test_invalid_category_rejected(client, student_token):
    r = client.post(
        "/api/memory",
        headers=auth_headers(student_token),
        json={"category": "nonsense", "content": "x"},
    )
    assert r.status_code == 422


def test_filter_by_category(client, student_token):
    headers = auth_headers(student_token)
    client.post("/api/memory", headers=headers, json={"category": "goal", "content": "goal 1"})
    client.post("/api/memory", headers=headers, json={"category": "deadline", "content": "deadline 1"})

    r = client.get("/api/memory?category=goal", headers=headers)
    assert len(r.json()) == 1
    assert r.json()[0]["category"] == "goal"


def test_memory_is_permission_isolated(client, student_token, other_token):
    r = client.post(
        "/api/memory",
        headers=auth_headers(student_token),
        json={"category": "goal", "content": "secret goal"},
    )
    memory_id = r.json()["id"]

    r = client.get("/api/memory", headers=auth_headers(other_token))
    assert r.json() == []

    r = client.delete(f"/api/memory/{memory_id}", headers=auth_headers(other_token))
    assert r.status_code == 404

    r = client.delete(f"/api/memory/{memory_id}", headers=auth_headers(student_token))
    assert r.status_code == 204
