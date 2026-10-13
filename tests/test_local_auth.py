"""Unit tests of the future native-transport authenticator.

These do not imply that API endpoints are protected yet.
"""
from local_auth import LocalAuth


def test_unknown_and_empty_are_denied():
    auth = LocalAuth()
    for candidate in (None, "", "Bearer ", "Bearer invalid", "Basic secret", "invalid"):
        assert not auth.header_is_authorized(candidate)


def test_per_instance_secrets_are_distinct():
    one, two = LocalAuth(), LocalAuth()
    token = one.token_for_trusted_transport()
    assert len(token) >= 40
    assert one.verify(token)
    assert one.header_is_authorized("Bearer " + token)
    assert one.header_is_authorized("bearer " + token)
    assert not two.verify(token)
    assert not two.header_is_authorized("Bearer " + token)


def test_header_not_loosely_parsed():
    auth = LocalAuth()
    token = auth.token_for_trusted_transport()
    assert not auth.header_is_authorized("Bearer" + token)
    assert not auth.header_is_authorized("Bearer  " + token)
    assert not auth.header_is_authorized("Bearer " + token + " extra")
