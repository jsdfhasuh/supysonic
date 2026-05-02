"""Create album-scoped metadata review tasks after scan post-processing."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from ..db import Album, AlbumReviewTask, close_connection, open_connection

if TYPE_CHECKING:
    from ..scanner import Scanner

logger = logging.getLogger(__name__)

PENDING_REVIEW_TASK_STATUS = "pending"
CLOSED_REVIEW_TASK_STATUSES = {"confirmed", "dismissed", "expired"}
METADATA_REVIEW_TASK_TYPE = "metadata_review"
NEW_ALBUM_REVIEW_REASON = "new_album"
MISSING_YEAR_REVIEW_REASON = "missing_year"


def rememberNewAlbum(scanner: Scanner, album: Album) -> None:
    if not hasattr(scanner, "review_task_album_ids"):
        scanner.review_task_album_ids = set()
    scanner.review_task_album_ids.add(album.id)


def buildAlbumReviewSnapshot(album: Album) -> str:
    snapshot = {
        "album_id": str(album.id),
        "album_name": album.name,
        "artist_name": album.artist.get_artist_name(),
        "year": album.year,
        "track_count": album.tracks.count(),
    }
    return json.dumps(snapshot, ensure_ascii=False)


def createAlbumReviewTasks(scanner: Scanner) -> int:
    album_ids = getattr(scanner, "review_task_album_ids", set())
    created = 0
    for album_id in album_ids:
        album = Album.get_or_none(Album.id == album_id)
        if album is None:
            continue

        _, was_created = AlbumReviewTask.get_or_create(
            pending_key=f"{album.id}:pending",
            defaults={
                "album": album,
                "task_type": METADATA_REVIEW_TASK_TYPE,
                "status": PENDING_REVIEW_TASK_STATUS,
                "reason": NEW_ALBUM_REVIEW_REASON,
                "snapshot_json": buildAlbumReviewSnapshot(album),
            },
        )
        if was_created:
            created += 1
    return created


def createMissingYearAlbumReviewTasks() -> int:
    albums_without_year = list(
        Album.select().where(
            (Album.year.is_null()) | (Album.year == "")
        )
    )
    total_candidates = len(albums_without_year)
    skipped_pending = 0
    created = 0

    for album in albums_without_year:
        _, was_created = AlbumReviewTask.get_or_create(
            pending_key=f"{album.id}:pending",
            defaults={
                "album": album,
                "task_type": METADATA_REVIEW_TASK_TYPE,
                "status": PENDING_REVIEW_TASK_STATUS,
                "reason": MISSING_YEAR_REVIEW_REASON,
                "snapshot_json": buildAlbumReviewSnapshot(album),
            },
        )
        if not was_created:
            skipped_pending += 1
            continue
        created += 1

    logger.info(
        "Missing-year review task bootstrap: %d candidate albums, %d skipped (pending exists), %d created",
        total_candidates,
        skipped_pending,
        created,
    )
    return created


def runMissingYearAlbumReviewBootstrap() -> int:
    open_connection(reuse=True)
    try:
        return createMissingYearAlbumReviewTasks()
    finally:
        close_connection()
