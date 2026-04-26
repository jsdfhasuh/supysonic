"""Repair missing album cover assets from local files and external services."""

from __future__ import annotations

import logging
import os
from typing import List, Optional, TYPE_CHECKING

import mediafile

from ..covers import CoverFile, find_cover_in_folder
from ..db import Album, Folder, Image, Track
from ..lastfm import LastFm
from ..tool import download_image
from ..MusicBrainz import get_musicbrainz_album_image_info, search_musicbrainz_album

if TYPE_CHECKING:
    from ..scanner import Scanner


def collectAlbumsMissingCover(scanner: Scanner) -> List[Album]:
    lost_cover_album: List[Album] = []
    for album in Album.select():
        if (
            Image.select()
            .where(Image.related_id == album.id, Image.image_type == "album")
            .exists()
        ):
            continue
        lost_cover_album.append(album)
        scanner.stats().lost_covers_albums[album.name] = ""
        scanner.stats().lost_covers.albums += 1
    return lost_cover_album


def findCover(scanner: Scanner, dirpath: str) -> None:
    if not isinstance(dirpath, str):  # pragma: nocover
        raise TypeError("Expecting string, got " + str(type(dirpath)))
    if not os.path.exists(dirpath):
        return

    try:
        folder = Folder.get(path=dirpath)
    except Folder.DoesNotExist:
        return

    track = folder.tracks.select().first()
    if track is None:
        return

    # This path handles folder-level cover discovery during scans and watcher updates.
    album_name = track.album.name
    album = track.album
    cover = find_cover_in_folder(folder.path, album_name)
    if cover:
        image_path = os.path.join(folder.path, cover.name)
        Image.get_or_create(
            image_type="album",
            related_id=album.id,
            path=image_path,
        )


def addCover(path: str, logger: logging.Logger) -> None:
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

    # This path handles a specific cover file being created or updated.
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
        return

    if os.path.exists(path):
        Image.create(
            image_type="album",
            related_id=album.id,
            path=path,
        )
        logger.info(f"Added cover for album {album_name} with {cover_name}")
    else:
        logger.error(f"Cover file {path} does not exist, cannot add cover")


def markAlbumCoverRestored(scanner: Scanner, album: Album) -> None:
    scanner.stats().lost_covers.albums -= 1
    scanner.stats().lost_covers_albums.pop(album.name, None)


def repairAlbumCover(
    scanner: Scanner,
    album: Album,
    get_cover_interner: bool = False,
    lfm: Optional[LastFm] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    track = Track.select().where(Track.album == album.id).first()
    scanner.stats().lost_covers_albums[album.name] = os.path.dirname(track.path) if track else ""
    if track is None:
        return

    cover_file = find_cover_in_folder(path=os.path.dirname(track.path), album_name=album.name)
    if cover_file:
        image_path = os.path.join(os.path.dirname(track.path), cover_file.name)
        Image.get_or_create(image_type="album", related_id=album.id, path=image_path)
        markAlbumCoverRestored(scanner, album)
        return

    cover = mediafile.MediaFile(track.path).art
    if cover:
        image_path = os.path.join(
            scanner.scan_config.BASE['tempdatafolder'], "album", f"{album.name}.png"
        )
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        with open(image_path, "wb") as f:
            f.write(cover)
        Image.create(image_type="album", related_id=album.id, path=image_path)
        markAlbumCoverRestored(scanner, album)
        return

    if get_cover_interner and not cover and lfm:
        dl_status = False
        album_artist_name = album.artist.get_artist_name()
        search_musicbrainz_album(artist_name=album_artist_name, album_name=album.name)
        lastfm_album = lfm.get_albuminfo(artist_name=album_artist_name, album_name=album.name)
        album_mbid = lastfm_album.get('album', {}).get('mbid', "")
        if album_mbid:
            musicbrainz_image_json = get_musicbrainz_album_image_info(mb_album_id=album_mbid)
            if musicbrainz_image_json:
                for image in musicbrainz_image_json.get('images', []):
                    if image.get('front', False):
                        dl_url = image['image']
                        image_path = download_image(
                            save_folder=os.path.dirname(track.path),
                            save_name="cover.png",
                            url=dl_url,
                            logger=logger,
                        )
                        if image_path:
                            Image.create(image_type="album", related_id=album.id, path=image_path)
                            if logger:
                                logger.info("download %s cover image", album.name)
                            markAlbumCoverRestored(scanner, album)
                            dl_status = True
                            break
                        if logger:
                            logger.error("Download image failed")
        if lastfm_album and not dl_status and lastfm_album['album']['image']:
            save_folder = os.path.dirname(track.path)
            for image in lastfm_album['album']['image']:
                if image['size'] not in ["large"]:
                    continue
                dl_url = image['#text']
                if not dl_url:
                    continue
                image_path = download_image(
                    save_folder=save_folder,
                    save_name="cover.png",
                    url=dl_url,
                    logger=logger,
                )
                if image_path:
                    Image.create(image_type="album", related_id=album.id, path=image_path)
                    if logger:
                        logger.info("download %s cover image", album.name)
                    markAlbumCoverRestored(scanner, album)
                    break
                if logger:
                    logger.error("Download image failed")
