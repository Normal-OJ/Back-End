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
  the deployment settings (startup snapshot, ADR-0005), every candidate is
  rejected rather than accepted or crashing.
- Verification never raises on hostile input: non-str values and lone UTF-16
  surrogate strings (which json.loads accepts but .encode() rejects) fail closed
  to False → 401, never a 500.
"""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from ulid import ULID

from config import settings
from mongo.utils import RedisCache
from . import params
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


def _utf8(s: str) -> Optional[bytes]:
    """UTF-8 encode ``s``, or None if it cannot be encoded (fail closed).

    json.loads happily yields str values holding a lone UTF-16 surrogate (the
    JSON literal "\\ud800" decodes to such a str), and .encode() on those raises
    UnicodeEncodeError. Callers at the trust boundary use None to fail closed
    instead of letting a hostile body turn into a 500.
    """
    try:
        return s.encode()
    except UnicodeEncodeError:
        return None


def verify_registration_token(candidate: Optional[str]) -> bool:
    """Constant-time check of a register request's shared secret. Fails closed.

    The secret is a startup-snapshot deployment setting (ADR-0005): rotating
    it takes a Back-End restart; unset/empty ⇒ registration is disabled.
    """
    expected = settings.RUNNER_REGISTRATION_TOKEN
    # Fail closed: no configured secret ⇒ registration is disabled, not open.
    # Reject non-str candidates too — a JSON body can carry ints/lists/bytes,
    # and .encode() below would otherwise raise instead of returning False.
    if not expected or not isinstance(candidate, str) or not candidate:
        return False
    # Compare UTF-8 bytes: compare_digest accepts str only when both sides are
    # ASCII ("str (ASCII only)", hmac docs) and raises TypeError otherwise;
    # `candidate` is attacker-controlled, so str comparison could crash (500)
    # instead of failing closed (401). _utf8 also fails closed on a lone-
    # surrogate candidate whose .encode() would raise UnicodeEncodeError.
    expected_bytes = _utf8(expected)
    candidate_bytes = _utf8(candidate)
    if expected_bytes is None or candidate_bytes is None:
        return False
    return hmac.compare_digest(expected_bytes, candidate_bytes)


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
    ttl = params.IDENTITY_TTL_SEC
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
    # Fail closed before touching Redis on a lone-surrogate runner_id/token whose
    # UTF-8 encode raises (redis-py encodes keys to UTF-8; _token_hash encodes
    # the token) — a hostile body must 401, not 500.
    if _utf8(runner_id) is None:
        return False
    token_bytes = _utf8(token)
    if token_bytes is None:
        return False
    stored = _redis().get(redis_keys.runner_token_hash(runner_id))
    if stored is None:
        return False
    # Compare raw bytes: no assumption the stored value decodes as UTF-8.
    return hmac.compare_digest(
        stored,
        hashlib.sha256(token_bytes).hexdigest().encode())


def list_runners() -> List[Dict]:
    """Return identity-layer facts for all registered identities (spec §7.6 subset).

    Not a liveness view: a revoked or dead runner stays listed (frozen
    last_seen) until identity GC sweeps it — a deliberate observability
    window; revocation only guarantees immediate auth failure (ADR-0004).
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
    cutoff = now - params.IDENTITY_TTL_SEC

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
