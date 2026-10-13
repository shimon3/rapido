"""S2 staged endpoint: reject unauthenticated requests before mutating downloads."""
import os
import tempfile
from unittest.mock import patch

os.environ.setdefault("RAPIDO_DATA", tempfile.mkdtemp(prefix="rapido-s2-test-"))

from fastapi.testclient import TestClient
import app


def test_native_capture_rejects_requests_without_process_token():
    with TestClient(app.app) as client:
        for authorization in (None, "Bearer invalid", "Basic invalid", "Bearer "):
            headers = {"host": "127.0.0.1:9614"}
            if authorization:
                headers["authorization"] = authorization
            response = client.post("/api/native/capture",
                json={"url": "https://example.org/file.zip"}, headers=headers)
            assert response.status_code == 403


def test_native_capture_token_is_not_exposed_in_settings():
    with TestClient(app.app) as client:
        response = client.get("/api/settings", headers={"host": "127.0.0.1:9614"})
        assert response.status_code == 200
        data = response.json()
        token = app._LOCAL_AUTH.token_for_trusted_transport()
        assert token not in response.text
        assert "auth_token" not in data


def test_authenticated_native_capture_uses_existing_capture_flow():
    with patch.object(app, "capture", return_value={"id":"test","dialog": True}) as capture:
        with TestClient(app.app) as client:
            response = client.post("/api/native/capture",
                json={"url": "https://example.org/file.zip"},
                headers={"host": "127.0.0.1:9614",
                         "authorization": "Bearer " + app._LOCAL_AUTH.token_for_trusted_transport()})
            assert response.status_code == 200
            assert response.json()["id"] == "test"
            assert capture.called
