import inspect
import httpx
from fastapi import Depends, Request
from mongo import engine
from .response import NOJException

__all__ = ('get_doc', 'get_ip', 'get_http_client')


def get_doc(src_param: str, cls, param_type=str):
    """
    Depends factory: resolves a MongoEngine document from a path/query parameter.

    Usage:
        @router.get('/{username}')
        def handler(target_user = get_doc('username', User)): ...

        @router.get('/{problem_id}')
        def handler(problem = get_doc('problem_id', Problem, int)): ...
    """

    def dependency(**kwargs):
        val = kwargs[src_param]
        try:
            doc = cls(val)
            if not doc:
                raise engine.DoesNotExist(f'{cls.__name__} not found')
            return doc
        except engine.DoesNotExist as e:
            raise NOJException(str(e), 404)
        except engine.ValidationError:
            raise NOJException('Invalid parameter', 400)

    # Give the function a proper named signature so FastAPI can inject the path param
    param = inspect.Parameter(
        src_param,
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=param_type,
    )
    dependency.__signature__ = inspect.Signature([param])
    dependency.__annotations__ = {src_param: param_type}
    return Depends(dependency)


def get_http_client(request: Request) -> httpx.Client:
    return request.app.state.http_client


def get_ip(request: Request) -> str:
    # cf-connecting-ip is set by Cloudflare and is more reliable than X-Forwarded-For
    cf_ip = request.headers.get('cf-connecting-ip', '').strip()
    if cf_ip:
        return cf_ip
    forwarded_for = request.headers.get('X-Forwarded-For',
                                        '').split(',')[-1].strip()
    if forwarded_for:
        return forwarded_for
    return request.client.host if request.client else ''
