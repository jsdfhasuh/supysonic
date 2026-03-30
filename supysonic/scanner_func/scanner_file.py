import os

from ..db import Track
from .scanner_types import ScanTarget


def getScanTargetInfo(path_or_direntry):
    if isinstance(path_or_direntry, str):
        path = path_or_direntry
        if not os.path.exists(path):
            return None
        return ScanTarget(path=path, basename=os.path.basename(path), stat=os.stat(path))

    return ScanTarget(
        path=path_or_direntry.path,
        basename=path_or_direntry.name,
        stat=path_or_direntry.stat(),
    )


def loadTrackForScan(scanner, path, mtime):
    track = Track.get_or_none(path=path)
    if track is not None and not scanner._Scanner__force and not mtime > track.last_modification:
        return track, None, None

    tag = scanner._Scanner__try_load_tag(path)
    if tag is None:
        if track is not None:
            scanner.remove_file(path)
        return track, None, None

    track_data = {} if track is not None else {"path": path}
    return track, tag, track_data


def resolveAlbumContext(scanner, path, tag):
    album_info_path = os.path.join(os.path.dirname(path), "album.nfo")
    nfo_data = scanner._Scanner__read_nfo(album_info_path)
    raw = tag.mgfile
    raw_artists = raw.get("artist", [])
    raw_albumartists = raw.get("albumartist", [])
    album_section = nfo_data.get("album", {})
    album_artists = album_section.get("albumartist", []) or raw_albumartists or ["unknown"]
    artists = album_section.get("artist", []) or raw_artists or ["unknown"]
    _, album_id, _ = scanner._record_album_artists(
        album_artists, scanner._Scanner__sanitize_str(tag.album)
    )
    return nfo_data, artists, album_id


def buildTrackData(scanner, basename, mtime, tag):
    return {
        "disc": tag.disc or 1,
        "number": tag.track or 1,
        "title": (scanner._Scanner__sanitize_str(tag.title) or basename)[:255],
        "year": tag.year,
        "genre": tag.genre,
        "duration": int(tag.length),
        "has_art": bool(tag.images),
        "bitrate": tag.bitrate // 1000,
        "last_modification": mtime,
    }
