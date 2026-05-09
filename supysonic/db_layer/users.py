from peewee import (
    BooleanField,
    CharField,
    CompositeKey,
    DateTimeField,
    FixedCharField,
    ForeignKeyField,
    IntegerField,
)

from .core import PrimaryKeyField, _Model, now
from .library import Track


class User(_Model):
    id = PrimaryKeyField()
    name = CharField(64, unique=True)
    mail = CharField(null=True)
    password = FixedCharField(40)
    salt = FixedCharField(6)

    admin = BooleanField(default=False)
    jukebox = BooleanField(default=False)

    lastfm_session = FixedCharField(32, null=True)
    lastfm_status = BooleanField(
        default=True
    )  # True: ok/unlinked, False: invalid session

    listenbrainz_session = FixedCharField(36, null=True)
    listenbrainz_status = BooleanField(
        default=True
    )  # True: ok/unlinked, False: invalid token

    last_play = ForeignKeyField(Track, null=True, backref="+")
    last_play_date = DateTimeField(null=True)

    def as_subsonic_user(self):
        from .serializers import serialize_user

        return serialize_user(self)


class User_Play_Activity(_Model):
    # record user play activity,every record is a play activity
    id = PrimaryKeyField()
    track = ForeignKeyField(Track, backref="play_activity_track")
    user = ForeignKeyField(User, backref="play_activity_user")
    time = DateTimeField(default=now)

    class Meta:
        table_name = "user_play_activity"


class ClientPrefs(_Model):
    user = ForeignKeyField(User, backref="clients")
    client_name = CharField(32)
    format = CharField(8, null=True)
    bitrate = IntegerField(null=True)

    class Meta:
        primary_key = CompositeKey("user", "client_name")
