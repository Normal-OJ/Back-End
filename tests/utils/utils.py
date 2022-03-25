from typing import Container, Dict

__all__ = (
    'none_or',
    'drop_none',
    'partial_dict',
)


def none_or(val, or_val):
    return val if val is not None else or_val


def drop_none(d: Dict):
    return {k: v for k, v in d.items() if v is not None}


def partial_dict(
    d: Dict,
    keys: Container[str],
):
    return {k: v for k, v in d.items() if k in keys}
