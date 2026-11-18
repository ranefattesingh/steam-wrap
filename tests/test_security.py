import pytest

from steam_wrap.core.exceptions import InvalidTokenError
from steam_wrap.core.logging import redact
from steam_wrap.core.security import decode_steam_token
from tests.conftest import STEAMID, make_token


def test_decodes_steamid_and_expiry() -> None:
    info = decode_steam_token(make_token())
    assert info.steamid == STEAMID
    assert info.expires_at is not None
    assert "signature" not in repr(info)


@pytest.mark.parametrize(
    "token",
    ["", "not-a-jwt", "a.b", "a.!!!.c", make_token(steamid="123"), make_token(exp_in=-10)],
)
def test_rejects_bad_tokens(token: str) -> None:
    with pytest.raises(InvalidTokenError):
        decode_steam_token(token)


def test_fingerprint_differs_per_token() -> None:
    a = decode_steam_token(make_token(jti="1"))
    b = decode_steam_token(make_token(jti="2"))
    assert a.steamid == b.steamid
    assert a.fingerprint != b.fingerprint


def test_redaction() -> None:
    line = "GET /x?access_token=eyJabc.def&steamid=1 Authorization: Bearer eyJ.x.y"
    out = redact(line)
    assert "eyJ" not in out
    assert "steamid=1" in out
