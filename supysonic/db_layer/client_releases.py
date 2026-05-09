from peewee import BooleanField, CharField, DateTimeField, IntegerField, TextField

from .core import PrimaryKeyField, _Model, now


class ClientRelease(_Model):
    id = PrimaryKeyField()
    platform = CharField(max_length=16)
    file_type = CharField(max_length=16)
    build_name = CharField(max_length=64)
    build_number = IntegerField()
    version = CharField(max_length=80)
    publish_mode = CharField(max_length=16)
    file_name = CharField(max_length=256, null=True)
    file_path = CharField(max_length=4096, null=True)
    download_url = CharField(max_length=2048, null=True)
    file_size = IntegerField(null=True)
    sha256 = CharField(max_length=64, null=True)
    release_notes = TextField(null=True)
    active = BooleanField(default=True)
    created = DateTimeField(default=now)
    updated = DateTimeField(default=now)

    def save(self, *args, **kwargs):
        self.updated = now()
        return super().save(*args, **kwargs)

    class Meta:
        table_name = "client_release"
        indexes = (
            (("platform", "build_name", "build_number"), True),
            (("platform", "active"), False),
        )
