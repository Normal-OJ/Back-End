"""Redis-based pull dispatch module (spec §11).

This slice ships only the runner-identity foundation (redis_keys, params,
runner registration / token verification / GC). It has no callers yet —
the HTTP layer and job lifecycle land in later slices.
"""
