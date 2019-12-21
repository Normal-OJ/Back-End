from . import engine
from . import user
from . import problem
from . import submission
from . import inbox
from . import course
from . import homework

from .engine import *
from .user import *
from .problem import *
from .submission import *
from .inbox import *
from .course import *
from .homework import *

__all__ = [
    *engine.__all__, *user.__all__, *problem.__all__, *submission.__all__,
    *inbox.__all__, *course.__all__, *homework.__all__
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