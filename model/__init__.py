from . import auth
from . import course
from . import profile
from . import submission
from . import test

from .auth import *
from .course import *
from .profile import *
from .submission import *
from .test import *

__all__ = [
    *auth.__all__, *course.__all__, *profile.__all__, *submission.__all__,
    *test.__all__
]
