from tortoise.models import Model
from tortoise import fields

import uuid


class Subscriber(Model):
    telegram_id = fields.IntField(pk=True)
    name = fields.TextField()
    enabled = fields.BooleanField(default=True)
    updated_at = fields.DatetimeField(auto_now=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    def __str__(self):
        return (f"Subscriber(id={self.telegram_id}, "
                f"name={self.name}, enabled={self.enabled})")

    class Meta:
        table = "subscribers"


class HolidayCache(Model):
    id = fields.IntField(pk=True)
    name = fields.TextField()
    directory = fields.TextField(default=uuid.uuid4)
    images_count = fields.SmallIntField(default=0)
    accessed_at = fields.DatetimeField(auto_now_add=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "holiday_cache"


class ImageQuery(Model):
    id = fields.IntField(pk=True)
    query = fields.TextField()
    uuid = fields.UUIDField(default=uuid.uuid4)
    ready = fields.BooleanField(default=False)
    retries = fields.IntField(default=0)
    updated_at = fields.DatetimeField(auto_now=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "image_queries"
