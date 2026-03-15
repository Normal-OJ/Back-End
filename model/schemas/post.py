from typing import Optional
from .base import BaseSchema


class ModifyPostBody(BaseSchema):
    course: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    target_thread_id: Optional[str] = None
