# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2024 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import mimetypes
import os.path
import time

import hashlib
from peewee import (
    AutoField,
    BlobField,
    BooleanField,
    CharField,
    DateTimeField,
    FixedCharField,
    ForeignKeyField,
    IntegerField,
    OperationalError,
    TextField,
)
from peewee import CompositeKey, MySQLDatabase
from peewee import fn
from uuid import UUID
from PIL import Image as PILImage
from .db_layer.core import (
    _Model,
    Meta,
    PathMixin,
    PrimaryKeyField,
    db,
    now,
    random,
)
from .tool import read_dict_from_json
from .db_layer.schema import (
    SCHEMA_VERSION,
    execute_sql_resource_script,
    get_resource_text,
    list_migrations,
)
from .db_layer.runtime import (
    close_connection,
    init_database,
    open_connection,
    release_database,
)
from .db_layer.emo import EmoLocalQueue, EmoPlaybackState, EmoSessionQueue
from .db_layer.client_releases import ClientRelease


class Image(_Model):
    """存储艺术家和专辑的图片"""

    id = AutoField()  # 改为自增整数ID
    path = CharField(4096)  # 文件路径
    # 关联类型：artist 或 album
    image_type = CharField(max_length=10)
    # 关联的ID（艺术家或专辑的字符串ID）
    related_id = CharField(max_length=36)
    # 创建时间
    created = DateTimeField(default=now)


class Folder(PathMixin, _Model):
    id = AutoField()
    root = BooleanField()
    name = CharField()
    path = CharField(4096)  # unique
    _path_hash = BlobField(column_name="path_hash", unique=True)
    created = DateTimeField(default=now)
    cover_art = CharField(null=True)
    last_scan = IntegerField(default=0)

    parent = ForeignKeyField("self", null=True, backref="children")

    def as_subsonic_child(self, user):
        from .db_layer.serializers import serialize_folder_child

        return serialize_folder_child(self, user)

    def as_subsonic_artist(self, user):  # "Artist" type in XSD
        from .db_layer.serializers import serialize_folder_artist

        return serialize_folder_artist(self, user)

    def as_subsonic_directory(self, user, client):  # "Directory" type in XSD
        from .db_layer.serializers import serialize_folder_directory

        return serialize_folder_directory(self, user, client)

    @classmethod
    def prune(cls):
        alias = cls.alias()
        query = cls.select(cls.id).where(
            ~cls.root,
            Track.select(fn.count("*")).where(Track.folder == cls.id) == 0,
            alias.select(fn.count("*")).where(alias.parent == cls.id) == 0,
        )
        total = 0
        while True:
            clone = query.clone()  # peewee caches the results, clone to force a refetch
            for f in clone:
                f.delete_instance(recursive=True)
                total += 1
            if not len(clone):
                return total

    def delete_hierarchy(self):
        if self.root:
            cond = Track.root_folder == self
        else:
            cond = Track.path.startswith(self.path)

        return self.__delete_hierarchy(cond)

    def __delete_hierarchy(self, cond):
        users = User.select(User.id).join(Track).where(cond)
        User.update(last_play=None).where(User.id.in_(users)).execute()

        tracks = Track.select(Track.id).where(cond)
        RatingTrack.delete().where(RatingTrack.rated.in_(tracks)).execute()
        StarredTrack.delete().where(StarredTrack.starred.in_(tracks)).execute()

        path_cond = Folder.path.startswith(self.path)
        folders = Folder.select(Folder.id).where(path_cond)
        RatingFolder.delete().where(RatingFolder.rated.in_(folders)).execute()
        StarredFolder.delete().where(StarredFolder.starred.in_(folders)).execute()

        deleted_tracks = Track.delete().where(cond).execute()

        # 修改代码，确保所有子文件夹中的 Track 都被删除
        # 获取所有相关的 folder_id
        folder_ids = [f.id for f in Folder.select(Folder.id).where(path_cond)]

        # 确保删除这些文件夹中的所有 Track
        Track.delete().where(Track.folder_id.in_(folder_ids)).execute()

        # 然后再删除文件夹
        query = Folder.delete().where(path_cond)
        if isinstance(db.obj, MySQLDatabase):
            query = query.order_by(Folder.path.desc())
        query.execute()

        return deleted_tracks


class Artist(_Model):
    id = PrimaryKeyField()
    name = CharField()
    artist_info_json = CharField(4096, null=True)
    # 指向一个整理好的艺术家名字（例如别名指向主艺术家）
    real_artist = ForeignKeyField(
        "self", null=True, backref="aliases", on_delete="SET NULL"
    )

    def get_artist_name(self):
        if self.real_artist:
            return self.real_artist.name
        return self.name

    # 更精确的 as_subsonic_artist 方法 返回艺术家信息字典
    def as_subsonic_artist(self, user):
        from .db_layer.serializers import serialize_artist

        return serialize_artist(self, user)

    def get_info(self):
        info = {
            "biography": "",
            "musicBrainzId": "",
            "lastFmUrl": "",
            "smallImageUrl": "",
            "mediumImageUrl": "",
            "largeImageUrl": "",
        }
        if self.artist_info_json:
            try:
                local_data = read_dict_from_json(self.artist_info_json)
                image_data = local_data.get("image")
                if not isinstance(image_data, dict):
                    image_data = {}
                info["biography"] = local_data.get("biography", "")
                info["musicBrainzId"] = local_data.get("musicBrainzId", "")
                info["lastFmUrl"] = local_data.get("lastFmUrl", "")
                info["smallImageUrl"] = image_data.get("small", "")
                info["mediumImageUrl"] = image_data.get("medium", "")
                info["largeImageUrl"] = image_data.get("large", "")
                return info
            except ValueError:
                return info
        info['cover_art'] = "ar-" + str(self.id)
        return info

    # 更新 Artist 类的 prune 方法
    @classmethod
    def prune(cls):
        # 获取所有被引用的艺术家ID
        album_artists = Album.select(Album.artist)
        track_artists = Track.select(Track.artist)
        album_multi_artists = AlbumArtist.select(AlbumArtist.artist_id)
        track_multi_artists = TrackArtist.select(TrackArtist.artist_id)
        # 删除指向不再被引用艺术家的收藏标记
        StarredArtist.delete().where(
            StarredArtist.starred.not_in(album_artists),
            StarredArtist.starred.not_in(track_artists),
            StarredArtist.starred.not_in(album_multi_artists),
            StarredArtist.starred.not_in(track_multi_artists),  # 添加这一行
        ).execute()

        # 删除不再被引用的艺术家记录
        return (
            cls.delete()
            .where(cls.real_artist.is_null())
            .where(
                cls.id.not_in(album_artists),
                cls.id.not_in(track_artists),
                cls.id.not_in(album_multi_artists),
            )
            .execute()
        )


class Album(_Model):
    id = PrimaryKeyField()
    name = CharField()
    artist = ForeignKeyField(Artist, backref="albums")
    year = CharField(default=None, null=True)  # 专辑年份
    release_date = CharField(max_length=32, null=True)
    release_type = CharField(max_length=64, null=True)
    album_info_json = TextField(null=True)

    # 在 Album 类中添加获取艺术家的方法

    def get_all_artists(self):
        """获取专辑的所有艺术家（包括主艺术家和其他艺术家）

        Returns:
            所有艺术家列表，按位置排序
        """
        # 查询 AlbumArtist 表中与当前专辑相关的所有记录
        artist_relations = self.album_artists.order_by(AlbumArtist.position)

        # 从关系中提取艺术家对象
        try:
            artists = [rel.artist_id for rel in artist_relations]
        except OperationalError as exc:
            if "album_artist" not in str(exc):
                raise
            artists = []

        return artists or [self.artist]

    def as_subsonic_album(self, user, server_type=None):  # "AlbumID3" type in XSD
        from .db_layer.serializers import serialize_album

        return serialize_album(self, user, server_type)

    def sort_key(self):
        year = self.tracks.select(fn.min(Track.year)).scalar() or 9999
        return f"{year}{self.name.lower()}"

    @classmethod
    def prune(cls):
        albums = Track.select(Track.album)
        StarredAlbum.delete().where(StarredAlbum.starred.not_in(albums)).execute()
        AlbumArtist.delete().where(AlbumArtist.album_id.not_in(albums)).execute()
        return cls.delete().where(cls.id.not_in(albums)).execute()


class ReviewTask(_Model):
    id = PrimaryKeyField()
    entity_type = CharField(max_length=32)
    entity_id = CharField(max_length=36)
    task_type = CharField(max_length=64)
    status = CharField(max_length=32)
    reason = CharField(max_length=64)
    pending_key = CharField(max_length=96, null=True)
    snapshot_json = TextField(null=True)
    created = DateTimeField(default=now)
    updated = DateTimeField(default=now)
    resolved_at = DateTimeField(null=True)
    expires_at = DateTimeField(null=True)

    def is_album_task(self):
        return self.entity_type == "album"

    def is_artist_task(self):
        return self.entity_type == "artist"

    def get_album(self):
        if not self.is_album_task():
            return None
        return Album.get_or_none(Album.id == self.entity_id)

    def get_artist(self):
        if not self.is_artist_task():
            return None
        return Artist.get_or_none(Artist.id == self.entity_id)

    @property
    def album(self):
        return self.get_album()

    @album.setter
    def album(self, value):
        self.entity_type = "album"
        self.entity_id = str(getattr(value, "id", value))

    @property
    def artist(self):
        return self.get_artist()

    @artist.setter
    def artist(self, value):
        self.entity_type = "artist"
        self.entity_id = str(getattr(value, "id", value))

    @property
    def album_id(self):
        if not self.is_album_task():
            return None
        return UUID(self.entity_id)

    @property
    def artist_id(self):
        if not self.is_artist_task():
            return None
        return UUID(self.entity_id)

    def save(self, *args, **kwargs):
        if self.status == "pending" and self.entity_type and self.entity_id:
            if self.entity_type == "artist":
                self.pending_key = f"artist:{self.entity_id}:pending:{self.reason}"
            elif self.reason == "external_enrichment":
                self.pending_key = f"{self.entity_type}:{self.entity_id}:pending:{self.reason}"
            else:
                self.pending_key = f"{self.entity_type}:{self.entity_id}:pending"
        elif self.status != "pending":
            self.pending_key = None
        return super().save(*args, **kwargs)

    class Meta:
        table_name = "review_task"
        indexes = (
            (("entity_type", "entity_id", "status"), False),
            (("status", "created"), False),
            (("pending_key",), True),
        )


AlbumReviewTask = ReviewTask


class AlbumArtist(_Model):
    """专辑与艺术家的多对多关系表"""

    id = AutoField()
    album_id = ForeignKeyField(Album, backref="album_artists", column_name="album_id")
    artist_id = ForeignKeyField(
        Artist, backref="artist_albums", column_name="artist_id"
    )
    position = IntegerField(default=0)  # 用于排序，主艺术家为1，其他递增,0为还没确定

    class Meta:
        table_name = 'album_artist'
        indexes = (
            # 确保 album-artist 组合唯一
            (('album', 'artist'), True),
        )


class Track(PathMixin, _Model):
    # 在代码里面有递归删除
    id = PrimaryKeyField()
    disc = IntegerField()
    number = IntegerField()
    title = CharField()
    year = IntegerField(null=True)
    genre = CharField(null=True)
    duration = IntegerField()
    has_art = BooleanField(default=False)

    album = ForeignKeyField(Album, backref="tracks")
    artist = ForeignKeyField(Artist, backref="tracks")

    bitrate = IntegerField()

    path = CharField(4096)  # unique
    _path_hash = BlobField(column_name="path_hash", unique=True)
    created = DateTimeField(default=now)
    last_modification = IntegerField()

    play_count = IntegerField(default=0)
    play_count_web = IntegerField(default=0)
    last_play = DateTimeField(null=True)

    root_folder = ForeignKeyField(Folder, backref="+")
    folder = ForeignKeyField(Folder, backref="tracks")

    def as_subsonic_child(self, user, prefs):
        from .db_layer.serializers import serialize_track_child

        return serialize_track_child(self, user, prefs)

    @property
    def mimetype(self):
        return mimetypes.guess_type(self.path, False)[0] or "application/octet-stream"

    def duration_str(self):
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        ret = f"{m:02}:{s:02}"
        if h:
            ret = f"{h:02}:{ret}"
        return ret

    def suffix(self):
        return os.path.splitext(self.path)[1][1:].lower()

    def sort_key(self):
        return f"{self.album.artist.get_artist_name()}{self.album.name}{self.disc:02}{self.number:02}{self.title}".lower()


class TrackArtist(_Model):
    """曲目与艺术家的多对多关系表"""

    id = AutoField()
    track_id = ForeignKeyField(Track, backref="track_artists")
    artist_id = ForeignKeyField(Artist, backref="artist_tracks")
    position = IntegerField(default=0)  # 用于排序，主艺术家为1，其他递增，0为还没确定

    class Meta:
        table_name = 'track_artist'
        indexes = (
            # 确保 track-artist 组合唯一
            (('track', 'artist'), True),
        )


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
        from .db_layer.serializers import serialize_user

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


class ChatMessage(_Model):
    id = PrimaryKeyField()
    user = ForeignKeyField(User, backref="+")
    time = IntegerField(default=lambda: int(time.time()))
    message = CharField(512)

    def responsize(self):
        from .db_layer.serializers import serialize_chat_message

        return serialize_chat_message(self)


class Playlist(_Model):
    id = PrimaryKeyField()
    user = ForeignKeyField(User, backref="playlists")
    name = CharField()
    comment = CharField(null=True)
    public = BooleanField(default=False)
    created = DateTimeField(default=now)
    tracks = TextField(null=True)

    def as_subsonic_playlist(self, user, tracks=None):
        from .db_layer.serializers import serialize_playlist

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


class RadioStation(_Model):
    id = PrimaryKeyField()
    stream_url = CharField()
    name = CharField()
    homepage_url = CharField(null=True)
    created = DateTimeField(default=now)

    def as_subsonic_station(self):
        from .db_layer.serializers import serialize_radio_station

        return serialize_radio_station(self)
