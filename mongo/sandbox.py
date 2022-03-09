import secrets
from .submission import Submission


def find_by_token(token: str):
    '''
    Find sandbox by token. return None if cannot find a sandbox with that token.
    '''
    sandboxes = Submission.config().sandbox_instances
    for sandbox in sandboxes:
        if secrets.compare_digest(token, sandbox.token):
            return sandbox
    return None
