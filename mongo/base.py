from functools import wraps
from . import engine
from mongoengine.errors import *

__all__ = ['MongoBase']


class MongoBase:
    qs_filter = {}

    def __init_subclass__(cls, engine, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.engine = engine

    def __new__(cls, pk, *args, **kwargs):
        new = super().__new__(cls)
        try:
            new.obj = new.engine.objects(pk=pk).get()
        except engine.DoesNotExist:
            new.obj = new.engine(pk=pk)
        return new

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

    def __str__(self):
        return f'{self.__class__.__name__.lower()} [{self.pk}]'

    def __repr__(self):
        return self.obj.to_json() if self else '{}'

    def reload(self):
        if self:
            self.obj.reload()
        return self
