"""Run the single-file scanner pipeline from discovery to relation updates."""

from __future__ import annotations

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

if TYPE_CHECKING:
    from ..scanner import Scanner


def _validateScanPath(scanner: Scanner, path: str) -> bool:
    try:
        path.encode("utf-8")
    except UnicodeError:
        scanner.stats().errors.append(path)
        return False
    return True


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
    nfo_data, artists, album_id = resolveAlbumContext(scanner, path, tag)
    track_data.update(buildTrackData(scanner, basename, mtime, tag))
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
