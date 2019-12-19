from . import course
from . import engine
from . import user
from . import submission
from . import homework

from .course import *
from .engine import *
from .user import *
from .submission import *
from .homework import *

__all__ = [
    *course.__all__, *engine.__all__, *user.__all__, *submission.__all__,
    *homework.__all__
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
