"""Runner lifecycle: registration, token verification, liveness tracking."""
import hashlib
import secrets
from datetime import datetime, timezone

from ulid import ULID

from mongo.utils import RedisCache
from .config import RUNNER_ALIVE_TTL_SEC
from .redis_keys import (
    RUNNERS_REGISTERED,
    runner_alive_key,
    runner_meta_key,
    runner_token_key,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_token(rk_token: str) -> str:
    return hashlib.sha256(rk_token.encode()).hexdigest()


def register(name: str, registration_ip: str) -> tuple[str, str]:
    """Register a new runner. Returns (rn_id, rk_token).

    rk_token is returned in plaintext only here — backend stores only the hash.
    """
    rn_id = f"rn_{ULID()}"
    rk_token = f"rk_{secrets.token_urlsafe(32)}"
    rds = RedisCache().client

    rds.hset(
        runner_meta_key(rn_id),
        mapping={
            "name": name,
            "registered_at": _now_iso(),
            "registration_ip": registration_ip,
        },
    )
    rds.set(runner_token_key(rn_id), _hash_token(rk_token))
    rds.sadd(RUNNERS_REGISTERED, rn_id)
    rds.set(runner_alive_key(rn_id), "1", ex=RUNNER_ALIVE_TTL_SEC)
    return rn_id, rk_token


def verify_token(rn_id: str, rk_token: str) -> bool:
    """Verify a runner's token. Returns False if rn_id unknown or token mismatch."""
    rds = RedisCache().client
    stored = rds.get(runner_token_key(rn_id))
    if stored is None:
        return False
    expected_hash = stored.decode() if isinstance(stored, bytes) else stored
    actual_hash = _hash_token(rk_token)
    return secrets.compare_digest(expected_hash, actual_hash)


def renew_alive(rn_id: str) -> None:
    """Refresh runner alive TTL. Called on every heartbeat.

    Caller MUST verify the runner's token before calling this — does not
    check existence and will create the key for any rn_id string.
    """
    RedisCache().client.set(runner_alive_key(rn_id),
                            "1",
                            ex=RUNNER_ALIVE_TTL_SEC)


def is_alive(rn_id: str) -> bool:
    """True if this runner has a non-expired alive key."""
    return bool(RedisCache().client.exists(runner_alive_key(rn_id)))


def verify_any_token(rk_token: str) -> bool:
    """Check if rk_token belongs to any registered runner.

    Used by endpoints that accept rk_token via query string (legacy auth shape
    inherited from old SANDBOX_TOKEN endpoints — testdata fetching).
    Linear scan over registered runners; fine for small N. If runner count
    grows, add a reverse-index of token_hash -> rn_id.
    """
    rds = RedisCache().client
    for rn_id_bytes in rds.smembers(RUNNERS_REGISTERED):
        rn_id = rn_id_bytes.decode()
        if verify_token(rn_id, rk_token):
            return True
    return False
