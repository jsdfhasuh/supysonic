"""Persist scanned track records and resolve track-level artist assignments."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from ..db import Album, Artist, Track
from .scanner_lookup import findArtist, findFolder, findRootFolder

if TYPE_CHECKING:
    from ..scanner import Scanner


def resolveTrackArtists(
    scanner: Scanner,
    nfo_data: Dict[str, Any],
    track_data: Dict[str, Any],
    fallback_artists: List[str],
) -> Tuple[List[str], Artist]:
    track_artists = []
    for nfo_track in nfo_data.get("album", {}).get("track", []):
        try:
            nfo_track_number = int(nfo_track.get("position", 1))
            nfo_track_disc = int(nfo_track.get("cdnum", 1))
        except Exception:
            nfo_track_number = nfo_track.get("position", 1)
            nfo_track_disc = nfo_track.get("cdnum", 1)
        if (
            nfo_track_disc == track_data["disc"]
            and nfo_track_number == track_data["number"]
        ):
            if "artist" in nfo_track:
                track_artists = nfo_track["artist"]
                break

    if not track_artists:
        track_artists = fallback_artists

    return track_artists, findArtist(scanner, track_artists[0])


def createOrUpdateTrack(
    scanner: Scanner,
    track: Optional[Track],
    path: str,
    mtime: int,
    track_data: Dict[str, Any],
    album: Album,
    artist: Artist,
) -> Optional[Track]:
    if track is None:
        track_data["root_folder"] = findRootFolder(path)
        track_data["folder"] = findFolder(path)
        track_data["album"] = album
        track_data["artist"] = artist
        track_data["created"] = datetime.fromtimestamp(mtime)
        try:
            track = Track.create(**track_data)
            scanner.stats().added.tracks += 1
        except ValueError:
            scanner.stats().errors.append(path)
            return None
        return track

    if track.album.id != album.id:
        track_data["album"] = album
    if track.artist.id != artist.id:
        track_data["artist"] = artist

    try:
        for attr, value in track_data.items():
            setattr(track, attr, value)
        track.save()
    except ValueError:
        scanner.stats().errors.append(path)
        return None

    return track
