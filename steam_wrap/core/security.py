"""Steam access-token handling.

Steam access tokens (the ``webapi_token`` / ``access_token`` a logged-in user
gets from the Steam store) are JWTs. Their ``sub`` claim is the user's
SteamID64, so the caller only has to send the token.

**The signature is not verified here** - Steam's public keys are not published
for that. Decoding locally is only used to (a) find the SteamID and (b) reject
obviously malformed/expired tokens early. Authority comes from Steam itself,
which validates the token on every upstream call. For that reason nothing
user-specific is ever cached by SteamID; see ``token_fingerprint``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from steam_wrap.core.exceptions import InvalidTokenError

_STEAMID64 = re.compile(r"^7656119\d{10}$")


@dataclass(frozen=True, slots=True)
class TokenInfo:
    """Claims extracted from a Steam access token."""

    token: str
    steamid: str
    expires_at: datetime | None

    @property
    def fingerprint(self) -> str:
        return token_fingerprint(self.token)

    def __repr__(self) -> str:  # never print the raw token
        return f"TokenInfo(steamid={self.steamid!r}, expires_at={self.expires_at!r})"


def token_fingerprint(token: str) -> str:
    """Stable, non-reversible identifier for a token (used as a cache key)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def decode_steam_token(token: str, *, now: float | None = None) -> TokenInfo:
    """Extract the SteamID and expiry from a Steam JWT access token.

    Raises:
        InvalidTokenError: if the token is not a JWT, has no SteamID64 ``sub``
            claim, or its ``exp`` is in the past.
    """
    token = token.strip()
    parts = token.split(".")
    if len(parts) != 3 or not all(parts[:2]):
        raise InvalidTokenError("Access token is not a valid JWT.")

    try:
        claims = json.loads(_b64url_decode(parts[1]))
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise InvalidTokenError("Access token payload could not be decoded.") from exc

    if not isinstance(claims, dict):
        raise InvalidTokenError("Access token payload is not a JSON object.")

    steamid = str(claims.get("sub", ""))
    if not _STEAMID64.match(steamid):
        raise InvalidTokenError("Access token does not contain a SteamID64 subject.")

    expires_at: datetime | None = None
    exp = claims.get("exp")
    if isinstance(exp, int | float):
        current = time.time() if now is None else now
        if exp <= current:
            raise InvalidTokenError("Access token has expired.")
        expires_at = datetime.fromtimestamp(exp, UTC)

    return TokenInfo(token=token, steamid=steamid, expires_at=expires_at)
