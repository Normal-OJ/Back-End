from typing import Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

__all__ = ['NOJException', 'HTTPResponse', 'HTTPRedirect', 'HTTPError']


class NOJException(HTTPException):
    """Carries the {status, message, data} envelope used by all NOJ error responses."""

    def __init__(self, message: str, status_code: int, data: Any = None):
        super().__init__(status_code=status_code)
        self.message = message
        self.data = data


def _apply_cookies(resp, cookies: dict):
    for k, v in cookies.items():
        if v is None:
            resp.delete_cookie(k.replace('_httponly', ''))
        else:
            httponly = k.endswith('_httponly')
            resp.set_cookie(k.replace('_httponly', ''), v, httponly=httponly)
    return resp


def HTTPResponse(
    message: str = '',
    status_code: int = 200,
    status: str = 'ok',
    data: Any = None,
    cookies: dict | None = None,
) -> JSONResponse:
    resp = JSONResponse(
        {
            'status': status,
            'message': message,
            'data': data,
        },
        status_code=status_code,
    )
    return _apply_cookies(resp, cookies or {})


def HTTPRedirect(
    location: str,
    status_code: int = 302,
    cookies: dict | None = None,
) -> RedirectResponse:
    resp = RedirectResponse(location, status_code=status_code)
    return _apply_cookies(resp, cookies or {})


def HTTPError(
    message: str,
    status_code: int,
    data: Any = None,
    logout: bool = False,
) -> JSONResponse:
    cookies = {'piann': None, 'jwt': None} if logout else {}
    return HTTPResponse(message, status_code, 'err', data, cookies)
