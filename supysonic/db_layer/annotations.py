from peewee import CompositeKey, DateTimeField, ForeignKeyField, IntegerField

from .core import _Model, now
from .library import Album, Artist, Folder, Track
from .users import User


def _make_starred_model(target_model):
    class Starred(_Model):
        user = ForeignKeyField(User, backref="+")
        starred = ForeignKeyField(target_model, backref="+")
        date = DateTimeField(default=now)

        class Meta:
            primary_key = CompositeKey("user", "starred")
            table_name = "starred_" + target_model._meta.table_name

    return Starred


StarredFolder = _make_starred_model(Folder)
StarredArtist = _make_starred_model(Artist)
StarredAlbum = _make_starred_model(Album)
StarredTrack = _make_starred_model(Track)


def _make_rating_model(target_model):
    class Rating(_Model):
        user = ForeignKeyField(User, backref="+")
        rated = ForeignKeyField(target_model, backref="+")
        rating = IntegerField()  # min=1, max=5

        class Meta:
            primary_key = CompositeKey("user", "rated")
            table_name = "rating_" + target_model._meta.table_name

    return Rating


RatingFolder = _make_rating_model(Folder)
RatingTrack = _make_rating_model(Track)
