from . import auth
from . import course
from . import profile
from . import submission
from . import test
from . import homework
from . import announcement

from .auth import *
from .course import *
from .profile import *
from .submission import *
from .test import *
from .homework import *
from .announcement import *

__all__ = [
    *auth.__all__, *course.__all__, *profile.__all__, *submission.__all__,
    *test.__all__, *homework.__all__, *announcement.__all__
]
