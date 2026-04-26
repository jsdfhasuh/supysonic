"""Handle scan target discovery and build raw track data from media files."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Union

import mediafile

from ..db import Album, Track
from .scanner_common import sanitizeString, tryLoadTag
from .scanner_nfo import readNfo
from .scanner_relations import recordAlbumArtists
from .scanner_types import ScanTarget

if TYPE_CHECKING:
    from ..scanner import Scanner


def getScanTargetInfo(path_or_direntry: Union[str, os.DirEntry]) -> Optional[ScanTarget]:
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


def loadTrackForScan(
    scanner: Scanner,
    path: str,
    mtime: int,
) -> Tuple[Optional[Track], Optional[mediafile.MediaFile], Optional[Dict[str, Any]]]:
    track = Track.get_or_none(path=path)
    if track is not None and not scanner.force_scan and not mtime > track.last_modification:
        return track, None, None

    tag = tryLoadTag(path)
    if tag is None:
        if track is not None:
            scanner.remove_file(path)
        return track, None, None

    track_data = {} if track is not None else {"path": path}
    return track, tag, track_data


def resolveAlbumContext(
    scanner: Scanner,
    path: str,
    tag: mediafile.MediaFile,
) -> Tuple[Dict[str, Any], List[str], Album]:
    album_info_path = os.path.join(os.path.dirname(path), "album.nfo")
    nfo_data = readNfo(album_info_path)
    raw = tag.mgfile
    raw_artists = raw.get("artist", [])
    raw_albumartists = raw.get("albumartist", [])
    album_section = nfo_data.get("album", {})
    album_artists = album_section.get("albumartist", []) or raw_albumartists or ["unknown"]
    artists = album_section.get("artist", []) or raw_artists or ["unknown"]
    _, album_id, _ = recordAlbumArtists(scanner, album_artists, sanitizeString(tag.album))
    return nfo_data, artists, album_id


def buildTrackData(
    scanner: Scanner,
    basename: str,
    mtime: int,
    tag: mediafile.MediaFile,
) -> Dict[str, Any]:
    return {
        "disc": tag.disc or 1,
        "number": tag.track or 1,
        "title": (sanitizeString(tag.title) or basename)[:255],
        "year": tag.year,
        "genre": tag.genre,
        "duration": int(tag.length),
        "has_art": bool(tag.images),
        "bitrate": tag.bitrate // 1000,
        "last_modification": mtime,
    }
