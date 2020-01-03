from functools import wraps

from flask import request

from .response import HTTPError
from model import *
from .response import *

__all__ = ['Request']

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
                        return HTTPError(
                            f'Unaccepted Content-Type {content_type}', 415)
                    try:
                        # Magic
                        kwargs.update({
                            k: (lambda v: v
                                if t is None or type(v) is t else int(''))(
                                    data.get((lambda s, *t: s + ''.join(
                                        map(str.capitalize, t))
                                              )(*filter(bool, k.split('_')))))
                            for k, t in [(
                                lambda x: (x[0], type_map.get(x[1].strip()) if
                                           x[1:] else None))(l.split(':', 1))
                                         for l in keys]
                        })
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
    pass
