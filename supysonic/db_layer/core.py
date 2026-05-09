from datetime import datetime
from hashlib import sha1
from uuid import uuid4

from peewee import CharField, DatabaseProxy, Model, MySQLDatabase, UUIDField, fn


def now():
    return datetime.now().replace(microsecond=0)


def random():
    if isinstance(db.obj, MySQLDatabase):
        return fn.rand()
    return fn.random()


def PrimaryKeyField(**kwargs):
    return UUIDField(primary_key=True, default=uuid4, **kwargs)


db = DatabaseProxy()


class _Model(Model):
    class Meta:
        database = db
        legacy_table_names = False


class Meta(_Model):
    key = CharField(32, primary_key=True)
    value = CharField(256)


class PathMixin:
    @classmethod
    def get(cls, *args, **kwargs):
        if kwargs:
            path = kwargs.pop("path", None)
            if path:
                kwargs["_path_hash"] = sha1(path.encode("utf-8")).digest()
        return _Model.get.__func__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        if "path" in kwargs:
            path = kwargs["path"]
            kwargs["_path_hash"] = sha1(path.encode("utf-8")).digest()
        _Model.__init__(self, *args, **kwargs)

    def __setattr__(self, attr, value):
        _Model.__setattr__(self, attr, value)
        if attr == "path":
            _Model.__setattr__(self, "_path_hash", sha1(value.encode("utf-8")).digest())
