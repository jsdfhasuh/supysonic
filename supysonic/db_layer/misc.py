import time

from peewee import CharField, DateTimeField, ForeignKeyField, IntegerField

from .core import PrimaryKeyField, _Model, now
from .users import User


class ChatMessage(_Model):
    id = PrimaryKeyField()
    user = ForeignKeyField(User, backref="+")
    time = IntegerField(default=lambda: int(time.time()))
    message = CharField(512)

    def responsize(self):
        from .serializers import serialize_chat_message

        return serialize_chat_message(self)


class RadioStation(_Model):
    id = PrimaryKeyField()
    stream_url = CharField()
    name = CharField()
    homepage_url = CharField(null=True)
    created = DateTimeField(default=now)

    def as_subsonic_station(self):
        from .serializers import serialize_radio_station

        return serialize_radio_station(self)
