"""
BIAR Protocol - Wallet authentication (SIWE-style sign-in + JWT sessions).

Flow:
  1. Client requests a nonce:            POST /api/v1/auth/nonce   {address}
  2. Client signs the challenge message with their wallet (EIP-191).
  3. Client submits the signature:       POST /api/v1/auth/verify  {address, signature}
  4. Server recovers the signer via ecrecover; if it matches the address,
     a JWT session token is issued (24h default expiry).

The JWT is then passed as `Authorization: Bearer <token>` on authenticated
routes (orders, portfolio, limit orders).
"""
import datetime
import secrets
import time
from typing import Optional

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.config import settings


class AuthError(Exception):
    pass


# ---------- nonce store (in-memory; use Redis for multi-instance) ----------

class NonceStore:
    """Single-use challenge nonces with TTL."""

    def __init__(self, ttl_seconds: int | None = None):
        self._nonces: dict[str, tuple[str, float]] = {}  # address -> (nonce, issued_at)
        self.ttl = ttl_seconds or settings.NONCE_TTL_SECONDS

    def issue(self, address: str) -> str:
        nonce = secrets.token_hex(16)
        self._nonces[address.lower()] = (nonce, time.monotonic())
        self._evict()
        return nonce

    def consume(self, address: str, nonce: str) -> bool:
        """Validate and burn a nonce. Returns False if unknown/expired/mismatched."""
        entry = self._nonces.get(address.lower())
        if entry is None:
            return False
        stored_nonce, issued_at = entry
        del self._nonces[address.lower()]
        if stored_nonce != nonce:
            return False
        if time.monotonic() - issued_at > self.ttl:
            return False
        return True

    def _evict(self) -> None:
        now = time.monotonic()
        expired = [a for a, (_, t) in self._nonces.items() if now - t > self.ttl]
        for a in expired:
            del self._nonces[a]


nonce_store = NonceStore()


# ---------- challenge message ----------

def build_challenge_message(address: str, nonce: str) -> str:
    """SIWE-style human-readable sign-in message."""
    issued = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"{settings.APP_NAME} wants you to sign in with your Ethereum account:\n"
        f"{address}\n"
        f"\n"
        f"By signing, you prove ownership of this wallet. This signature will not\n"
        f"trigger any blockchain transaction or cost any gas.\n"
        f"\n"
        f"URI: https://biar.protocol\n"
        f"Version: 1\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued}"
    )


# ---------- signature verification ----------

def verify_signature(address: str, message: str, signature: str) -> bool:
    """Recover the signer of an EIP-191 personal_sign message and compare."""
    try:
        recovered = Account.recover_message(
            encode_defunct(text=message), signature=signature
        )
    except Exception:
        return False
    return recovered.lower() == address.lower()


# ---------- JWT sessions ----------

def _get_secret() -> str:
    secret = settings.JWT_SECRET
    if not secret:
        if settings.DEBUG:
            # Deterministic dev-only fallback so tests/local work without config.
            return "biar-dev-secret-do-not-use-in-production"
        raise AuthError("JWT_SECRET must be configured in production")
    return secret


def create_session_token(address: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": address.lower(),
        "iat": now,
        "exp": now + datetime.timedelta(seconds=settings.JWT_EXPIRY_SECONDS),
        "iss": settings.APP_NAME,
    }
    return jwt.encode(payload, _get_secret(), algorithm=settings.JWT_ALGORITHM)


def verify_session_token(token: str) -> str:
    """Return the wallet address for a valid token, or raise AuthError."""
    try:
        payload = jwt.decode(
            token, _get_secret(), algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError as e:
        raise AuthError(f"Invalid session token: {e}") from e
    sub = payload.get("sub")
    if not sub:
        raise AuthError("Invalid session token: missing subject")
    return sub


# ---------- FastAPI dependency ----------

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Resolve the authenticated wallet address.

    If AUTH_REQUIRED is false, unauthenticated requests resolve to 'anonymous'
    (read-only / demo mode). If AUTH_REQUIRED is true, a valid Bearer token is
    mandatory.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        if settings.AUTH_REQUIRED:
            raise HTTPException(status_code=401, detail="Authentication required")
        return "anonymous"
    try:
        return verify_session_token(credentials.credentials)
    except AuthError:
        if settings.AUTH_REQUIRED:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        return "anonymous"


def require_auth(user: str = Depends(get_current_user)) -> str:
    """Dependency for routes that must always be authenticated."""
    if user == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")
    return user