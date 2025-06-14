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

from datetime import datetime
from queue import Queue, Empty as QueueEmpty
from threading import Thread, Event
from flask import current_app
from .config import IniConfig
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
from .tool import download_image, read_dict_from_json, write_dict_to_json, extract_year
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

    def scan_file(self, path_or_direntry):
        if isinstance(path_or_direntry, str):
            path = path_or_direntry

            if not os.path.exists(path):
                return

            basename = os.path.basename(path)
            stat = os.stat(path)
        else:
            path = path_or_direntry.path
            basename = path_or_direntry.name
            stat = path_or_direntry.stat()

        try:
            path.encode("utf-8")  # Test for badly encoded paths
        except UnicodeError:
            self.__stats.errors.append(path)
            return

        mtime = int(stat.st_mtime)
        if os.path.isfile(path) and '.flac' in path.lower():
            pass
            self.__stats.existing_tracks += 1
        tr = Track.get_or_none(path=path)
        if tr is not None:
            if not self.__force and not mtime > tr.last_modification:
                return

            tag = self.__try_load_tag(path)
            if tag is None:
                self.remove_file(path)
                return
            trdict = {}
        else:
            tag = self.__try_load_tag(path)
            if tag is None:
                return

            trdict = {"path": path}
        # album info
        album_info = "album.nfo"
        raw = tag.mgfile
        raw_artists = raw.get("artist", [])
        raw_albumartists = raw.get("albumartist", [])
        # add artist to db

        nfo_data = self.__read_nfo(os.path.join(os.path.dirname(path), album_info))
        artists = nfo_data['album'].get("artist", []) or raw_artists or ["unknown"]
        album = (self.__sanitize_str(tag.album) or "[non-album tracks]")[:255]
        albumartist = (
            nfo_data['album'].get("albumartist", []) or raw_albumartists or ["unknown"]
        )
        rs, album_id, main_artist = self._record_album_artists(
            albumartist, self.__sanitize_str(tag.album)
        )

        trdict["disc"] = tag.disc or 1
        trdict["number"] = tag.track or 1
        trdict["title"] = (self.__sanitize_str(tag.title) or basename)[:255]
        trdict["year"] = tag.year
        trdict["genre"] = tag.genre
        trdict["duration"] = int(tag.length)
        trdict["has_art"] = bool(tag.images)
        trartists = []
        trdict["bitrate"] = tag.bitrate // 1000
        trdict["last_modification"] = mtime
        for nfo_track in nfo_data.get('album', {}).get('track', []):
            try:
                nfo_track_number = int(nfo_track.get("cdnum", 1))
                nfo_track_disc = int(nfo_track.get("cdnum", 1))
            except:
                nfo_track_number = nfo_track.get("cdnum", 1)
                nfo_track_disc = nfo_track.get("cdnum", 1)
            if (
                nfo_track_disc == trdict["number"]
                and nfo_track_number == trdict["disc"]
            ):
                if "artist" in nfo_track:
                    trartists = nfo_track["artist"]
                    break
        # artist only one temperate
        tralbum = album_id
        if trartists == []:
            trartists = artists
        trartist = trartists[0]
        trartist = self.__find_artist(trartist)
        if tr is None:
            trdict["root_folder"] = self.__find_root_folder(path)
            trdict["folder"] = self.__find_folder(path)
            trdict["album"] = tralbum
            trdict["artist"] = trartist
            trdict["created"] = datetime.fromtimestamp(mtime)
            try:
                tr = Track.create(**trdict)
                self.__stats.added.tracks += 1
            except ValueError:
                # Field validation error
                self.__stats.errors.append(path)
        else:
            if tr.album.id != tralbum.id:
                trdict["album"] = tralbum

            if tr.artist.id != trartist.id:
                trdict["artist"] = trartist
            try:
                for attr, value in trdict.items():
                    setattr(tr, attr, value)
                tr.save()
            except ValueError:
                # Field validation error
                self.__stats.errors.append(path)
        self._record_track_artists(trartists, tr)

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
        # find lost album and artist information
        # check album
        # find lost year

        lfm = None
        sp = None
        user = User.get_or_none(User.name == "root")
        get_cover_interner = False
        if user and user.lastfm_status and self.__config.SPOTIFY['client_id']:
            get_cover_interner = True
            lfm = LastFm(self.__config.LASTFM, user)
            sp = MySpotify(self.__config.SPOTIFY)
        lost_year_albums = []
        for album in Album.select():
            track = Track.select().where(Track.album == album.id).first()
            if album.year:
                continue
            else:
                lost_year_albums.append(album)
                self.__stats.lost_year_albums[album.name] = (
                    os.path.dirname(track.path) if track else ""
                )
        for album in lost_year_albums:
            track = Track.select().where(Track.album == album.id).first()
            if track and track.year:
                year = extract_year(str(track.year))
                album.year = year
                album.save()
                lost_year_albums.remove(album)
                self.__stats.lost_year_albums.pop(album.name, None)
        for album in lost_year_albums:
            # try to find year from musicBrainz
            album_artist_name = album.artist.name
            musicbrainz_album = search_musicbrainz_album(
                artist_name=album_artist_name, album_name=album.name
            )
            if musicbrainz_album and musicbrainz_album.get('id'):
                result = get_musicbrainz_album(mb_album_id=musicbrainz_album['id'])
                year = extract_year(result.get('date'))
                if year:
                    print(f"find year {year} for album {album.name}")
                    album.year = year
                    album.save()
                    self.__stats.lost_year_albums.pop(album.name, None)
                    lost_year_albums.remove(album)
            pass
        pass
        if lfm and sp:
            for album in lost_year_albums:
                album_artist_name = album.artist.name
                lastfm_album = lfm.get_albuminfo(
                    artist_name=album_artist_name, album_name=album.name
                )
                if lastfm_album and 'wiki' in lastfm_album.get('album', {}):
                    wiki_content = lastfm_album['album']['wiki'].get('summary', "")
                    wiki_year = extract_year(s=lfm.get_wiki_year(wiki_content))
                    if wiki_year:
                        year = extract_year(wiki_year)
                    else:
                        published_year = lastfm_album['album']['wiki'].get(
                            'published', ""
                        )
                        year = extract_year(published_year)
                    print(f"find year {year} for album {album.name}")
                    album.year = year
                    album.save()
                    self.__stats.lost_year_albums.pop(album.name, None)
                    lost_year_albums.remove(album)
                pass
        # find lost cover
        lost_cover_album = []
        for album in Album.select():
            if (
                Image.select()
                .where(Image.related_id == album.id, Image.image_type == "album")
                .exists()
            ):
                continue
            else:
                lost_cover_album.append(album)
                self.__stats.lost_covers_albums[album.name] = ""
                self.__stats.lost_covers.albums += 1

        for album in lost_cover_album:
            track = Track.select().where(Track.album == album.id).first()
            self.__stats.lost_covers_albums[album.name] = (
                os.path.dirname(track.path) if track else ""
            )
            # local folder cover
            cover_file = find_cover_in_folder(
                path=os.path.dirname(track.path), album_name=album.name
            )
            if cover_file:
                image_path = os.path.join(os.path.dirname(track.path), cover_file.name)
                Image.get_or_create(
                    image_type="album",
                    related_id=album.id,
                    path=image_path,
                )
                self.__stats.lost_covers.albums -= 1
                self.__stats.lost_covers_albums.pop(album.name, None)
                continue
            # find_local_cover
            cover = mediafile.MediaFile(track.path).art
            if cover:
                image_path = os.path.join(
                    self.__config.BASE['tempdatafolder'], "album", f"{album.name}.png"
                )
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                with open(image_path, "wb") as f:
                    f.write(cover)
                Image.create(
                    image_type="album",
                    related_id=album.id,
                    path=image_path,
                )
                self.__stats.lost_covers.albums -= 1
                self.__stats.lost_covers_albums.pop(album.name, None)
                continue

            # try lastfm cover
            if get_cover_interner and not cover:
                # get information from musicBrainz
                dl_status = False
                # get information from lastfm cover
                album_artist_name = album.artist.name
                musicbrainz_album = search_musicbrainz_album(
                    artist_name=album_artist_name, album_name=album.name
                )
                lastfm_album = lfm.get_albuminfo(
                    artist_name=album_artist_name, album_name=album.name
                )
                album_mbid = lastfm_album.get('album', {}).get('mbid', "")
                if album_mbid:
                    musicBrainzId_json = get_musicbrainz_album_image_info(
                        mb_album_id=album_mbid
                    )
                    if musicBrainzId_json:
                        for image in musicBrainzId_json.get('images', []):
                            if image.get('front', False):
                                dl_url = image['image']
                                image_path = download_image(
                                    save_folder=os.path.dirname(track.path),
                                    save_name=f"cover.png",
                                    url=dl_url,
                                    logger=logger,
                                )
                                if image_path:
                                    Image.create(
                                        image_type="album",
                                        related_id=album.id,
                                        path=image_path,
                                    )
                                    logger.info(f"download {album.name} cover image")
                                    self.__stats.lost_covers.albums -= 1
                                    self.__stats.lost_covers_albums.pop(
                                        album.name, None
                                    )
                                    dl_status = True
                                    break
                                else:
                                    logger.error("Download image failed")
                                    continue
                if lastfm_album and not dl_status:
                    if lastfm_album['album']['image']:
                        save_folder = os.path.dirname(track.path)
                        for image in lastfm_album['album']['image']:
                            size = image['size']
                            if size not in ["large"]:
                                continue
                            dl_url = image['#text']
                            if not dl_url:
                                continue
                            image_path = download_image(
                                save_folder=save_folder,
                                save_name=f"cover.png",
                                url=dl_url,
                                logger=logger,
                            )
                            if image_path:
                                Image.create(
                                    image_type="album",
                                    related_id=album.id,
                                    path=image_path,
                                )
                                logger.info(f"download {album.name} cover image")
                                dl_status = True
                                self.__stats.lost_covers.albums -= 1
                                self.__stats.lost_covers_albums.pop(album.name, None)
                                break
                            else:
                                logger.error("Download image failed")
                                continue

        # check artist
        lost_cover_artist = []
        for artist in Artist.select():
            if artist.artist_info_json:
                continue
            else:
                lost_cover_artist.append(artist)
                self.__stats.lost_covers.artists += 1
                self.__stats.lost_covers_artists.append(artist.name)
        # check if the root user in

        if get_cover_interner:
            if user.lastfm_status and self.__config.SPOTIFY['client_id']:
                sp = MySpotify(self.__config.SPOTIFY, user)
                lfm = LastFm(self.__config.LASTFM, user)
                for artist in lost_cover_artist:
                    if artist.name == "Various Artists" or len(artist.name) < 2:
                        continue
                    result = lfm.get_artistinfo(
                        name=artist.name, lang=self.__config.LASTFM['display_lang']
                    )
                    if (
                        not result
                        or result.get('message', "")
                        == 'The artist you supplied could not be found'
                    ):
                        continue
                    result_json = {}
                    result_json['image'] = {}
                    result_json['similarArtists'] = []
                    wiki_url = result['artist']['bio']['links']['link']['href']
                    artist_name = result['artist']['name']
                    artists_folder = os.path.join(
                        self.__config.BASE['tempdatafolder'], 'artist', f'{artist_name}'
                    )
                    sp_result = sp.get_artist_info(artist.name)
                    os.makedirs(artists_folder, exist_ok=True)
                    # get image from spotify
                    dl_status = False
                    if sp_result:
                        dl_status = True
                        if sp_result['artists']['items']:
                            for element in sp_result['artists']['items'][0]['images']:
                                size_num = element['height']
                                if size_num > 600:
                                    size = "large"
                                elif 600 > size_num > 300:
                                    size = "medium"
                                elif size_num < 300:
                                    size = "small"
                                dl_url = element['url']
                                image_path = download_image(
                                    save_folder=artists_folder,
                                    save_name=size,
                                    url=dl_url,
                                    logger=logger,
                                )
                                if image_path:
                                    result_json['image'][size] = image_path
                                    self.__stats.lost_covers.artists -= 1
                                else:
                                    logger.error("Download image failed")
                                    dl_status = False
                        else:
                            continue

                    else:
                        if not dl_status:
                            logger.error("Download image failed")
                            continue
                    wiki_content = lfm.get_lastfm_wiki(wiki_url)
                    wiki_content = wiki_content if wiki_content else wiki_url
                    if not wiki_content:
                        logger.error("Get wiki content failed")
                        continue
                    result_json['biography'] = wiki_content
                    result_json['lastFmUrl'] = result['artist']['url']
                    write_dict_to_json(
                        data=result_json,
                        filename=os.path.join(artists_folder, f"info.json"),
                    )
                    if os.path.exists(os.path.join(artists_folder, f"info.json")):
                        artist.artist_info_json = os.path.join(
                            artists_folder, f"info.json"
                        )
                        artist.save()
                        self.__stats.lost_covers_artists.remove(artist.name)

        if get_cover_interner:
            if user.lastfm_status and self.__config.SPOTIFY['client_id']:
                # check if the artist who have infor.json the picture is exist
                for artist in Artist.select().where(
                    Artist.artist_info_json.is_null(False)
                ):
                    if not os.path.exists(artist.artist_info_json):
                        continue
                    info = read_dict_from_json(artist.artist_info_json)
                    if not info or not info.get('image'):
                        continue
                    for size, image_path in info['image'].items():
                        if not os.path.exists(image_path):
                            sp_result = sp.get_artist_info(artist.name)
                            # get image from spotify
                            artists_folder = os.path.dirname(image_path)
                            if sp_result:
                                if sp_result['artists']['items']:
                                    for element in sp_result['artists']['items'][0][
                                        'images'
                                    ]:
                                        size_num = element['height']
                                        if size_num > 600:
                                            size = "large"
                                        elif 600 > size_num > 300:
                                            size = "medium"
                                        elif size_num < 300:
                                            size = "small"
                                        dl_url = element['url']
                                        if download_image(
                                            save_folder=artists_folder,
                                            save_name=size,
                                            url=dl_url,
                                            logger=logger,
                                        ):
                                            info['image'][size] = os.path.join(
                                                artists_folder, f"{size}.png"
                                            )
                                            write_dict_to_json(
                                                data=info,
                                                filename=os.path.join(
                                                    artists_folder, f"info.json"
                                                ),
                                            )

    def _record_album_artists(self, artists, album):
        # find all artists in the database
        al = None
        ars = []
        res = []
        for artist in artists:
            ar = self.__find_artist(artist)
            if ar is None:
                ar = Artist.create(name=artist)
            ars.append(ar)
            if not al:
                al = self.__find_album(artist, album)
        else:
            if al is None:
                al = Album.create(name=album, artist=ars[0])
        for ar in ars:
            relation = AlbumArtist.get_or_create(album_id=al, artist_id=ar)
            res.append(relation)
        return res, al, ars[0]

    def _record_track_artists(self, artists, track):
        tr = track
        ars = []
        res = []
        for artist in artists:
            ar = self.__find_artist(artist)
            if ar is None:
                ar = Artist.create(name=artist)
            ars.append(ar)
        for ar in ars:
            relation = TrackArtist.get_or_create(track_id=tr, artist_id=ar)
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
            return Artist.get(name=artist)
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
            if not track_element:
                return
            album_element = track_element.album
            # renow album year
            nfo_year = nfo_data.get('album', {}).get('year', None)
            if nfo_year:
                album_element.year = nfo_year
                logger.info(f"renow album {album_element.name} year to {nfo_year}")
                album_element.save()
            pass

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
