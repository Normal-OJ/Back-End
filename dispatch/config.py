"""Configuration for dispatch module — env vars and tuning constants."""
import os

# Shared secret used by runners to register with backend.
# In production, set via env var (RUNNER_REGISTRATION_TOKEN).
# Default value is for tests/dev only.
DEFAULT_RUNNER_REGISTRATION_TOKEN = "dev-only-registration-token-change-me"
RUNNER_REGISTRATION_TOKEN: str = os.getenv(
    "RUNNER_REGISTRATION_TOKEN",
    DEFAULT_RUNNER_REGISTRATION_TOKEN,
)
RUNNER_REQUIRE_SECURE_TOKEN: bool = os.getenv(
    "RUNNER_REQUIRE_SECURE_TOKEN",
    "",
).lower() in {"1", "true", "yes", "on"}

if RUNNER_REQUIRE_SECURE_TOKEN and (not RUNNER_REGISTRATION_TOKEN
                                    or RUNNER_REGISTRATION_TOKEN
                                    == DEFAULT_RUNNER_REGISTRATION_TOKEN):
    raise RuntimeError(
        "RUNNER_REGISTRATION_TOKEN must be set to a non-default value when "
        "RUNNER_REQUIRE_SECURE_TOKEN=true")

# Heartbeat / lease parameters
HEARTBEAT_INTERVAL_SEC: int = 15
RUNNER_ALIVE_TTL_SEC: int = 30  # 2x heartbeat
POLL_INTERVAL_SEC: int = 3
MAX_CONCURRENT_JOBS_PER_RUNNER: int = 8
JOB_LEASE_TTL_SEC: int = 600
SUBMISSION_JOB_LOCK_TTL_SEC: int = 600

# Job retry policy
MAX_ATTEMPTS: int = 3  # 1 initial + 2 reclaims, then mark JE

# Presigned URL TTL for code download (seconds)
CODE_PRESIGNED_URL_TTL_SEC: int = 3600  # 1 hour
