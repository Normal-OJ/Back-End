from functools import wraps

from flask import request

from model import *
from .response import *

__all__ = ['Request']


class _Request(type):
    def __getattr__(self, content_type):
        def get(*keys, vars_dict={}):
            def data_func(func):
                @wraps(func)
                def wrapper(*args, **kwargs):
                    data = getattr(request, content_type)
                    if data == None:
                        return HTTPError('Unaccepted Content-Type', 415)
                    # Magic
                    kwargs.update({
                        k: data.get(
                            (lambda s, *t: s + ''.join(map(str.capitalize, t))
                             )(*filter(bool, k.split('_'))))
                        for k in keys
                    })
                    kwargs.update(
                        {v: data.get(vars_dict[v])
                         for v in vars_dict})
                    return func(*args, **kwargs)

                return wrapper

            return data_func

        return get


class Request(metaclass=_Request):
    pass
