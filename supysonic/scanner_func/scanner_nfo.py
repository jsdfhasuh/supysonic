"""Apply album and track metadata repairs from album.nfo files."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from ..db import Album, AlbumArtist, Folder, Track, TrackArtist
from ..nfo.nfo import NfoHandler
from .scanner_lookup import findArtist
from .scanner_relations import recordAlbumArtists, recordTrackArtists

if TYPE_CHECKING:
    from ..scanner import Scanner


def _splitArtists(value: Optional[str]) -> List[str]:
    return value.split(",") if value else []


def readNfo(nfoPath: str) -> Dict[str, Any]:
    if not os.path.exists(nfoPath):
        return {}

    nfoData = NfoHandler.read(nfoPath)
    # Normalize artist-like fields to lists so later scan steps can treat
    # file-backed and folder-backed NFO data the same way.
    if "album" in nfoData:
        nfoData["album"]["artist"] = _splitArtists(nfoData["album"].get("artist"))
        nfoData["album"]["albumartist"] = _splitArtists(nfoData["album"].get("albumartist"))
        albumTracks = nfoData["album"].get("track", [])
        if isinstance(albumTracks, list):
            for track in albumTracks:
                track["artist"] = _splitArtists(track.get("artist"))
        else:
            albumTracks["artist"] = _splitArtists(albumTracks.get("artist"))
            nfoData["album"]["track"] = [albumTracks]
        return nfoData

    nfoData["artist"] = _splitArtists(nfoData.get("artist"))
    nfoData["albumartist"] = _splitArtists(nfoData.get("albumartist"))
    for track in nfoData.get("track", []):
        track["artist"] = _splitArtists(track.get("artist"))
    return nfoData


def _loadAlbumNfo(scanner: Scanner, path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    nfoData = None
    folderPath = None

    if not os.path.exists(path):
        return None, None
    if os.path.isfile(path):
        nfoData = readNfo(path)
        folderPath = os.path.dirname(path)
    elif os.path.isdir(path):
        folderPath = path
        nfoPath = os.path.join(path, "album.nfo")
        if os.path.exists(nfoPath):
            nfoData = readNfo(nfoPath)

    return nfoData, folderPath


def _loadAlbumFolderState(folderPath: str) -> Tuple[Optional[Folder], Optional[Track], Optional[List[Track]]]:
    folderElement = Folder.get_or_none(path=folderPath)
    if not folderElement:
        return None, None, None

    trackElement = folderElement.tracks.select().first()
    allTracks = list(folderElement.tracks)
    if not trackElement:
        return None, None, None

    return folderElement, trackElement, allTracks


def _renowAlbumMetadata(
    scanner: Scanner,
    albumElement: Album,
    nfoData: Dict[str, Any],
    logger: logging.Logger,
) -> None:
    nfoYear = nfoData.get("album", {}).get("year", None)
    if nfoYear:
        albumElement.year = nfoYear
        logger.info(f"renow album {albumElement.name} year to {nfoYear}")
        albumElement.save()

    albumArtists = nfoData.get("album", {}).get("albumartist", None)
    albumArtist = albumArtists[0] if albumArtists else None
    if albumArtist:
        albumElement.artist = findArtist(scanner, albumArtist)
        albumElement.save()
        logger.info(f"renow album {albumElement.name} artist to {albumArtist}")

    nfoArtists = nfoData.get("album", {}).get("artist", None)
    if nfoArtists:
        AlbumArtist.delete().where(AlbumArtist.album_id == albumElement).execute()
        recordAlbumArtists(
            scanner,
            nfoArtists,
            albumElement.name,
            main_artist=albumElement.artist,
        )
        albumElement.save()


def _validateTrackNumbers(allTracks: List[Track], logger: logging.Logger) -> bool:
    existNums = []
    for dbTrack in allTracks:
        if dbTrack.disc is None or dbTrack.number is None:
            logger.warning(
                f"Track {dbTrack.path} has no disc or track number, skip renow artist"
            )
            return False
        if dbTrack.number not in existNums:
            existNums.append((dbTrack.disc, dbTrack.number))
        else:
            logger.warning(
                f"Track {dbTrack.path} has duplicate disc and track number, skip renow artist"
            )
            return False
    return True


def _renowTrackArtists(
    scanner: Scanner,
    albumElement: Album,
    nfoData: Dict[str, Any],
    logger: logging.Logger,
) -> None:
    nfoTracks = nfoData.get("album", {}).get("track", [])
    dbTracks = Track.select().where(Track.album == albumElement.id)
    for nfoTrack in nfoTracks:
        dbTrack = dbTracks.where(
            (Track.disc == nfoTrack.get("cdnum"))
            & (Track.number == nfoTrack.get("position"))
        ).first()
        if not dbTrack:
            continue

        track = dbTrack
        track.artist = albumElement.artist
        TrackArtist.delete().where(TrackArtist.track_id == track).execute()
        recordTrackArtists(scanner, nfoTrack.get("artist"), track)
        track.save()
        logger.info(f"renow track {track.title} artist to {nfoTrack.get('artist')}")


def renowAlbumByNfo(scanner: Scanner, path: str, logger: logging.Logger) -> None:
    nfoData, folderPath = _loadAlbumNfo(scanner, path)
    if not nfoData or not folderPath:
        return

    _, trackElement, allTracks = _loadAlbumFolderState(folderPath)
    if not trackElement:
        return

    albumElement = trackElement.album
    _renowAlbumMetadata(scanner, albumElement, nfoData, logger)
    if not _validateTrackNumbers(allTracks, logger):
        return
    _renowTrackArtists(scanner, albumElement, nfoData, logger)
