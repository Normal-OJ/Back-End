"""Lua scripts — one per job state transition (spec §8, §9).

Each script is atomic on the Redis side, so a state transition can never be
observed half-applied even under concurrent runners (INV2/INV3/INV4/INV5).
Every script takes ``now`` via ARGV — never ``redis.call('TIME')`` — so tests
are deterministic and fakeredis (which has no server clock for scripts) works.

The scripts here cover slices 2 and 3 of the delivery plan (§15.2):
``claim_pending``, ``renew_lease``, ``reclaim_expired`` (slice 2) and
``complete_begin``, ``complete_finish``, ``complete_restore``, ``abort_requeue``
(slice 3 — result landing / abort / JE convergence).

Key handling: static keys (``jobs:pending``, ``jobs:leased``, a specific
``job:<jb>`` hash) are passed in as KEYS by the Python layer via redis_keys.
The ``submission:<sid>:current_job`` pointer key is the exception — several
scripts learn ``sid`` only after reading it out of the job hash and so must
build that pointer key from inside Lua (``claim_pending`` discovers the job id
by RPOP and builds both keys the same way). Those literal templates mirror
``redis_keys.job`` / ``redis_keys.submission_current_job`` and are the only
place key names are spelled outside redis_keys.

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

# complete_begin — ownership + currency gate, then mark completing (INV3/INV4).
#
# KEYS[1] = jobs:leased (SET)   KEYS[2] = job:<jb> (HASH)
# ARGV[1] = job_id   ARGV[2] = runner_id
#
# Entry gate of the single-writer landing (INV3). Ownership is checked before
# currency so a reclaimed-away or never-owned job answers 409, not a stale drop.
# Currency (INV4, result side) destroys the job hash and unindexes it but never
# touches the pointer — the pointer belongs to whoever is current now. A hash
# that lost its submission_id is corrupted beyond a currency check and is treated
# as a stale drop (same policy as claim_pending). The lease_deadline is left
# alone on purpose: a lease expiring during a slow Mongo write is deliberately
# reclaimable (spec §9), and the per-submission lock + delete-after-write is what
# bounds double writes — not lease extension. Returns 1 proceed / 0 not-owner /
# -1 stale-or-corrupt destroyed / -2 gone.
COMPLETE_BEGIN = '''
if redis.call('EXISTS', KEYS[2]) == 0 then
  redis.call('SREM', KEYS[1], ARGV[1])
  return -2
end
if redis.call('HGET', KEYS[2], 'leased_by') ~= ARGV[2] then
  return 0
end
local sid = redis.call('HGET', KEYS[2], 'submission_id')
if not sid then
  redis.call('DEL', KEYS[2])
  redis.call('SREM', KEYS[1], ARGV[1])
  return -1
end
if redis.call('GET', 'submission:' .. sid .. ':current_job') ~= ARGV[1] then
  redis.call('DEL', KEYS[2])
  redis.call('SREM', KEYS[1], ARGV[1])
  return -1
end
redis.call('HSET', KEYS[2], 'state', 'completing')
return 1
'''

# complete_finish — post-Mongo-success cleanup, the sole INV1 exit for a result.
#
# KEYS[1] = jobs:leased (SET)   KEYS[2] = job:<jb> (HASH)
# ARGV[1] = job_id
#
# The result has landed, so the job is done: DEL the hash and SREM it
# unconditionally (a reclaim that re-leased it mid-write does not matter — the
# re-run runner's later complete answers -2/404 and drops). The pointer is
# deleted only if it still points at this job (compare-and-delete): a rejudge may
# have advanced current_job to a newer job while we wrote, and that pointer is
# not ours to clear. Returns 1, or 0 if the hash was already gone (still SREMs).
COMPLETE_FINISH = '''
local sid = redis.call('HGET', KEYS[2], 'submission_id')
local existed = redis.call('DEL', KEYS[2])
redis.call('SREM', KEYS[1], ARGV[1])
if sid and redis.call('GET', 'submission:' .. sid .. ':current_job') == ARGV[1] then
  redis.call('DEL', 'submission:' .. sid .. ':current_job')
end
if existed == 1 then
  return 1
end
return 0
'''

# complete_restore — undo the completing mark after a failed Mongo write.
#
# KEYS[1] = job:<jb> (HASH)
# ARGV[1] = runner_id   ARGV[2] = last_error (pre-truncated to <=200 chars)
#
# Lets the same runner's retry re-enter complete_begin. Only acts when the hash
# still exists, is owned by the same runner, and is still in completing: if a
# reclaim already handed the job to a new owner, leased_by differs and restore
# must NOT stomp the new owner's state. lease_deadline is untouched. Anything
# else → 0, no write.
COMPLETE_RESTORE = '''
if redis.call('EXISTS', KEYS[1]) == 0 then
  return 0
end
if redis.call('HGET', KEYS[1], 'leased_by') ~= ARGV[1] then
  return 0
end
if redis.call('HGET', KEYS[1], 'state') ~= 'completing' then
  return 0
end
redis.call('HSET', KEYS[1], 'state', 'leased', 'last_error', ARGV[2])
return 1
'''

# abort_requeue — clear lease, requeue at tail, count by reason (spec §7.5, INV5).
#
# KEYS[1] = jobs:leased (SET)   KEYS[2] = jobs:pending (LIST)   KEYS[3] = job:<jb>
# ARGV[1] = job_id   ARGV[2] = runner_id   ARGV[3] = reason
# ARGV[4] = max_attempts
#
# Ownership then currency, same as complete_begin: evaporated hash → -2 (404),
# wrong owner → 0 (409), lost submission_id / superseded job → destroy + -1
# (requeueing a stale job is pointless; the pointer is never touched). ``drain``
# must not cost the job an attempt (rolling restarts must not shorten a job's
# life, spec §7.5): claim counts on every claim, but a drained execution never
# ran to a verdict, so the claim+drain round-trip must net zero — the drain
# branch REFUNDS one attempt (floored at 0) as it resets to pending and LPUSHes
# onto the queue tail (same side as enqueue; RPOP serves the head); otherwise a
# rolling restart would erode the retry budget.
# ``prep_failed`` / ``rejected`` both count: attempts+1, and at the ceiling the
# job is left IN jobs:leased with an immediately-expired lease (leased_by
# unchanged) — the exact orphan shape reclaim_expired answers -1 to, so a JE
# landing sweep can still find it if the caller's inline landing fails (INV1).
# Below the ceiling it requeues like drain. Reason is validated in Python; the
# script assumes one of the three. Returns 1 requeued / 2 converged / -1 stale /
# -2 gone / 0 not-owner.
ABORT_REQUEUE = '''
if redis.call('EXISTS', KEYS[3]) == 0 then
  redis.call('SREM', KEYS[1], ARGV[1])
  return -2
end
if redis.call('HGET', KEYS[3], 'leased_by') ~= ARGV[2] then
  return 0
end
local sid = redis.call('HGET', KEYS[3], 'submission_id')
if not sid then
  redis.call('DEL', KEYS[3])
  redis.call('SREM', KEYS[1], ARGV[1])
  return -1
end
if redis.call('GET', 'submission:' .. sid .. ':current_job') ~= ARGV[1] then
  redis.call('DEL', KEYS[3])
  redis.call('SREM', KEYS[1], ARGV[1])
  return -1
end
if ARGV[3] == 'drain' then
  local refunded = math.max(0, (tonumber(redis.call('HGET', KEYS[3], 'attempts')) or 0) - 1)
  redis.call('HSET', KEYS[3],
    'state', 'pending', 'leased_by', '', 'lease_deadline', 0,
    'attempts', refunded, 'last_error', 'abort:drain')
  redis.call('SREM', KEYS[1], ARGV[1])
  redis.call('LPUSH', KEYS[2], ARGV[1])
  return 1
end
local attempts = (tonumber(redis.call('HGET', KEYS[3], 'attempts')) or 0) + 1
redis.call('HSET', KEYS[3], 'attempts', attempts, 'last_error', 'abort:' .. ARGV[3])
if attempts >= tonumber(ARGV[4]) then
  redis.call('HSET', KEYS[3], 'lease_deadline', 0)
  return 2
end
redis.call('HSET', KEYS[3],
  'state', 'pending', 'leased_by', '', 'lease_deadline', 0)
redis.call('SREM', KEYS[1], ARGV[1])
redis.call('LPUSH', KEYS[2], ARGV[1])
return 1
'''


@dataclass(frozen=True)
class Scripts:
    claim_pending: Any
    renew_lease: Any
    reclaim_expired: Any
    complete_begin: Any
    complete_finish: Any
    complete_restore: Any
    abort_requeue: Any


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
        complete_begin=client.register_script(COMPLETE_BEGIN),
        complete_finish=client.register_script(COMPLETE_FINISH),
        complete_restore=client.register_script(COMPLETE_RESTORE),
        abort_requeue=client.register_script(ABORT_REQUEUE),
    )
