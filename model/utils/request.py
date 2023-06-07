import time
import json
from functools import wraps
from flask import request, current_app
from mongo import engine
from mongo.utils import doc_required
from .response import *

__all__ = (
    'Request',
    'get_ip',
)

type_map = {
    'int': int,
    'list': list,
    'str': str,
    'dict': dict,
    'bool': bool,
    'None': type(None)
}


class _Request(type):

    def __getattr__(self, content_type):

        def get(*keys, vars_dict={}):

            def data_func(func):

                @wraps(func)
                def wrapper(*args, **kwargs):
                    data = getattr(request, content_type)
                    if data == None:
                        # FIXME: This exception doesn't mean the content type is wrong
                        return HTTPError(
                            f'Unaccepted Content-Type {content_type}', 415)
                    try:
                        # Magic
                        # yapf: disable
                        kwargs.update({
                            k: (lambda v: v
                                if t is None or type(v) is t else int(''))(
                                    data.get((lambda s, *t: s + ''.join(
                                        map(str.capitalize, t))
                                              )(*filter(bool, k.split('_')))))
                            for k, t in map(
                                lambda x:
                                (x[0], (x[1:] or None) and type_map.get(x[1].strip())),
                                map(lambda q: q.split(':', 1), keys))
                        })
                        # yapf: enable
                    except ValueError as ve:
                        return HTTPError('Requested Value With Wrong Type',
                                         400)
                    kwargs.update(
                        {v: data.get(vars_dict[v])
                         for v in vars_dict})
                    return func(*args, **kwargs)

                return wrapper

            return data_func

        return get


class Request(metaclass=_Request):

    @staticmethod
    def doc(src, des, cls=None, src_none_allowed=False):
        '''
        a warpper to `doc_required` for flask route
        '''

        def deco(func):

            @doc_required(src, des, cls, src_none_allowed)
            def inner_wrapper(*args, **ks):
                return func(*args, **ks)

            @wraps(func)
            def real_wrapper(*args, **ks):
                try:
                    return inner_wrapper(*args, **ks)
                # if document not exists in db
                except engine.DoesNotExist as e:
                    return HTTPError(str(e), 404)
                # if args missing
                except TypeError as e:
                    return HTTPError(str(e), 500)
                except engine.ValidationError as e:
                    current_app.logger.info(
                        f'Validation error [err={e.to_dict()}]')
                    return HTTPError('Invalid parameter', 400)

            return real_wrapper

        return deco


def get_ip() -> str:
    ip = request.headers.get('X-Forwarded-For', '').split(',')[-1].strip()
    return ip
