"""Pull-dispatch protocol parameters (spec §13).

Deployment settings never live here — they live in the top-level
``config.py`` Settings (ADR-0005).
"""

HEARTBEAT_INTERVAL_SEC = 15
LEASE_TTL_SEC = 30
POLL_INTERVAL_SEC = 3
ORPHAN_SCAN_INTERVAL_SEC = 15
MAX_ATTEMPTS = 3
IDENTITY_TTL_SEC = 7 * 24 * 60 * 60  # 7 days
PRESIGNED_URL_TTL_SEC = 60 * 60  # 1 hour
MAX_CONCURRENT_JOBS = 8  # advertised to runners in the register response (§7.1)
