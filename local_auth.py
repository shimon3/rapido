"""Per-process authentication for the protected desktop API.

The secret remains in native Python memory. WebView2 adds it natively only to
owned local requests; browser extensions use scoped Windows IPC without it.
"""
from __future__ import annotations

import hmac
import secrets


class LocalAuth:
    """Ephemeral secret for one instance, never written to disk or returned by HTTP."""

    def __init__(self) -> None:
        self._token = secrets.token_urlsafe(32)

    def verify(self, candidate: str | None) -> bool:
        if (not isinstance(candidate, str) or not candidate.isascii() or
                len(candidate) != len(self._token)):
            return False
        return hmac.compare_digest(self._token, candidate)

    def header_is_authorized(self, authorization: str | None) -> bool:
        if not isinstance(authorization, str):
            return False
        scheme, sep, value = authorization.partition(" ")
        if sep != " " or scheme.lower() != "bearer" or not value:
            return False
        return self.verify(value)

    def token_for_trusted_transport(self) -> str:
        """Only a trusted *native* caller may use this; NEVER expose by HTTP.

        This accessor must not be wired to FastAPI, UI JavaScript or logs.
        A separate protected IPC bridge is required before enabling S2.
        """
        return self._token
