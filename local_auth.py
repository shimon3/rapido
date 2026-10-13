"""Authentication primitives for Rapido's future trusted local transport.

NOT wired into FastAPI yet: existing Windows WebView and Chrome capture must
be migrated together before protecting mutation routes. This module alone
does not fix S2 or S3.
"""
from __future__ import annotations

import hmac
import secrets


class LocalAuth:
    """Ephemeral secret for one instance, never written to disk or returned by HTTP."""

    def __init__(self) -> None:
        self._token = secrets.token_urlsafe(32)

    def verify(self, candidate: str | None) -> bool:
        if not isinstance(candidate, str):
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
