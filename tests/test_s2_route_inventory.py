"""S2 migration inventory: explicitly track every mutating HTTP endpoint.

This test does NOT establish that these endpoints are authenticated.
It prevents silently adding new unauthenticated mutation routes during migration.
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
AUTHENTICATED_MUTATIONS = {("POST", "/api/native/capture")}


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


def test_only_native_capture_is_marked_authenticated():
    assert AUTHENTICATED_MUTATIONS == {("POST", "/api/native/capture")}
