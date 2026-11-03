from tests.conftest import auth_headers, make_text_file


def test_upload_and_list(client, student_token):
    r = client.post(
        "/api/documents/upload", headers=auth_headers(student_token), files=make_text_file("notes.txt")
    )
    assert r.status_code == 201
    body = r.json()
    assert body["filename"] == "notes.txt"
    assert body["processing_status"] == "completed"
    # No GEMINI_API_KEY in the test environment - embeddings should
    # degrade gracefully rather than fail the upload.
    assert body["embedding_status"] in ("unavailable", "completed", "failed")

    r = client.get("/api/documents", headers=auth_headers(student_token))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_unsupported_extension_rejected(client, student_token):
    files = {"file": ("virus.exe", b"data", "application/octet-stream")}
    r = client.post("/api/documents/upload", headers=auth_headers(student_token), files=files)
    assert r.status_code == 400


def test_empty_file_rejected(client, student_token):
    files = {"file": ("empty.txt", b"", "text/plain")}
    r = client.post("/api/documents/upload", headers=auth_headers(student_token), files=files)
    assert r.status_code == 400


def test_upload_requires_auth(client):
    r = client.post("/api/documents/upload", files=make_text_file("notes.txt"))
    assert r.status_code in (401, 403)


def test_chunks_are_created_from_text(client, student_token):
    r = client.post(
        "/api/documents/upload", headers=auth_headers(student_token), files=make_text_file("notes.txt")
    )
    doc_id = r.json()["id"]

    r = client.get(f"/api/documents/{doc_id}/chunks", headers=auth_headers(student_token))
    assert r.status_code == 200
    chunks = r.json()
    assert len(chunks) >= 1
    assert "PID" in chunks[0]["content"]


def test_documents_are_permission_isolated(client, student_token, other_token):
    r = client.post(
        "/api/documents/upload",
        headers=auth_headers(student_token),
        files=make_text_file("secret.txt", b"very private notes"),
    )
    doc_id = r.json()["id"]

    # Another user's list never includes it.
    r = client.get("/api/documents", headers=auth_headers(other_token))
    assert r.json() == []

    # Another user can't download it.
    r = client.get(f"/api/documents/{doc_id}/download", headers=auth_headers(other_token))
    assert r.status_code == 404

    # Another user can't see its chunks.
    r = client.get(f"/api/documents/{doc_id}/chunks", headers=auth_headers(other_token))
    assert r.status_code == 404

    # Another user can't delete it.
    r = client.delete(f"/api/documents/{doc_id}", headers=auth_headers(other_token))
    assert r.status_code == 404

    # The owner can do all of the above.
    r = client.get(f"/api/documents/{doc_id}/download", headers=auth_headers(student_token))
    assert r.status_code == 200
    r = client.delete(f"/api/documents/{doc_id}", headers=auth_headers(student_token))
    assert r.status_code == 204


def test_deleted_document_is_gone(client, student_token):
    r = client.post(
        "/api/documents/upload", headers=auth_headers(student_token), files=make_text_file("notes.txt")
    )
    doc_id = r.json()["id"]

    client.delete(f"/api/documents/{doc_id}", headers=auth_headers(student_token))

    r = client.get(f"/api/documents/{doc_id}/download", headers=auth_headers(student_token))
    assert r.status_code == 404

    r = client.get("/api/documents", headers=auth_headers(student_token))
    assert r.json() == []
