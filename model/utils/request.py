from flask import request
from functools import wraps

from .response import HTTPError


class _Request(type):
    def __getattr__(self, content_type):
        def get(keys=[], vars_dict={}):
            def data_func(func):
                @wraps(func)
                def wrapper(*args, **kwargs):
                    data = getattr(request, content_type)
                    if data == None:
                        return HTTPError('Unaccepted Content-Type.', 415)
                    kwargs.update({k: data.get(change_style(k)) for k in keys})
                    kwargs.update(
                        {v: data.get(vars_dict[v])
                         for v in vars_dict})
                    return func(*args, **kwargs)

                return wrapper

            return data_func

        return get


class Request(metaclass=_Request):
    pass


def change_style(name):
    '''Change naming style from snake_case to camelCase
    '''
    new_name = ''
    i = 0
    while i < len(name):
        if name[i] == '_' and i + 1 < len(name) and name[i + 1].isalpha():
            new_name += name[i + 1].upper()
            i += 1
        else:
            new_name += name[i]

        i += 1

    return new_name


print(change_style('he_is_a_noob'))
