from functools import wraps

from mongoengine.errors import *

__all__ = ['MongoBase']


class MongoBase:
    qs_filter = {}

    def __init_subclass__(cls, engine, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.engine = engine

    def __new__(cls, pk, *args, **kwargs):
        new = super().__new__(cls)
        new.obj = new.engine(pk=pk)
        return new.reload()

    def __getattr__(self, name):
        return self.obj.__getattribute__(name)

    def __setattr__(self, name, value):
        if name in self.engine._fields:
            self.obj.__setattr__(name, value)
        else:
            super().__setattr__(name, value)

    def __eq__(self, other):
        return self and self.pk == other.pk

    def __bool__(self):
        try:
            return self._qs.filter(pk=self.pk, **self.qs_filter).__bool__()
        except ValidationError:
            return False

    def __repr__(self):
        return self.obj.to_json() if self else '{}'

    def reload(self):
        if self:
            self.obj.reload()
        return self
