"""Runner identity: registration, token verification, and lazy GC (spec §7.1, §8).

Identity is soft state that can be rebuilt from scratch (ADR-0004): the
``runners:registered`` ZSET tracks last-seen, while meta/token_hash carry a 7d
TTL. Dead identities evaporate via TTL; the ZSET members (which have no TTL) are
swept lazily on register / list_runners.

Security notes:
- The runner token is returned exactly once. Only its SHA-256 hex is stored, so
  a Redis dump never reveals a usable credential.
- All token comparisons are constant-time (``hmac.compare_digest``).
- A missing ``token_hash`` key means the identity was revoked (or expired) →
  verification fails. This is the single revocation mechanism (ADR-0004).
- Registration verification fails closed: if the shared secret is unset/empty in
  the environment, every candidate is rejected rather than accepted or crashing.
"""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from ulid import ULID

from mongo.utils import RedisCache
from . import config
from . import redis_keys

RUNNER_ID_PREFIX = 'rn_'
RUNNER_TOKEN_PREFIX = 'rk_'

# One shared RedisCache instance. In production every RedisCache() shares the
# pooled real Redis, but under fakeredis each instance gets an isolated dataset;
# caching one instance keeps register/verify/list coherent in both worlds.
_cache: Optional[RedisCache] = None


@dataclass(frozen=True)
class Registration:
    runner_id: str
    token: str


def _redis():
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache.client


def _now() -> float:
    return time.time()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_registration_token(candidate: Optional[str]) -> bool:
    """Constant-time check of a register request's shared secret. Fails closed."""
    expected = config.registration_token()
    # Fail closed: no configured secret ⇒ registration is disabled, not open.
    if not expected or not candidate:
        return False
    # Compare UTF-8 bytes: compare_digest raises TypeError on non-ASCII str, and
    # `candidate` is attacker-controlled, so str comparison could crash (500)
    # instead of failing closed (401).
    return hmac.compare_digest(expected.encode(), candidate.encode())


def register(name: str, ip: str) -> Registration:
    """Mint a fresh runner identity and persist its soft state (spec §7.1).

    Returns the runner_id and the plaintext token (shown once). Only the token's
    SHA-256 hex is stored. Also sweeps expired identities before registering.
    """
    now = _now()
    _gc(now)

    runner_id = RUNNER_ID_PREFIX + str(ULID())
    token = RUNNER_TOKEN_PREFIX + secrets.token_urlsafe(32)

    client = _redis()
    ttl = config.IDENTITY_TTL_SEC
    meta_key = redis_keys.runner_meta(runner_id)

    pipe = client.pipeline()
    pipe.zadd(redis_keys.RUNNERS_REGISTERED, {runner_id: now})
    pipe.hset(
        meta_key,
        mapping={
            'name': name,
            'registered_at': repr(now),
            'registration_ip': ip,
        },
    )
    pipe.expire(meta_key, ttl)
    pipe.set(redis_keys.runner_token_hash(runner_id),
             _token_hash(token),
             ex=ttl)
    pipe.execute()

    return Registration(runner_id=runner_id, token=token)


def verify_token(runner_id: Optional[str], token: Optional[str]) -> bool:
    """Constant-time check that ``token`` matches the stored hash for ``runner_id``.

    A missing token_hash key (revoked or expired) yields ``False`` (→ 401).
    """
    if not runner_id or not token:
        return False
    stored = _redis().get(redis_keys.runner_token_hash(runner_id))
    if stored is None:
        return False
    stored_hex = stored.decode()
    return hmac.compare_digest(stored_hex, _token_hash(token))


def list_runners() -> List[Dict]:
    """Return identity-layer facts for all live runners (spec §7.6 subset).

    Sweeps expired identities first. Fields: runner_id, name, last_seen,
    registered_at. Liveness/held-jobs are added by the admin-API slice.
    """
    now = _now()
    _gc(now)

    client = _redis()
    members = client.zrange(redis_keys.RUNNERS_REGISTERED,
                            0,
                            -1,
                            withscores=True)

    runners: List[Dict] = []
    for member, score in members:
        runner_id = member.decode() if isinstance(member, bytes) else member
        raw_meta = client.hgetall(redis_keys.runner_meta(runner_id))
        meta = {
            (k.decode() if isinstance(k, bytes) else k):
            (v.decode() if isinstance(v, bytes) else v)
            for k, v in raw_meta.items()
        }
        runners.append({
            'runner_id': runner_id,
            'name': meta.get('name'),
            'last_seen': score,
            'registered_at': meta.get('registered_at'),
        })
    return runners


def _gc(now: Optional[float] = None) -> None:
    """Evict identities whose last-seen is older than the 7d TTL.

    Removes the ZSET member (which carries no TTL of its own) plus the meta,
    token_hash and alive keys. Meta/token_hash usually expire on their own; the
    explicit deletes keep the namespace clean even if timing drifts.
    """
    if now is None:
        now = _now()
    cutoff = now - config.IDENTITY_TTL_SEC

    client = _redis()
    # Strictly older than the cutoff: '(' makes the max bound exclusive.
    expired = client.zrangebyscore(
        redis_keys.RUNNERS_REGISTERED,
        '-inf',
        f'({cutoff!r}',
    )
    if not expired:
        return

    pipe = client.pipeline()
    for member in expired:
        runner_id = member.decode() if isinstance(member, bytes) else member
        pipe.zrem(redis_keys.RUNNERS_REGISTERED, runner_id)
        pipe.delete(redis_keys.runner_meta(runner_id))
        pipe.delete(redis_keys.runner_token_hash(runner_id))
        pipe.delete(redis_keys.runner_alive(runner_id))
    pipe.execute()
