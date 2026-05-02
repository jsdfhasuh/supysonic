"""Run the single-file scanner pipeline from discovery to relation updates."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Union

from .scanner_file import (
    buildTrackData,
    getScanTargetInfo,
    loadTrackForScan,
    resolveAlbumContext,
)
from .scanner_persist import createOrUpdateTrack, resolveTrackArtists
from .scanner_relations import replaceTrackArtists
from .scanner_trace import logTrace

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..scanner import Scanner


def _validateScanPath(scanner: Scanner, path: str) -> bool:
    try:
        path.encode("utf-8")
    except UnicodeError:
        scanner.stats().errors.append(path)
        return False
    return True


def _hasMatchingNfoTrackArtists(nfo_data, track_data) -> bool:
    for nfo_track in nfo_data.get("album", {}).get("track", []):
        if not nfo_track.get("artist"):
            continue
        try:
            nfo_track_number = int(nfo_track.get("position", 1))
            nfo_track_disc = int(nfo_track.get("cdnum", 1))
        except Exception:
            nfo_track_number = nfo_track.get("position", 1)
            nfo_track_disc = nfo_track.get("cdnum", 1)
        if nfo_track_disc == track_data["disc"] and nfo_track_number == track_data["number"]:
            return True
    return False


def _getTrackArtistSource(nfo_data, track_data, track_artists, artists) -> str:
    if _hasMatchingNfoTrackArtists(nfo_data, track_data):
        return "album.nfo track artists"
    if track_artists == artists:
        return "fallback album artists"
    if tag_artists := track_data.get("_tag_artists"):
        if track_artists == tag_artists:
            return "tag artist"
    return "resolver override"


def processScanFile(scanner: Scanner, path_or_direntry: Union[str, os.DirEntry]) -> None:
    target = getScanTargetInfo(path_or_direntry)
    if target is None:
        return

    path = target.path
    basename = target.basename
    stat = target.stat
    if not _validateScanPath(scanner, path):
        return

    mtime = int(stat.st_mtime)
    # Keep the current FLAC bookkeeping intact while the scan pipeline is moved out.
    if os.path.isfile(path) and ".flac" in path.lower():
        scanner.stats().existing_tracks += 1

    track, tag, track_data = loadTrackForScan(scanner, path, mtime)
    if tag is None:
        return

    # Normalize metadata before persistence, then update artist relations last.
    nfo_data, artists, album_id, album_context = resolveAlbumContext(scanner, path, tag)
    track_data.update(buildTrackData(scanner, basename, mtime, tag))
    track_data["_tag_artists"] = list(album_context.get("raw_artists", []))
    track_artists, track_artist = resolveTrackArtists(scanner, nfo_data, track_data, artists)
    track = createOrUpdateTrack(
        scanner,
        track,
        path,
        mtime,
        track_data,
        album_id,
        track_artist,
    )
    if track is None:
        return

    replaceTrackArtists(scanner, track_artists, track)
    album_section = nfo_data.get("album", {})
    tag_artists = track_data.pop("_tag_artists", [])
    track_artist_source = _getTrackArtistSource(nfo_data, track_data, track_artists, artists)
    resolved_album_artists = album_context.get("resolved_album_artists", album_context.get("album_artists", []))
    resolved_album_artist_count = album_context.get("resolved_album_artist_count", len(resolved_album_artists))

    logTrace(
        logger,
        "TRACK_TRACE",
        {
            "path": path,
            "track_id": track.id,
            "disc": track_data.get("disc"),
            "number": track_data.get("number"),
        },
        [
            f"album artists source: {album_context['album_artist_source']}",
            f"album artists from tag: {', '.join(album_context['raw_album_artists']) or 'none'}",
            f"album artists from nfo: {', '.join(album_section.get('albumartist', [])) or 'none'}",
            f"resolved album artists: {', '.join(resolved_album_artists) or 'none'}",
            f"resolved album artist count: {resolved_album_artist_count}",
            f"album track artists source: {album_context['artist_source']}",
            f"track artists source: {track_artist_source}",
            f"track artists from tag: {', '.join(album_context['raw_artists']) or 'none'}",
            f"track artists from nfo: {', '.join(next((nfo_track.get('artist', []) for nfo_track in nfo_data.get('album', {}).get('track', []) if str(nfo_track.get('cdnum', 1)) == str(track_data.get('disc')) and str(nfo_track.get('position', 1)) == str(track_data.get('number'))), [])) or 'none'}",
            f"resolved track artists: {', '.join(track_artists)}",
            f"resolved main artist: {track_artist.name}",
        ],
    )
