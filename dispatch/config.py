"""Pull-dispatch parameters (spec §13) and the registration-token accessor."""

import os
from typing import Optional

# --- §13 parameters -----------------------------------------------------
HEARTBEAT_INTERVAL_SEC = 15
LEASE_TTL_SEC = 30
POLL_INTERVAL_SEC = 3
ORPHAN_SCAN_INTERVAL_SEC = 15
MAX_ATTEMPTS = 3
IDENTITY_TTL_SEC = 7 * 24 * 60 * 60  # 7 days
PRESIGNED_URL_TTL_SEC = 60 * 60  # 1 hour
MAX_CONCURRENT_JOBS = 8  # advertised to runners in the register response (§7.1)

_REGISTRATION_TOKEN_ENV = 'RUNNER_REGISTRATION_TOKEN'


def registration_token() -> Optional[str]:
    """The shared runner registration secret, read live from the environment.

    Read at call time (not cached at import) so the value stays consistent
    with the deployed env and so verification fails closed the moment the
    secret is removed. Returns ``None`` when unset or empty; callers must
    treat that as "reject everything" rather than crashing.
    """
    token = os.getenv(_REGISTRATION_TOKEN_ENV)
    if not token:
        return None
    return token
