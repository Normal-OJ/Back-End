from . import course
from . import engine
from . import user
from . import submission
from . import homework
from . import inbox
from . import problem
from . import announcement
from . import post

from .course import *
from .engine import *
from .user import *
from .submission import *
from .homework import *
from .inbox import *
from .problem import *
from .announcement import *
from .post import *

__all__ = [
    *course.__all__, *engine.__all__, *user.__all__, *submission.__all__,
    *homework.__all__, *inbox.__all__, *problem.__all__, *announcement.__all__,
    *post.__all__
]

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
