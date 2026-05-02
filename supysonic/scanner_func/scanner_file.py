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


def _coerceArtistList(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]

    artists = []
    for item in values:
        artist = sanitizeString(item)
        if artist:
            artists.append(artist)
    return artists


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
) -> Tuple[Dict[str, Any], List[str], Album, Dict[str, Any]]:
    album_info_path = os.path.join(os.path.dirname(path), "album.nfo")
    nfo_data = readNfo(album_info_path)
    raw = getattr(tag, "mgfile", {})
    raw_artists = _coerceArtistList(raw.get("artist", [])) if hasattr(raw, "get") else []
    raw_albumartists = _coerceArtistList(raw.get("albumartist", [])) if hasattr(raw, "get") else []
    if not raw_artists:
        raw_artists = _coerceArtistList(getattr(tag, "artists", None) or getattr(tag, "artist", None))
    if not raw_albumartists:
        raw_albumartists = _coerceArtistList(
            getattr(tag, "albumartists", None) or getattr(tag, "albumartist", None)
        )
    album_section = nfo_data.get("album", {})
    album_artists = album_section.get("albumartist", []) or raw_albumartists or raw_artists or ["unknown"]
    artists = album_section.get("artist", []) or raw_artists or raw_albumartists or ["unknown"]
    _, album_id, _ = recordAlbumArtists(scanner, album_artists, sanitizeString(tag.album))
    trace_context = {
        "album_artists": album_artists,
        "album_artist_source": "fallback unknown",
        "raw_album_artists": raw_albumartists,
        "raw_artists": raw_artists,
        "artist_source": "fallback unknown",
        "resolved_album_artists": album_artists,
        "resolved_album_artist_count": len(album_artists),
    }
    if album_section.get("albumartist", []):
        trace_context["album_artist_source"] = "album.nfo albumartist"
    elif raw_albumartists:
        trace_context["album_artist_source"] = "tag albumartist"
    elif raw_artists:
        trace_context["album_artist_source"] = "tag artist fallback"

    if album_section.get("artist", []):
        trace_context["artist_source"] = "album.nfo artist"
    elif raw_artists:
        trace_context["artist_source"] = "tag artist"
    elif raw_albumartists:
        trace_context["artist_source"] = "tag albumartist fallback"

    return nfo_data, artists, album_id, trace_context


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
