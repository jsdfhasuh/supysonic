from uuid import UUID

from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    TextField,
)

from .core import PrimaryKeyField, _Model, now
from .library import Track
from .users import User


class Playlist(_Model):
    id = PrimaryKeyField()
    user = ForeignKeyField(User, backref="playlists")
    name = CharField()
    comment = CharField(null=True)
    public = BooleanField(default=False)
    created = DateTimeField(default=now)
    tracks = TextField(null=True)

    def as_subsonic_playlist(self, user, tracks=None):
        from .serializers import serialize_playlist

        return serialize_playlist(self, user, tracks)

    def get_tracks(self):
        if not self.tracks:
            return []

        tracks = []
        should_fix = False

        for t in self.tracks.split(","):
            try:
                tid = UUID(t)
                track = Track[tid]
                tracks.append(track)
            except (ValueError, Track.DoesNotExist):
                should_fix = True

        if should_fix:
            self.tracks = ",".join(str(t.id) for t in tracks)
            self.save()

        return tracks

    def clear(self):
        self.tracks = ""

    def add(self, track):
        if isinstance(track, UUID):
            tid = track
        elif isinstance(track, Track):
            tid = track.id
        elif isinstance(track, str):
            tid = UUID(track)
        if self.tracks and len(self.tracks) > 0:
            self.tracks = f"{self.tracks},{tid}"
        else:
            self.tracks = str(tid)

    def remove_at_indexes(self, indexes):
        tracks = self.tracks.split(",")
        for i in indexes:
            if i < 0 or i >= len(tracks):
                continue
            tracks[i] = None

        self.tracks = ",".join(t for t in tracks if t)


class SharedTrackLink(_Model):
    id = PrimaryKeyField()
    token = CharField(96, unique=True)
    track = ForeignKeyField(Track, backref="shared_links")
    created_by = ForeignKeyField(User, backref="shared_track_links")
    enabled = BooleanField(default=True)
    created_at = DateTimeField(default=now)
