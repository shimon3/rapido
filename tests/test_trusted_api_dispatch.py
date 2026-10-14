"""Internal ASGI dispatch stays in process; no bearer reaches an HTTP listener."""
import asyncio
import os
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI, Request
from local_auth import LocalAuth
from trusted_api import call


class TrustedDispatchTests(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever,daemon=True)
        self.thread.start()
        auth = LocalAuth()
        api = FastAPI()
        @api.post("/api/example")
        async def example(request: Request):
            if not auth.header_is_authorized(request.headers.get("authorization")):
                return {"ok":False}
            return {"ok":True,"body":await request.json()}
        self.rapido = SimpleNamespace(app=api,_LOCAL_AUTH=auth,manager=SimpleNamespace(loop=self.loop))
    def tearDown(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)
        self.loop.close()
    def test_authenticated_request_is_dispatched_without_tcp_or_proxy(self):
        with patch("socket.create_connection",side_effect=AssertionError("no TCP")):
            result = call(self.rapido,"/api/example",{"value":123})
        self.assertEqual(result,{"ok":True,"body":{"value":123}})
        self.assertNotIn(self.rapido._LOCAL_AUTH.token_for_trusted_transport(),str(result))
    def test_other_routes_methods_and_origins_are_rejected(self):
        for path in ("https://evil.example/api/example","//evil.example/api/example",
                     "/other","/api/example#fragment",r"/api\example"):
            with self.assertRaises(ValueError):
                call(self.rapido,path,{})
        with self.assertRaises(ValueError):
            call(self.rapido,"/api/example",{},method="TRACE")


if __name__ == "__main__":
    unittest.main()
