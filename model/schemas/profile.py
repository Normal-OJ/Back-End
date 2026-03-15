from typing import Any, Optional
from .base import BaseSchema


class EditProfileBody(BaseSchema):
    bio: Optional[str] = None
    displayed_name: Optional[str] = None


class EditConfigBody(BaseSchema):
    font_size: Optional[Any] = None
    theme: Optional[Any] = None
    indent_type: Optional[Any] = None
    tab_size: Optional[Any] = None
    language: Optional[Any] = None
