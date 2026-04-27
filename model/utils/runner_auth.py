"""@require_runner_token decorator for runner API endpoints."""
from functools import wraps
from flask import request

from dispatch import runner as runner_mod
from .response import HTTPError

__all__ = ['require_runner_token']

_BEARER_PREFIX = "Bearer "


def require_runner_token(f):
    """Verify Authorization: Bearer rk_xxx against the runner_id in URL.

    Routes using this decorator must accept a `runner_id` URL path parameter.
    """

    @wraps(f)
    def wrapper(runner_id, *args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith(_BEARER_PREFIX):
            return HTTPError("missing or malformed Authorization header", 401)
        token = auth[len(_BEARER_PREFIX):]
        if not runner_mod.verify_token(runner_id, token):
            return HTTPError("invalid runner token", 401)
        return f(runner_id, *args, **kwargs)

    return wrapper
