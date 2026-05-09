from peewee import CharField, DateTimeField, IntegerField, TextField

from .core import PrimaryKeyField, _Model, now


class EmoSessionQueue(_Model):
    id = PrimaryKeyField()
    session_id = CharField(128, unique=True)
    user_name = CharField(64)
    owner_client_id = CharField(128)
    queue_json = TextField()
    current_index = IntegerField(default=0)
    position_ms = IntegerField(default=0)
    version = IntegerField(default=1)
    created_at = DateTimeField(default=now)
    updated_at = DateTimeField(default=now)


class EmoLocalQueue(_Model):
    id = PrimaryKeyField()
    session_id = CharField(128)
    owner_client_id = CharField(128)
    queue_json = TextField()
    current_index = IntegerField(default=0)
    position_ms = IntegerField(default=0)
    created_at = DateTimeField(default=now)
    updated_at = DateTimeField(default=now)

    class Meta:
        indexes = ((('session_id', 'owner_client_id'), True),)


class EmoPlaybackState(_Model):
    id = PrimaryKeyField()
    session_id = CharField(128)
    user_name = CharField(64)
    owner_client_id = CharField(128)
    state = CharField(32)
    track_id = CharField(128, null=True)
    position_ms = IntegerField(default=0)
    volume = IntegerField(null=True)
    playback_json = TextField(null=True)
    created_at = DateTimeField(default=now)
    updated_at = DateTimeField(default=now)

    class Meta:
        indexes = ((('session_id', 'owner_client_id'), True),)
