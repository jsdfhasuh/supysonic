from __future__ import annotations

import os
import tempfile
from typing import Dict, List, Optional, Protocol

from ..db import Album, AlbumReviewTask, Track
from ..nfo.nfo import NfoHandler


class NfoSuppressClient(Protocol):
    def suppress_nfo_path(self, path: str, ttl: int) -> None:
        ...


def _normalizeTrackList(trackData: object) -> List[Dict[str, object]]:
    if isinstance(trackData, list):
        return [dict(track) for track in trackData if isinstance(track, dict)]
    if isinstance(trackData, dict):
        return [dict(trackData)]
    return []


def getReviewAlbumTracks(album: Album) -> List[Track]:
    return list(album.tracks.order_by(Track.disc, Track.number, Track.title))


def getReviewAlbumNfoPath(album: Album) -> str:
    tracks = getReviewAlbumTracks(album)
    if not tracks or tracks[0].folder is None or not tracks[0].folder.path:
        raise ValueError("album folder not found")

    return os.path.join(tracks[0].folder.path, "album.nfo")


def buildReviewAlbumNfoData(album: Album) -> Dict[str, Dict[str, object]]:
    tracks = getReviewAlbumTracks(album)

    return {
        "album": {
            "title": album.name,
            "year": album.year or "",
            "albumartist": album.artist.get_artist_name(),
            "artist": album.artist.get_artist_name(),
            "track": [
                {
                    "title": track.title,
                    "cdnum": track.disc,
                    "position": track.number,
                    "artist": track.artist.get_artist_name(),
                }
                for track in tracks
            ],
        }
    }


def mergeReviewAlbumNfo(existingData: Dict[str, object], reviewData: Dict[str, object]) -> Dict[str, object]:
    mergedData = dict(existingData or {})
    mergedAlbum = dict(mergedData.get("album", {}))
    reviewAlbum = dict(reviewData.get("album", {}))
    existingTracks = _normalizeTrackList(mergedAlbum.get("track"))
    reviewTracks = _normalizeTrackList(reviewAlbum.get("track"))
    existingTrackMap = {
        (str(track.get("cdnum")), str(track.get("position"))): dict(track)
        for track in existingTracks
    }

    for key in ("title", "year", "albumartist", "artist"):
        mergedAlbum[key] = reviewAlbum.get(key)

    mergedAlbum["track"] = []
    for index, reviewTrack in enumerate(reviewTracks):
        trackKey = (str(reviewTrack.get("cdnum")), str(reviewTrack.get("position")))
        mergedTrack = dict(existingTrackMap.get(trackKey, {}))
        if not mergedTrack and index < len(existingTracks):
            mergedTrack = dict(existingTracks[index])
        mergedTrack.update(reviewTrack)
        mergedAlbum["track"].append(mergedTrack)

    mergedData["album"] = mergedAlbum
    return mergedData


def writeReviewAlbumNfo(
    task: AlbumReviewTask,
    daemonClient: Optional[NfoSuppressClient],
    suppressTtl: int,
) -> str:
    if task.status != "pending":
        raise ValueError("Only pending review tasks can write album.nfo")

    nfoPath = getReviewAlbumNfoPath(task.album)
    reviewData = buildReviewAlbumNfoData(task.album)
    existingData = NfoHandler.read(nfoPath) if os.path.exists(nfoPath) else {}
    mergedData = mergeReviewAlbumNfo(existingData or {}, reviewData)
    if daemonClient is not None:
        daemonClient.suppress_nfo_path(nfoPath, suppressTtl)

    xmlContent = NfoHandler.write(mergedData, pretty=True)
    if not xmlContent:
        raise RuntimeError("failed to write album.nfo")

    tempFile = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=os.path.dirname(nfoPath),
            prefix=".album.nfo.",
            suffix=".tmp",
            delete=False,
        ) as outputFile:
            outputFile.write(xmlContent)
            tempFile = outputFile.name

        os.replace(tempFile, nfoPath)
    finally:
        if tempFile and os.path.exists(tempFile):
            os.unlink(tempFile)

    return nfoPath
