"""Lua scripts for atomic Redis operations."""
from datetime import datetime, timezone

from mongo.utils import RedisCache
from .redis_keys import job_key, JOBS_LEASED


# Lua reclaim script:
#   KEYS[1] = job:<jb_id>
#   ARGV[1] = expected_owner (rn_id we expect to currently hold the lease)
#   ARGV[2] = new_owner      (rn_id taking over)
#   ARGV[3] = leased_at      (ISO timestamp string)
#   ARGV[4] = max_attempts   (string-encoded int)
#   ARGV[5] = jobs_leased_set_name
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

local attempts = tonumber(redis.call('HGET', KEYS[1], 'attempts')) or 0
local max_attempts = tonumber(ARGV[4])
if attempts >= max_attempts then
    redis.call('SREM', ARGV[5], string.sub(KEYS[1], 5))
    return -1
end

redis.call('HSET', KEYS[1], 'leased_by', ARGV[2], 'leased_at', ARGV[3])
redis.call('HINCRBY', KEYS[1], 'attempts', 1)
return 1
"""

_script_cache = {}


def _get_reclaim_script():
    """Lazily register the script (so we get a fresh script per Redis client)."""
    rds = RedisCache().client
    cache_key = id(rds)
    if cache_key not in _script_cache:
        _script_cache[cache_key] = rds.register_script(_RECLAIM_LUA)
    return _script_cache[cache_key]


def reclaim_orphan_atomic(
    jb_id: str,
    expected_owner: str,
    new_owner: str,
    max_attempts: int,
) -> int:
    """Atomically transfer lease from expected_owner to new_owner.

    Returns:
        1 if reclaimed
        0 if owner changed before we could reclaim
       -1 if attempts exhausted (job removed from JOBS_LEASED set)
    """
    script = _get_reclaim_script()
    leased_at = datetime.now(timezone.utc).isoformat()
    return int(
        script(
            keys=[job_key(jb_id)],
            args=[expected_owner, new_owner, leased_at, max_attempts, JOBS_LEASED],
        ))
