"""Configuration for dispatch module — env vars and tuning constants."""
import os

# Shared secret used by runners to register with backend.
# In production, set via env var (RUNNER_REGISTRATION_TOKEN).
# Default value is for tests/dev only.
RUNNER_REGISTRATION_TOKEN: str = os.getenv(
    "RUNNER_REGISTRATION_TOKEN",
    "dev-only-registration-token-change-me",
)

# Heartbeat / lease parameters
HEARTBEAT_INTERVAL_SEC: int = 15
RUNNER_ALIVE_TTL_SEC: int = 30           # 2x heartbeat
POLL_INTERVAL_SEC: int = 3
MAX_CONCURRENT_JOBS_PER_RUNNER: int = 8

# Job retry policy
MAX_ATTEMPTS: int = 3                     # 1 initial + 2 reclaims, then mark JE

# Presigned URL TTL for code download (seconds)
CODE_PRESIGNED_URL_TTL_SEC: int = 3600    # 1 hour
