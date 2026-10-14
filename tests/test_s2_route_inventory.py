"""S2 migration inventory: explicitly track every mutating HTTP endpoint.

This inventory also probes every mutation without credentials and requires 403.
It prevents silently adding an unprotected mutation route.
"""
import os
import tempfile
os.environ.setdefault("RAPIDO_DATA", tempfile.mkdtemp(prefix="rapido-s2-inventory-"))

from app import app

LEGACY_MUTATIONS = {
    ("POST", "/api/downloads"),
    ("POST", "/api/capture"),
    ("POST", "/api/capture-video"),
    ("POST", "/api/downloads/{dl_id}/confirm"),
    ("POST", "/api/downloads/{dl_id}/cancel-capture"),
    ("POST", "/api/downloads/{dl_id}/pause"),
    ("POST", "/api/downloads/{dl_id}/resume"),
    ("POST", "/api/downloads/{dl_id}/redownload"),
    ("POST", "/api/downloads/{dl_id}/refresh"),
    ("POST", "/api/downloads/{dl_id}/move-to-queue"),
    ("POST", "/api/downloads/{dl_id}/open-window"),
    ("POST", "/api/downloads/{dl_id}/description"),
    ("POST", "/api/bulk/{action}"),
    ("DELETE", "/api/downloads/{dl_id}"),
    ("POST", "/api/downloads/{dl_id}/open"),
    ("POST", "/api/open-folder"),
    ("POST", "/api/queue/start"),
    ("POST", "/api/queue/stop"),
    ("POST", "/api/power/cancel"),
    ("PUT", "/api/settings"),
    ("POST", "/api/window"),
    ("POST", "/api/window-action"),
    ("POST", "/api/show"),
    ("POST", "/api/tools/ffmpeg"),
    ("POST", "/api/tools/deno"),
    ("POST", "/api/tools/extension"),
}
AUTHENTICATED_MUTATIONS = {("POST", "/api/native/capture"),
    ("POST", "/api/downloads/{dl_id}/recover-handoff")}


def test_explicit_mutation_inventory_prevents_unreviewed_routes():
    routes = {
        (method, route.path)
        for route in app.routes
        for method in (route.methods or ())
        if method in {"POST", "PUT", "PATCH", "DELETE"} and route.path.startswith("/api/")
    }
    assert routes == LEGACY_MUTATIONS | AUTHENTICATED_MUTATIONS, (
        "Mutation routes changed: review S2 authorization before changing this inventory"
    )


def test_all_inventory_routes_are_protected_without_token():
    from fastapi.testclient import TestClient
    with TestClient(app, base_url="http://127.0.0.1:9614") as client:
        for method, path in LEGACY_MUTATIONS | AUTHENTICATED_MUTATIONS:
            path = path.replace("{dl_id}", "abcdef").replace("{action}", "delete")
            assert client.request(method, path, json={}).status_code == 403


def test_all_private_read_routes_reject_anonymous_access():
    """Every new API GET route must remain covered by the central auth guard."""
    from fastapi.testclient import TestClient
    paths = {
        route.path
        for route in app.routes
        if "GET" in (route.methods or ())
        and route.path.startswith("/api/")
        and route.path != "/api/ping"
    }
    assert paths, "Expected private API read routes"
    with TestClient(app, base_url="http://127.0.0.1:9614") as client:
        for path in sorted(paths):
            # Check auth first, even on non-existent resource IDs.
            candidate = (path.replace("{dl_id}", "abcdef")
                             .replace("{action}", "delete")
                             .replace("{id}", "abcdef"))
            response = client.get(candidate)
            assert response.status_code == 403, (candidate, response.status_code)
