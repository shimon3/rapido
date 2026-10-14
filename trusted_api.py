"""Trusted in-process API dispatch; does not send credentials over loopback."""
import asyncio
from urllib.parse import urlsplit


def call(rapido, path, body=None, *, method=None, timeout=3):
    value = urlsplit(path)
    if not path.startswith("/api/") or value.scheme or value.netloc or value.fragment or "\\" in path:
        raise ValueError("Invalid internal API route")
    method = method or ("GET" if body is None else "POST")
    if method not in {"GET","POST","PUT","DELETE"}:
        raise ValueError("Invalid internal API method")

    async def dispatch():
        import httpx
        transport = httpx.ASGITransport(app=rapido.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:9614",
                                     trust_env=False) as client:
            response = await client.request(method, path, json=body,
                headers={"Authorization":"Bearer "+rapido._LOCAL_AUTH.token_for_trusted_transport(),
                         "Content-Type":"application/json"})
            response.raise_for_status()
            return response.json()
    return asyncio.run_coroutine_threadsafe(dispatch(), rapido.manager.loop).result(timeout)
