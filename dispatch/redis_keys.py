"""Centralized Redis key naming. All Redis keys used by dispatch live here."""

# Runner namespace
RUNNERS_REGISTERED = "runners:registered"


def runner_meta_key(rn_id: str) -> str:
    return f"runner:{rn_id}:meta"


def runner_token_key(rn_id: str) -> str:
    """STRING key holding SHA-256 digest of the runner's bearer token."""
    return f"runner:{rn_id}:token_hash"


def runner_alive_key(rn_id: str) -> str:
    return f"runner:{rn_id}:alive"


# Job namespace
JOBS_PENDING = "jobs:pending"
JOBS_LEASED = "jobs:leased"


def job_key(jb_id: str) -> str:
    return f"job:{jb_id}"


def submission_current_job_key(submission_id: str) -> str:
    return f"submission:{submission_id}:current_job"
