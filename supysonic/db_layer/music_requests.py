import json
from typing import Any, Iterable, List

from peewee import CharField, DateTimeField, ForeignKeyField, TextField

from .core import PrimaryKeyField, _Model, now
from .users import User


class MusicRequest(_Model):
    STATUS_PENDING = "pending"
    STATUS_RESOLVED = "resolved"
    STATUS_REJECTED = "rejected"
    STATUSES = (STATUS_PENDING, STATUS_RESOLVED, STATUS_REJECTED)

    id = PrimaryKeyField()
    user = ForeignKeyField(User, backref="music_requests")
    artist_name = CharField(max_length=256)
    album_name = CharField(max_length=256, null=True)
    tracks_json = TextField(null=True)
    note = TextField(null=True)
    status = CharField(max_length=32, default=STATUS_PENDING)
    status_note = TextField(null=True)
    created_at = DateTimeField(default=now)
    updated_at = DateTimeField(default=now)
    resolved_at = DateTimeField(null=True)

    def get_track_titles(self) -> List[str]:
        if not self.tracks_json:
            return []
        try:
            tracks = json.loads(self.tracks_json)
        except ValueError:
            return []
        if not isinstance(tracks, list):
            return []
        return [str(track).strip() for track in tracks if str(track).strip()]

    def set_track_titles(self, tracks: Iterable[object]) -> None:
        clean_tracks = [str(track).strip() for track in tracks if str(track).strip()]
        self.tracks_json = json.dumps(clean_tracks) if clean_tracks else None

    def save(self, *args: Any, **kwargs: Any) -> int:
        self.updated_at = now()
        if self.status == self.STATUS_PENDING:
            self.resolved_at = None
        elif self.resolved_at is None:
            self.resolved_at = now()
        return super().save(*args, **kwargs)

    class Meta:
        table_name = "music_request"
        indexes = (
            (("status", "created_at"), False),
            (("user", "created_at"), False),
            (("artist_name", "album_name", "status"), False),
        )
