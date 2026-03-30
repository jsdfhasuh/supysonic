# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2023 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import logging
import os
import os.path
import mediafile
import time
from peewee import IntegrityError

from datetime import datetime
from queue import Queue, Empty as QueueEmpty
from threading import Thread, Event
from flask import current_app
from .config import IniConfig
from .scanner_func import (
    buildTrackData,
    createOrUpdateTrack,
    findLostInformation,
    getScanTargetInfo,
    loadTrackForScan,
    resolveAlbumContext,
    resolveTrackArtists,
)
from .lastfm import LastFm
from .spotify import MySpotify
from .MusicBrainz import (
    get_musicbrainz_album_image_info,
    get_musicbrainz_album,
    search_musicbrainz_album,
)
from .covers import find_cover_in_folder, CoverFile
from .db import (
    User,
    Folder,
    Artist,
    Album,
    Track,
    open_connection,
    close_connection,
    AlbumArtist,
    Image,
    TrackArtist,
)
from .tool import (
    download_image,
    read_dict_from_json,
    write_dict_to_json,
    extract_year,
    get_file_md5,
)
from .nfo.nfo import NfoHandler

logger = logging.getLogger(__name__)


class StatsDetails:
    def __init__(self):
        self.artists = 0
        self.albums = 0
        self.tracks = 0


class Stats:
    def __init__(self):
        self.scanned = 0
        self.existing_tracks = 0
        self.added = StatsDetails()
        self.deleted = StatsDetails()
        self.errors = []
        self.lost_covers = StatsDetails()
        self.lost_covers_albums = {}
        self.lost_covers_artists = []
        self.lost_year_albums = {}


class ScanQueue(Queue):
    def _init(self, maxsize):
        self.queue = set()
        self.__last_got = None

    def _put(self, item):
        if self.__last_got != item:
            self.queue.add(item)

    def _get(self):
        self.__last_got = self.queue.pop()
        return self.__last_got


class Scanner(Thread):
    def __init__(
        self,
        force=False,
        extensions=None,
        follow_symlinks=False,
        progress=None,
        on_folder_start=None,
        on_folder_end=None,
        on_done=None,
    ):
        super().__init__()

        if extensions is not None and not isinstance(extensions, list):
            raise TypeError("Invalid extensions type")

        self.__force = force
        self.__extensions = extensions
        self.__follow_symlinks = follow_symlinks

        self.__progress = progress
        self.__on_folder_start = on_folder_start
        self.__on_folder_end = on_folder_end
        self.__on_done = on_done

        self.__stopped = Event()
        self.__queue = ScanQueue()
        self.__stats = Stats()
        self.__config = IniConfig.from_common_locations()

    scanned = property(lambda self: self.__stats.scanned)

    def __report_progress(self, folder_name, scanned):
        if self.__progress is None:
            return

        self.__progress(folder_name, scanned)

    def queue_folder(self, folder_name):
        if not isinstance(folder_name, str):
            raise TypeError("Expecting string, got " + str(type(folder_name)))

        self.__queue.put(folder_name)

    def run(self):
        opened = open_connection(True)
        while not self.__stopped.is_set():
            try:
                folder_name = self.__queue.get(False)
            except QueueEmpty:
                break

            try:
                folder = Folder.get(name=folder_name, root=True)
            except Folder.DoesNotExist:
                continue

            self.__scan_folder(folder)

        self.dicede_all_positions()
        self.prune()
        logger.info('begin to find all covers')
        self.find_lost_information()
        if self.__on_done is not None:
            self.__on_done()

        if opened:
            close_connection()

    def stop(self):
        self.__stopped.set()

    def __scan_folder(self, folder):
        logger.info("Scanning folder %s", folder.name)

        if self.__on_folder_start is not None:
            self.__on_folder_start(folder)

        # Scan new/updated files
        to_scan = [folder.path]
        scanned = 0
        while not self.__stopped.is_set() and to_scan:
            path = to_scan.pop()
            for entry in os.scandir(path):
                if entry.name.startswith("."):
                    continue
                if entry.is_symlink() and not self.__follow_symlinks:
                    continue
                elif entry.is_dir():
                    to_scan.append(entry.path)
                elif entry.is_file() and self.__check_extension(entry.path):
                    self.scan_file(entry)
                    self.__stats.scanned += 1
                    scanned += 1

                    self.__report_progress(folder.name, scanned)

        # Remove deleted/moved folders
        folders = [folder]
        while not self.__stopped.is_set() and folders:
            f = folders.pop()

            if not f.root and not os.path.isdir(f.path):
                self.__stats.deleted.tracks += f.delete_hierarchy()
                continue

            folders += f.children[:]

        # Remove files that have been deleted
        # Could be more efficient if done when walking on the files
        if not self.__stopped.is_set():
            for track in Track.select().where(Track.root_folder == folder):
                if not os.path.exists(track.path) or not self.__check_extension(
                    track.path
                ):
                    self.remove_file(track.path)

        # Update cover art info
        folders = [folder]
        while not self.__stopped.is_set() and folders:
            f = folders.pop()
            self.find_cover(f.path)
            folders += f.children[:]

        if not self.__stopped.is_set():
            folder.last_scan = int(time.time())
            folder.save()

        if self.__on_folder_end is not None:
            self.__on_folder_end(folder)

    def prune(self):
        if self.__stopped.is_set():
            return

        self.__stats.deleted.albums += Album.prune()
        self.__stats.deleted.artists += Artist.prune()
        Folder.prune()

    def __check_extension(self, path):
        if not self.__extensions:
            return True
        return os.path.splitext(path)[1][1:].lower() in self.__extensions

    def __read_nfo(self, nfo_path):
        if os.path.exists(nfo_path):
            nfo_data = NfoHandler.read(nfo_path)
            # change artist to list
            if 'album' in nfo_data:
                if 'artist' in nfo_data['album']:
                    temp = nfo_data['album']['artist'].split(",")
                    nfo_data['album']['artist'] = temp
                else:
                    nfo_data['album']['artist'] = []
                if 'albumartist' in nfo_data['album']:
                    temp = nfo_data['album']['albumartist'].split(",")
                    nfo_data['album']['albumartist'] = temp
                if isinstance(nfo_data['album'].get('track', []), list):
                    for track in nfo_data['album']['track']:
                        if 'artist' in track:
                            temp = track['artist'].split(",")
                            track['artist'] = temp
                        else:
                            track['artist'] = []
                else:

                    if 'artist' in nfo_data['album']['track']:
                        temp = nfo_data['album']['track']['artist'].split(",")
                        nfo_data['album']['track']['artist'] = temp
                    temp = []
                    temp.append(nfo_data['album']['track'])
                    nfo_data['album']['track'] = temp

            else:
                if 'artist' in nfo_data:
                    temp = nfo_data['artist'].split(",")
                    nfo_data['artist'] = temp
                else:
                    nfo_data['artist'] = []
                if 'albumartist' in nfo_data:
                    temp = nfo_data['albumartist'].split(",")
                    nfo_data['albumartist'] = temp
                for track in nfo_data['track']:
                    temp = []
                    if 'artist' in track:
                        temp = track['artist'].split(",")
                        track['artist'] = temp
                    else:
                        track['artist'] = []

        else:
            nfo_data = {}
        return nfo_data

    def __get_scan_target_info(self, path_or_direntry):
        return getScanTargetInfo(path_or_direntry)

    def __load_track_for_scan(self, path, mtime):
        return loadTrackForScan(self, path, mtime)

    def __resolve_album_context(self, path, tag):
        return resolveAlbumContext(self, path, tag)

    def __build_track_data(self, basename, mtime, tag):
        return buildTrackData(self, basename, mtime, tag)

    def __resolve_track_artists(self, nfo_data, track_data, fallback_artists):
        return resolveTrackArtists(self, nfo_data, track_data, fallback_artists)

    def __create_or_update_track(self, track, path, mtime, track_data, album, artist):
        return createOrUpdateTrack(self, track, path, mtime, track_data, album, artist)

    def scan_file(self, path_or_direntry):
        target = self.__get_scan_target_info(path_or_direntry)
        if target is None:
            return

        path = target.path
        basename = target.basename
        stat = target.stat

        try:
            path.encode("utf-8")  # Test for badly encoded paths
        except UnicodeError:
            self.__stats.errors.append(path)
            return

        mtime = int(stat.st_mtime)
        if os.path.isfile(path) and '.flac' in path.lower():
            pass
            self.__stats.existing_tracks += 1
        track, tag, track_data = self.__load_track_for_scan(path, mtime)
        if tag is None:
            return

        nfo_data, artists, album_id = self.__resolve_album_context(path, tag)
        track_data.update(self.__build_track_data(basename, mtime, tag))
        track_artists, track_artist = self.__resolve_track_artists(
            nfo_data, track_data, artists
        )
        track = self.__create_or_update_track(
            track, path, mtime, track_data, album_id, track_artist
        )
        if track is None:
            return
        self._record_track_artists(track_artists, track)

    def remove_file(self, path):
        if not isinstance(path, str):
            raise TypeError("Expecting string, got " + str(type(path)))

        try:
            Track.get(path=path).delete_instance(recursive=True)
            self.__stats.deleted.tracks += 1
        except Track.DoesNotExist:
            pass

    def move_file(self, src_path, dst_path):
        if not isinstance(src_path, str):
            raise TypeError("Expecting string, got " + str(type(src_path)))
        if not isinstance(dst_path, str):
            raise TypeError("Expecting string, got " + str(type(dst_path)))

        if src_path == dst_path:
            return

        try:
            tr = Track.get(path=src_path)
        except Track.DoesNotExist:
            return

        try:
            tr_dst = Track.get(path=dst_path)
            root = tr_dst.root_folder
            folder = tr_dst.folder
            self.remove_file(dst_path)
            tr.root_folder = root
            tr.folder = folder
        except Track.DoesNotExist:
            root = self.__find_root_folder(dst_path)
            folder = self.__find_folder(dst_path)
            tr.root_folder = root
            tr.folder = folder
        tr.path = dst_path
        tr.save()

    def find_cover(self, dirpath):
        if not isinstance(dirpath, str):  # pragma: nocover
            raise TypeError("Expecting string, got " + str(type(dirpath)))
        if not os.path.exists(dirpath):
            return
        try:
            folder = Folder.get(path=dirpath)
        except Folder.DoesNotExist:
            return
        album_name = None
        track = folder.tracks.select().first()
        if track is not None:
            album_name = track.album.name
            album = track.album
        else:
            return
        cover = find_cover_in_folder(folder.path, album_name)
        if cover:
            image_path = os.path.join(folder.path, cover.name) if cover else None
            Image.get_or_create(
                image_type="album",
                related_id=album.id,
                path=image_path,
            )

    def add_cover(self, path):
        if not isinstance(path, str):  # pragma: nocover
            raise TypeError("Expecting string, got " + str(type(path)))
        try:
            folder = Folder.get(path=os.path.dirname(path))
        except Folder.DoesNotExist:
            return
        track = folder.tracks.select().first()
        if track is not None:
            album = track.album
            if not album:
                logger.error(f"Track {track.path} has no album, cannot add cover")
                return
        else:
            logger.error(f"Folder {folder.path} has no tracks, cannot add cover")
            return
        cover_name = os.path.basename(path)
        album_name = track.album.name
        old_cover = Image.get_or_none(image_type="album", related_id=album.id)
        if old_cover and os.path.exists(old_cover.path):
            current_cover = CoverFile(old_cover.path, album_name)
            new_cover = CoverFile(cover_name, album_name)
            if new_cover.score > current_cover.score:
                old_cover.path = path
                old_cover.save()
                logger.info(f"Updated cover for album {album_name} with {cover_name}")
        else:
            # if no cover exists, create a new one
            if os.path.exists(path):
                Image.create(
                    image_type="album",
                    related_id=album.id,
                    path=path,
                )
                logger.info(f"Added cover for album {album_name} with {cover_name}")
            else:
                logger.error(f"Cover file {path} does not exist, cannot add cover")

    def find_lost_information(self):
        findLostInformation(self, logger=logger)

    def _record_album_artists(self, artists, album, main_artist=None):
        artist_names = [self.__sanitize_str(a) for a in artists]
        artist_names = [name for name in artist_names if name]
        if not artist_names:
            artist_names = ["unknown"]
        with Artist._meta.database.atomic():
            ars = [self.__find_artist(name) for name in artist_names]

            if main_artist is None:
                main = ars[0]
            elif isinstance(main_artist, Artist):
                main = main_artist
            else:
                main = self.__find_artist(main_artist)

            al, created = Album.get_or_create(name=album, artist=main)
            if created:
                self.__stats.added.albums += 1

            res = []
            for ar in ars:
                try:
                    relation, _ = AlbumArtist.get_or_create(album_id=al, artist_id=ar)
                except IntegrityError:
                    refreshed_artist = Artist.get_or_none(Artist.id == ar.id)
                    if refreshed_artist is None:
                        refreshed_artist = self.__find_artist(ar.name)
                    relation, _ = AlbumArtist.get_or_create(
                        album_id=al, artist_id=refreshed_artist
                    )
                res.append(relation)
        return res, al, ars[0]

    def _record_track_artists(self, artists, track):
        tr = track
        artist_names = [self.__sanitize_str(a) for a in artists]
        artist_names = [name for name in artist_names if name]
        if not artist_names:
            artist_names = ["unknown"]

        ars = [self.__find_artist(name) for name in artist_names]
        res = []
        for ar in ars:
            try:
                relation, _ = TrackArtist.get_or_create(track_id=tr, artist_id=ar)
            except IntegrityError:
                refreshed_artist = Artist.get_or_none(Artist.id == ar.id)
                if refreshed_artist is None:
                    refreshed_artist = self.__find_artist(ar.name)
                relation, _ = TrackArtist.get_or_create(
                    track_id=tr, artist_id=refreshed_artist
                )
            res.append(relation)
        return res, ars[0]

    def dicede_all_positions(self):
        # first dicide main album artist
        lost_positions_albumartist_relations = AlbumArtist.select().where(
            AlbumArtist.position == 0
        )
        for relation in lost_positions_albumartist_relations:
            # 获取该专辑-艺术家关系对应的专辑
            album = relation.album_id
            artist = relation.artist_id

            # 检查这个艺术家是否出现在该专辑的任何曲目的艺术家中
            artist_exists_in_tracks = False

            for track in album.tracks:  # 遍历专辑的所有曲目
                # 正确的方式：查询该曲目的TrackArtist关系
                track_artist_exists = (
                    TrackArtist.select()
                    .where(
                        (TrackArtist.track_id == track)
                        & (TrackArtist.artist_id == artist)
                    )
                    .exists()
                )

                if track_artist_exists:
                    artist_exists_in_tracks = True
                    break

            # 如果该艺术家不在任何曲目中，删除这个关系
            if not artist_exists_in_tracks:
                relation.delete_instance()
                continue
        lost_positions_albumartist_relations = AlbumArtist.select().where(
            AlbumArtist.position == 0
        )
        finish_albums = []
        for relation in lost_positions_albumartist_relations:
            target_album = relation.album_id
            if target_album in finish_albums:
                continue
            count = {}
            for track in target_album.tracks:
                for track_artist in track.track_artists:
                    if track_artist.artist_id not in count:
                        count[track_artist.artist_id] = 0
                    count[track_artist.artist_id] += 1
            # 先根据次数排序
            sorted_artists = sorted(count.items(), key=lambda x: x[1], reverse=True)
            i = 1
            for element in sorted_artists:
                artist = element[0]
                # 更新album
                if i == 1:
                    target_album.artist = artist
                    target_album.save()
                # 更新albumartists_relation
                relation = AlbumArtist.get_or_none(
                    album_id=target_album, artist_id=artist
                )
                if relation is None:
                    continue
                relation.position = i
                relation.save()
                # 更新track
                if i == 1:
                    for track in target_album.tracks:
                        track.artist = artist
                        track.save()
                # 更新track_artist_relation
                for track_relation in artist.artist_tracks:
                    if track_relation.track_id.album == target_album:
                        track_relation.position = i
                        track_relation.save()
                i += 1
            finish_albums.append(target_album)
        return

    def __find_album(self, artist, album):
        ar = self.__find_artist(artist)
        al = ar.albums.where(Album.name == album).first()
        if al:
            return al

        self.__stats.added.albums += 1
        return Album.create(name=album, artist=ar)

    def __find_artist(self, artist):
        try:
            artist = Artist.get(name=artist)
            if artist.real_artist:
                return artist.real_artist
            return artist
        except Artist.DoesNotExist:
            self.__stats.added.artists += 1
            return Artist.create(name=artist)

    def __find_root_folder(self, path):
        path = os.path.dirname(path)
        for folder in Folder.select().where(Folder.root):
            if path.startswith(folder.path):
                return folder

        raise Exception(
            "Couldn't find the root folder for '{}'.\nDon't scan files that aren't located in a defined music folder".format(
                path
            )
        )

    def __find_folder(self, path):
        children = []
        drive, _ = os.path.splitdrive(path)
        path = os.path.dirname(path)
        while path not in (drive, "/"):
            try:
                folder = Folder.get(path=path)
                break
            except Folder.DoesNotExist:
                pass

            created = datetime.fromtimestamp(os.path.getmtime(path))
            children.append(
                {
                    "root": False,
                    "name": os.path.basename(path),
                    "path": path,
                    "created": created,
                }
            )
            path = os.path.dirname(path)

        assert folder is not None
        while children:
            folder = Folder.create(parent=folder, **children.pop())

        return folder

    def renow_album_by_nfo(self, path):
        if not os.path.exists(path):
            return
        if os.path.isfile(path):
            nfo_data = self.__read_nfo(path)
            folder_path = os.path.dirname(path)
        elif os.path.isdir(path):
            folder_path = path
            nfo_path = os.path.join(path, "album.nfo")
            if os.path.exists(nfo_path):
                nfo_data = self.__read_nfo(nfo_path)
        if nfo_data:
            folder_element = Folder.get_or_none(path=folder_path)
            if not folder_element:
                return
            track_element = folder_element.tracks.select().first()
            all_tracks = list(folder_element.tracks)
            if not track_element:
                return
            album_element = track_element.album
            # renow album year
            nfo_year = nfo_data.get('album', {}).get('year', None)
            if nfo_year:
                album_element.year = nfo_year
                logger.info(f"renow album {album_element.name} year to {nfo_year}")
                album_element.save()
            # renow album artist
            albumartist = nfo_data.get('album', {}).get('albumartist', None)[0]
            if albumartist:
                album_element.artist = self.__find_artist(albumartist)
                album_element.save()
                logger.info(f"renow album {album_element.name} artist to {albumartist}")
            # renow album_artist relation
            nfo_artists = nfo_data.get('album', {}).get('artist', None)
            if nfo_artists:
                AlbumArtist.delete().where(
                    AlbumArtist.album_id == album_element
                ).execute()
                self._record_album_artists(
                    nfo_artists, album_element.name, main_artist=album_element.artist
                )
                album_element.save()
            # renow track artist by albumartist
            # check all tracks cdnum and tracknum right
            exist_nums = []
            for db_track in all_tracks:

                if db_track.disc is None or db_track.number is None:
                    logger.warning(
                        f"Track {db_track.path} has no disc or track number, skip renow artist"
                    )
                    return
                if db_track.number not in exist_nums:
                    exist_nums.append((db_track.disc, db_track.number))
                else:
                    logger.warning(
                        f"Track {db_track.path} has duplicate disc and track number, skip renow artist"
                    )
                    return
            # begin renow track artist
            nfo_tracks = nfo_data.get('album', {}).get('track', [])
            db_tracks = Track.select().where(Track.album == album_element.id)
            for nfo_track in nfo_tracks:
                db_track = db_tracks.where(
                    (Track.disc == nfo_track.get("cdnum"))
                    & (Track.number == nfo_track.get("position"))
                ).first()
                if db_track:
                    track = db_track
                    track.artist = album_element.artist
                    TrackArtist.delete().where(TrackArtist.track_id == track).execute()
                    self._record_track_artists(nfo_track.get("artist"), track)
                    track.save()
                    logger.info(
                        f"renow track {track.title} artist to {nfo_track.get('artist')}"
                    )

    def __try_load_tag(self, path):
        try:
            return mediafile.MediaFile(path)
        except mediafile.UnreadableFileError:
            return None

    def __sanitize_str(self, value):
        if value is None:
            return None
        return value.replace("\x00", "").strip()

    def stats(self):
        return self.__stats


def renow_track_hash():
    all_tracks = Track.select()
    for track in all_tracks:
        path = track.path
        if track.content_hash == "NULL":
            hash_value = get_file_md5(path)
            track.content_hash = hash_value
            track.save()
            logger.info(f"renow track {track.title} hash to {hash_value}")
