"""Lua scripts for atomic Redis operations."""
from datetime import datetime, timedelta, timezone

from mongo.utils import RedisCache
from .redis_keys import job_key, JOBS_PENDING, JOBS_LEASED

_CLAIM_PENDING_LUA = """
local jb_id = redis.call('RPOP', KEYS[1])
if not jb_id then
    return nil
end

local job_key = ARGV[1] .. jb_id
if redis.call('EXISTS', job_key) == 0 then
    return nil
end
if redis.call('HGET', job_key, 'state') ~= 'pending' then
    return nil
end

redis.call(
    'HSET',
    job_key,
    'state', 'leased',
    'leased_by', ARGV[2],
    'leased_at', ARGV[3],
    'lease_deadline', ARGV[4]
)
redis.call('HINCRBY', job_key, 'attempts', 1)
redis.call('SADD', ARGV[5], jb_id)
return jb_id
"""

# Lua reclaim script:
#   KEYS[1] = job:<jb_id>
#   ARGV[1] = expected_owner (rn_id we expect to currently hold the lease)
#   ARGV[2] = new_owner      (rn_id taking over)
#   ARGV[3] = leased_at      (ISO timestamp string)
#   ARGV[4] = lease_deadline (ISO timestamp string)
#   ARGV[5] = max_attempts   (string-encoded int)
#   ARGV[6] = jobs_leased_set_name
#
# Return:
#    1 = success (lease transferred, attempts incremented)
#    0 = failed (owner changed before we could reclaim)
#   -1 = exhausted (attempts >= max_attempts; job removed from leased set)
_RECLAIM_LUA = """
local current_owner = redis.call('HGET', KEYS[1], 'leased_by')
if current_owner ~= ARGV[1] then
    return 0
end
local state = redis.call('HGET', KEYS[1], 'state')
if state and state ~= 'leased' then
    return 0
end

local attempts = tonumber(redis.call('HGET', KEYS[1], 'attempts')) or 0
local max_attempts = tonumber(ARGV[5])
if attempts >= max_attempts then
    redis.call('SREM', ARGV[6], string.sub(KEYS[1], 5))
    return -1
end

redis.call(
    'HSET',
    KEYS[1],
    'leased_by', ARGV[2],
    'leased_at', ARGV[3],
    'lease_deadline', ARGV[4]
)
redis.call('HINCRBY', KEYS[1], 'attempts', 1)
return 1
"""


def claim_pending_atomic(rn_id: str, lease_ttl_sec: int) -> str | None:
    rds = RedisCache().client
    script = rds.register_script(_CLAIM_PENDING_LUA)
    leased_at = datetime.now(timezone.utc)
    lease_deadline = leased_at + timedelta(seconds=lease_ttl_sec)
    result = script(
        keys=[JOBS_PENDING],
        args=[
            "job:",
            rn_id,
            leased_at.isoformat(),
            lease_deadline.isoformat(),
            JOBS_LEASED,
        ],
    )
    if result is None:
        return None
    return result.decode() if isinstance(result, bytes) else result


def reclaim_orphan_atomic(
    jb_id: str,
    expected_owner: str,
    new_owner: str,
    max_attempts: int,
    lease_ttl_sec: int,
) -> int:
    """Atomically transfer lease from expected_owner to new_owner.

    Returns:
        1 if reclaimed
        0 if owner changed before we could reclaim
       -1 if attempts exhausted (job removed from JOBS_LEASED set)
    """
    rds = RedisCache().client
    script = rds.register_script(
        _RECLAIM_LUA)  # redis-py caches EVALSHA internally
    leased_at = datetime.now(timezone.utc)
    lease_deadline = leased_at + timedelta(seconds=lease_ttl_sec)
    return int(
        script(
            keys=[job_key(jb_id)],
            args=[
                expected_owner,
                new_owner,
                leased_at.isoformat(),
                lease_deadline.isoformat(),
                max_attempts,
                JOBS_LEASED,
            ],
        ))


# Lua renew script:
#   KEYS[1] = job:<jb_id>
#   ARGV[1] = expected_owner (rn_id)
#   ARGV[2] = new lease_deadline (ISO timestamp string)
# Return: 1 = renewed, 0 = skipped (gone / wrong owner / not leased)
_RENEW_LEASE_LUA = """
if redis.call('EXISTS', KEYS[1]) == 0 then
    return 0
end
if redis.call('HGET', KEYS[1], 'leased_by') ~= ARGV[1] then
    return 0
end
local state = redis.call('HGET', KEYS[1], 'state')
if state and state ~= 'leased' then
    return 0
end
if redis.call('HEXISTS', KEYS[1], 'je_pending') == 1 then
    return 0
end
redis.call('HSET', KEYS[1], 'lease_deadline', ARGV[2])
return 1
"""


def renew_lease_atomic(jb_id: str, rn_id: str, lease_ttl_sec: int) -> int:
    """Atomically extend a job's lease iff it still exists, is owned by
    rn_id, and is in the leased state. Returns 1 if renewed, else 0."""
    rds = RedisCache().client
    script = rds.register_script(_RENEW_LEASE_LUA)
    lease_deadline = datetime.now(
        timezone.utc) + timedelta(seconds=lease_ttl_sec)
    return int(
        script(
            keys=[job_key(jb_id)],
            args=[rn_id, lease_deadline.isoformat()],
        ))


# Lua requeue-stuck script:
#   KEYS[1] = job:<jb_id>
#   ARGV[1] = jb_id
#   ARGV[2] = max_attempts (string-encoded int)
#   ARGV[3] = jobs_pending_list_name
#   ARGV[4] = jobs_leased_set_name
# Return:
#    1 = requeued to pending
#    0 = skipped (state changed / gone)
#   -1 = attempts exhausted (removed from leased set; caller finalizes)
_REQUEUE_STUCK_LUA = """
if redis.call('EXISTS', KEYS[1]) == 0 then
    return 0
end
if redis.call('HGET', KEYS[1], 'state') ~= 'completing' then
    return 0
end

local attempts = tonumber(redis.call('HGET', KEYS[1], 'attempts')) or 0
if attempts >= tonumber(ARGV[2]) then
    redis.call('SREM', ARGV[4], ARGV[1])
    return -1
end

redis.call('HDEL', KEYS[1], 'leased_by', 'leased_at', 'lease_deadline')
redis.call('HSET', KEYS[1], 'state', 'pending')
redis.call('SREM', ARGV[4], ARGV[1])
redis.call('LPUSH', ARGV[3], ARGV[1])
return 1
"""


def requeue_stuck_completing(jb_id: str, max_attempts: int) -> int:
    """Atomically requeue a job stuck in 'completing' (backend died mid
    process_result). Caller must have checked the lease is expired.
    Returns 1 requeued, 0 skipped, -1 attempts exhausted."""
    rds = RedisCache().client
    script = rds.register_script(_REQUEUE_STUCK_LUA)
    return int(
        script(
            keys=[job_key(jb_id)],
            args=[jb_id, max_attempts, JOBS_PENDING, JOBS_LEASED],
        ))
