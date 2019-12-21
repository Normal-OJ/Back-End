from . import course
from . import problem
from . import engine
from . import user

from .course import *
from .problem import *
from .engine import *
from .user import *

__all__ = [*course.__all__, *problem.__all__, *engine.__all__, *user.__all__]

if User("first_admin").obj is None:
    ADMIN = {
        'username': 'first_admin',
        'password': 'firstpasswordforadmin',
        'email': 'i.am.first.admin@noj.tw'
    }

    admin = User.signup(**ADMIN)
    admin.update(active=True, role=0)

if Course("Public").obj is None:
    add_course("Public", "first_admin")

if Number("serial_number").obj is None:
    engine.Number(name="serial_number", number=1).save()