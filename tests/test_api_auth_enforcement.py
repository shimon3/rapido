"""S2 API enforcement and narrow native RPC behavior, without network downloads."""
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

os.environ.setdefault("RAPIDO_DATA", tempfile.mkdtemp(prefix="rapido-auth-test-"))
import app

app.manager.settings["monitor_clipboard"] = False


class ApiAuthTests(unittest.TestCase):
    def test_every_api_mutation_is_denied_without_credentials(self):
        routes = [(m, r.path.replace("{dl_id}", "abcdef").replace("{action}", "delete"))
                  for r in app.app.routes for m in (r.methods or ())
                  if m in {"POST","PUT","PATCH","DELETE"} and r.path.startswith("/api/")]
        before = len(app.manager.downloads)
        with TestClient(app.app, base_url="http://127.0.0.1:9614") as client:
            for method, path in routes:
                with self.subTest(method=method, path=path):
                    self.assertEqual(client.request(method,path,json={}).status_code,403)
            for path in ("/api/settings","/api/state","/api/downloads","/api/updates/check",
                         "/api/downloads/abcdef?watch=true"):
                self.assertEqual(client.get(path).status_code,403)
            self.assertEqual(client.get("/api/ping").status_code,200)
        self.assertEqual(len(app.manager.downloads),before)

    def test_forged_browser_headers_do_not_substitute_for_a_token(self):
        with TestClient(app.app, base_url="http://127.0.0.1:9614") as client:
            for origin in (None,"http://127.0.0.1:9614",app.EXTENSION_ORIGIN):
                headers = {"Sec-Fetch-Site":"same-origin"}
                if origin:
                    headers["Origin"] = origin
                self.assertEqual(client.post("/api/capture",json={"url":"https://example.org/a.zip"},
                                             headers=headers).status_code,403)

    def test_token_authorizes_existing_routes_and_never_appears_in_responses(self):
        token = app._LOCAL_AUTH.token_for_trusted_transport()
        with TestClient(app.app, base_url="http://127.0.0.1:9614",
                        headers={"Authorization":"Bearer "+token}) as client:
            for path in ("/api/settings","/api/state","/api/downloads"):
                reply = client.get(path)
                self.assertEqual(reply.status_code,200)
                self.assertNotIn(token,reply.text)
            self.assertEqual(client.post("/api/bulk/resume",json={}).status_code,200)
            self.assertNotIn(token,client.get("/").text)

    def test_malformed_bearer_headers_never_authorize_private_api(self):
        token = app._LOCAL_AUTH.token_for_trusted_transport()
        invalid = (
            "", "Bearer", "Bearer ", "Basic " + token,
            "Bearer " + token + "extra", "Bearer " + token + " ",
            "Bearer  " + token, "Bearer\\t" + token,
            "Bearer " + token[:-1], "Bearer " + token + "\\n",
        )
        with TestClient(app.app, base_url="http://127.0.0.1:9614") as client:
            for value in invalid:
                with self.subTest(value=repr(value)[:25]):
                    response = client.get("/api/settings", headers={"Authorization": value})
                    self.assertEqual(response.status_code, 403)
                    self.assertNotIn(token, response.text)

    def test_valid_token_cannot_override_host_or_origin_policy(self):
        token = app._LOCAL_AUTH.token_for_trusted_transport()
        protected = {"Authorization": "Bearer " + token}
        with TestClient(app.app, base_url="http://127.0.0.1:9614") as client:
            cases = (
                {"Host": "attacker.example:9614"},
                {"Origin": "https://attacker.example"},
                {"Sec-Fetch-Site": "cross-site"},
                {"Origin": "http://127.0.0.1:12345", "Sec-Fetch-Site": "same-site"},
            )
            for headers in cases:
                with self.subTest(headers=headers):
                    response = client.get("/api/settings", headers={**protected, **headers})
                    self.assertEqual(response.status_code, 403)
                    self.assertNotIn(token, response.text)

    def test_native_rpc_has_no_general_route_or_secret_authority(self):
        for role, request in (("native",{"type":"delete","id":"abcdef"}),
                              ("native",{"type":"auth"}),
                              ("native",{"type":"request","path":"/api/settings","method":"PUT"}),
                              ("desktop",{"type":"capture_public"}),
                              ("unknown",{"type":"capabilities"})):
            with self.assertRaises(ValueError):
                app.native_dispatch(role,request)
        config = app.native_dispatch("native",{"type":"settings_public"})
        self.assertEqual(set(config),{"type","capture_exts","min_capture_kb"})
        self.assertNotIn(app._LOCAL_AUTH.token_for_trusted_transport(),str(config))

    def test_public_capture_validates_again_and_strips_private_referrer(self):
        message = {"type":"capture_public","url":"https://example.org/a.zip",
                   "referrer":"https://example.org/page?token=secret#fragment","filename":"a.zip"}
        with TestClient(app.app, base_url="http://127.0.0.1:9614"):
            with patch.object(app,"capture",new=AsyncMock(return_value={"id":"abcdef"})) as capture:
                self.assertEqual(app.native_dispatch("native",message),
                                 {"type":"capture_result","ok":True})
                captured = capture.call_args.args[0]
                self.assertEqual(captured.headers,{"Referer":"https://example.org/page"})
                self.assertTrue(captured.open_window)
            with self.assertRaises(ValueError):
                app.native_dispatch("native",{**message,"cookie":"secret"})


if __name__ == "__main__":
    unittest.main()
