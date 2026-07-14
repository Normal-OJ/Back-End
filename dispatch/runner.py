"""Runner identity: registration, token verification, and lazy GC (spec §7.1, §8).

Identity is soft state that can be rebuilt from scratch (ADR-0004): the
``runners:registered`` ZSET tracks last-seen, while meta/token_hash carry a 7d
TTL. TTL is the *only* thing that invalidates a live identity. GC never kills an
identity — it lazily sweeps the corpses (ZSET members have no TTL of their own)
left behind once ``token_hash`` has already evaporated, so a heartbeat that
renews an identity between GC's scan and sweep can never lose its just-renewed
token (the TOCTOU is structurally impossible, no atomicity machinery needed).

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
    # Reject non-str candidates too — a JSON body can carry ints/lists/bytes,
    # and .encode() below would otherwise raise instead of returning False.
    if not expected or not isinstance(candidate, str) or not candidate:
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
    # Reject non-str inputs from the trust boundary: runner_id feeds a Redis key
    # and token feeds _token_hash().encode() — both would otherwise raise.
    if not isinstance(runner_id, str) or not isinstance(token, str):
        return False
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
    """Sweep ZSET corpses whose identity keys have already evaporated via TTL.

    TTL is the sole invalidator: GC only removes a member once its
    ``token_hash`` is already gone. The score prefilter (>7d stale) just narrows
    the candidate set; any candidate whose ``token_hash`` still exists is skipped
    untouched — its TTL has not fired, so touching it is exactly what caused the
    TOCTOU (a heartbeat renewing the key between scan and delete).

    Race-freedom without atomicity: once a ``token_hash`` is gone it can never
    reappear for the same ``rn_id`` — register always mints a fresh ULID, and
    heartbeat (future) requires token auth that fails without the key. So an
    ``EXISTS == 0`` observation stays true, making the sweep safe.
    """
    if now is None:
        now = _now()
    cutoff = now - config.IDENTITY_TTL_SEC

    client = _redis()
    # Strictly older than the cutoff: '(' makes the max bound exclusive.
    candidates = client.zrangebyscore(
        redis_keys.RUNNERS_REGISTERED,
        '-inf',
        f'({cutoff!r}',
    )
    if not candidates:
        return

    runner_ids = [
        member.decode() if isinstance(member, bytes) else member
        for member in candidates
    ]

    # Only sweep members whose token_hash has already expired (TTL fired).
    exists_pipe = client.pipeline()
    for runner_id in runner_ids:
        exists_pipe.exists(redis_keys.runner_token_hash(runner_id))
    token_hash_exists = exists_pipe.execute()

    sweep = [
        runner_id
        for runner_id, has_token in zip(runner_ids, token_hash_exists)
        if not has_token
    ]
    if not sweep:
        return

    pipe = client.pipeline()
    for runner_id in sweep:
        pipe.zrem(redis_keys.RUNNERS_REGISTERED, runner_id)
        pipe.delete(redis_keys.runner_meta(runner_id))
        pipe.delete(redis_keys.runner_alive(runner_id))
    pipe.execute()
