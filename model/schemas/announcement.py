from typing import Optional
from .base import BaseSchema


class CreateAnnouncementBody(BaseSchema):
    title: Optional[str] = None
    markdown: Optional[str] = None
    course_name: Optional[str] = None
    pinned: Optional[bool] = None


class UpdateAnnouncementBody(BaseSchema):
    ann_id: Optional[str] = None
    title: Optional[str] = None
    markdown: Optional[str] = None
    pinned: Optional[bool] = None


class DeleteAnnouncementBody(BaseSchema):
    ann_id: Optional[str] = None
