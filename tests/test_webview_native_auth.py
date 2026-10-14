"""Native header policy: only an owned local page can authorize local API."""
import unittest
from types import SimpleNamespace
from local_auth import LocalAuth
from webview_auth import authorize_request, trusted_page, BASE


class WebViewAuthTests(unittest.TestCase):
    def setUp(self):
        self.auth = LocalAuth()

    def request(self, url):
        return SimpleNamespace(url=url, headers={})

    def test_local_api_get_and_write_are_authorized_without_html_secret(self):
        for route in ("/api/state", "/api/capture", "/api/settings"):
            request = self.request(BASE+route)
            self.assertTrue(authorize_request(request, current_page=BASE+"/",
                initial_page=BASE+"/", auth=self.auth))
            self.assertTrue(self.auth.header_is_authorized(request.headers["Authorization"]))

    def test_other_hosts_schemes_ports_and_paths_never_get_credentials(self):
        token = "Bearer " + self.auth.token_for_trusted_transport()
        for url in ("https://evil.example/api/state", "http://127.0.0.1:9615/api/state",
                    "http://localhost:9614/api/state", "http://evil.example:9614/api/state",
                    BASE+"/favicon.ico", "http://user@127.0.0.1:9614/api/state",
                    BASE+"/api%2fstate", "https://127.0.0.1:9614/api/state"):
            request = self.request(url)
            request.headers["authorization"] = token
            self.assertFalse(authorize_request(request, current_page=BASE+"/",
                initial_page=BASE+"/", auth=self.auth))
            self.assertFalse(any(k.lower()=="authorization" for k in request.headers))

    def test_external_or_unknown_window_cannot_authorize_local_requests(self):
        for source in (None, "https://evil.example/", BASE+"/w", BASE+"/?other=1"):
            request = self.request(BASE+"/api/state")
            self.assertFalse(authorize_request(request, current_page=source,
                initial_page=BASE+"/", auth=self.auth))
            self.assertEqual(request.headers, {})

    def test_popup_is_bound_to_its_id_and_window_token(self):
        initial = BASE+"/w?view=capture&id=abcdef&w=1234567890abcdef"
        self.assertTrue(trusted_page(initial, initial))
        self.assertTrue(trusted_page(initial.replace("view=capture","view=progress"), initial))
        for changed in (initial.replace("id=abcdef","id=badbad"),
                        initial.replace("w=1234567890abcdef","w=badbad"),
                        initial+"&id=abcdef", initial+"&extra=1",
                        initial.replace("view=capture","view=other")):
            self.assertFalse(trusted_page(changed, initial))

    def test_non_ascii_and_oversized_auth_tokens_fail_closed(self):
        for candidate in ("é", "令牌", "a"*100000, None, ""):
            self.assertFalse(self.auth.verify(candidate))
            if isinstance(candidate, str):
                self.assertFalse(self.auth.header_is_authorized("Bearer "+candidate))


if __name__ == "__main__":
    unittest.main()
