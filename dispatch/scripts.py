"""Lua scripts — one per job state transition (spec §8, §9).

Each script is atomic on the Redis side, so a state transition can never be
observed half-applied even under concurrent runners (INV2/INV3/INV4/INV5).
Every script takes ``now`` via ARGV — never ``redis.call('TIME')`` — so tests
are deterministic and fakeredis (which has no server clock for scripts) works.

The scripts here cover slice 2 of the delivery plan (§15.2): ``claim_pending``,
``renew_lease``, ``reclaim_expired``. ``abort_requeue`` belongs to slice 3 and
is deliberately absent.

Key handling: static keys (``jobs:pending``, ``jobs:leased``, a specific
``job:<jb>`` hash) are passed in as KEYS by the Python layer via redis_keys.
``claim_pending`` is the sole exception — it discovers a job id by RPOP and so
must build that job's ``job:<jb>`` hash key and its
``submission:<sid>:current_job`` pointer key from inside Lua; those two literal
templates mirror ``redis_keys.job`` / ``redis_keys.submission_current_job`` and
are the only place key names are spelled outside redis_keys.

Corrupted state (partial Redis data loss — never produced by normal operation)
is reaped lazily, in passing: the job hash is the single source of truth and
the pending list / leased set are only indexes, so a script that stumbles on a
dangling entry destroys or unindexes it and moves on instead of erroring. The
affected submission stays Pending and is rescued by rejudge (spec §12).
"""

from dataclasses import dataclass
from typing import Any

# claim_pending — pending → leased, with dispatch-side currency destroy (INV4).
#
# KEYS[1] = jobs:pending (LIST)   KEYS[2] = jobs:leased (SET)
# ARGV[1] = now   ARGV[2] = runner_id   ARGV[3] = lease_ttl_sec
#
# Loop popping the FIFO tail: a job whose hash has evaporated or lost its
# submission_id (currency would be unverifiable — corrupted beyond judging) is
# destroyed and skipped; a job that is no longer its submission's current_job is
# destroyed on the spot (the dispatch-side half of INV4 — a superseded rejudge
# job never runs); the first live current job is leased (attempts+1,
# state=leased) and its id returned. A missing attempts field falls back to 0
# instead of erroring — the id is already popped at that point, so a script
# error would silently lose the job. Empty queue → nil.
CLAIM_PENDING = '''
local now = tonumber(ARGV[1])
local runner = ARGV[2]
local ttl = tonumber(ARGV[3])
while true do
  local jb = redis.call('RPOP', KEYS[1])
  if not jb then
    return nil
  end
  local job_key = 'job:' .. jb
  local sid = redis.call('HGET', job_key, 'submission_id')
  if not sid then
    -- Hash evaporated (DEL is a no-op then) or corrupted beyond judging (no
    -- submission_id means currency cannot be verified): destroy, move on.
    redis.call('DEL', job_key)
  else
    local current = redis.call('GET', 'submission:' .. sid .. ':current_job')
    if current == jb then
      local attempts = (tonumber(redis.call('HGET', job_key, 'attempts')) or 0) + 1
      redis.call('HSET', job_key,
        'attempts', attempts,
        'leased_by', runner,
        'lease_deadline', now + ttl,
        'state', 'leased')
      redis.call('SADD', KEYS[2], jb)
      return jb
    else
      redis.call('DEL', job_key)
    end
  end
end
'''

# renew_lease — heartbeat extends an owned lease (spec §7.2).
#
# KEYS[1] = jobs:leased (SET)   KEYS[2] = job:<jb> (HASH)
# ARGV[1] = job_id   ARGV[2] = runner_id   ARGV[3] = now   ARGV[4] = lease_ttl_sec
#
# Only when the job is still leased AND owned by the caller: push the deadline to
# now+ttl, return 1. Anything else (not leased, wrong owner, evaporated hash) →
# 0. An evaporated hash additionally reaps the ghost member from jobs:leased —
# the hash is the source of truth, the set only an index. Never creates or
# resurrects a key (SREM only removes) — HSET runs only on the confirmed-owner
# path, where the hash provably exists.
RENEW_LEASE = '''
if redis.call('SISMEMBER', KEYS[1], ARGV[1]) == 0 then
  return 0
end
if redis.call('EXISTS', KEYS[2]) == 0 then
  -- Hash is the source of truth; a member whose hash evaporated is a ghost --
  -- reap it so the orphan scan stops rescanning it forever.
  redis.call('SREM', KEYS[1], ARGV[1])
  return 0
end
local leased_by = redis.call('HGET', KEYS[2], 'leased_by')
if leased_by == ARGV[2] then
  redis.call('HSET', KEYS[2], 'lease_deadline', tonumber(ARGV[3]) + tonumber(ARGV[4]))
  return 1
end
return 0
'''

# reclaim_expired — expired lease → new leaseholder, or converge (spec §7.3, §9).
#
# KEYS[1] = jobs:leased (SET)   KEYS[2] = job:<jb> (HASH)
# ARGV[1] = job_id   ARGV[2] = new_runner   ARGV[3] = now
# ARGV[4] = lease_ttl_sec   ARGV[5] = max_attempts
#
# Eligibility is decided ONLY by lease_deadline vs now (INV2) — runner liveness
# never enters. If expired and attempts < max: attempts+1, hand to new_runner,
# fresh deadline, return 1. If expired and attempts already >= max: return -1 and
# leave the job UNTOUCHED (INV5 boundary; the JE landing sweep is slice 3, not
# this script's job). Not leased / not expired → 0. An evaporated hash → 0 and
# the ghost member is reaped from jobs:leased (hash is the source of truth); a
# hash that still exists but lost its lease_deadline field stays tracked — a
# runner may well be judging it, and tearing down live state risks losing the
# job entirely.
RECLAIM_EXPIRED = '''
if redis.call('SISMEMBER', KEYS[1], ARGV[1]) == 0 then
  return 0
end
if redis.call('EXISTS', KEYS[2]) == 0 then
  -- Hash is the source of truth; a member whose hash evaporated is a ghost --
  -- reap it so the orphan scan stops rescanning it forever.
  redis.call('SREM', KEYS[1], ARGV[1])
  return 0
end
local deadline = redis.call('HGET', KEYS[2], 'lease_deadline')
if not deadline then
  -- Hash alive but the field is gone: leave it tracked (see header note).
  return 0
end
local now = tonumber(ARGV[3])
if tonumber(deadline) >= now then
  return 0
end
local attempts = tonumber(redis.call('HGET', KEYS[2], 'attempts'))
if attempts >= tonumber(ARGV[5]) then
  return -1
end
redis.call('HSET', KEYS[2],
  'attempts', attempts + 1,
  'leased_by', ARGV[2],
  'lease_deadline', now + tonumber(ARGV[4]),
  'state', 'leased')
return 1
'''


@dataclass(frozen=True)
class Scripts:
    claim_pending: Any
    renew_lease: Any
    reclaim_expired: Any


def load(client) -> Scripts:
    """Register the per-transition scripts on ``client`` and return them.

    ``register_script`` is cheap (it only stores the body and computes the SHA
    lazily on first EVALSHA), so binding to the currently active shared client on
    each use keeps scripts coherent with the ``_cache`` reset done per test.
    """
    return Scripts(
        claim_pending=client.register_script(CLAIM_PENDING),
        renew_lease=client.register_script(RENEW_LEASE),
        reclaim_expired=client.register_script(RECLAIM_EXPIRED),
    )
