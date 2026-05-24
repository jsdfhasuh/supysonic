"""Create album-scoped metadata review tasks after scan post-processing."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from ..db import Album, Artist, ReviewTask, close_connection, open_connection, now
from ..logging_utils import format_log_event

if TYPE_CHECKING:
    from ..scanner import Scanner

logger = logging.getLogger(__name__)

PENDING_REVIEW_TASK_STATUS = "pending"
CLOSED_REVIEW_TASK_STATUSES = {"confirmed", "dismissed", "expired"}
METADATA_REVIEW_TASK_TYPE = "metadata_review"
NEW_ALBUM_REVIEW_REASON = "new_album"
MISSING_YEAR_REVIEW_REASON = "missing_year"
EXTERNAL_ENRICHMENT_REVIEW_REASON = "external_enrichment"
NEW_ARTIST_REVIEW_REASON = "new_artist"
MISSING_IMAGE_REVIEW_REASON = "missing_image"
NEW_ARTIST_REVIEW_TTL_DAYS = 7
NEW_ALBUM_REVIEW_TTL_DAYS = 3
AUTO_CONFIRM_ALBUM_REVIEW_REASONS = (
    NEW_ALBUM_REVIEW_REASON,
    EXTERNAL_ENRICHMENT_REVIEW_REASON,
)


def rememberNewAlbum(scanner: Scanner, album: Album) -> None:
    if not hasattr(scanner, "review_task_album_ids"):
        scanner.review_task_album_ids = set()
    scanner.review_task_album_ids.add(album.id)


def rememberNewArtist(scanner: Scanner, artist) -> None:
    if not hasattr(scanner, "review_task_artist_ids"):
        scanner.review_task_artist_ids = set()
    scanner.review_task_artist_ids.add(artist.id)


def rememberExternalEnrichedAlbum(scanner: Scanner, album: Album) -> None:
    if not hasattr(scanner, "review_task_enriched_album_ids"):
        scanner.review_task_enriched_album_ids = set()
    scanner.review_task_enriched_album_ids.add(album.id)


def _getAlbumEnrichmentSnapshot(album: Album) -> dict:
    try:
        album_info = json.loads(album.album_info_json or "{}")
    except (TypeError, ValueError):
        album_info = {}
    if not isinstance(album_info, dict):
        album_info = {}
    enrichment = {}
    for key in (
        "providers_used",
        "source_urls",
        "genres",
        "styles",
        "primary_genre",
        "musicbrainz_id",
        "discogs_id",
        "last_enriched_at",
    ):
        value = album_info.get(key)
        if value not in (None, "", [], {}):
            enrichment[key] = value
    return enrichment


def buildAlbumReviewSnapshot(album: Album) -> str:
    snapshot = {
        "album_id": str(album.id),
        "album_name": album.name,
        "artist_name": album.artist.get_artist_name(),
        "year": album.year,
        "release_date": album.release_date,
        "release_type": album.release_type,
        "track_count": album.tracks.count(),
        "issues": getAlbumReviewIssues(album),
    }
    enrichment = _getAlbumEnrichmentSnapshot(album)
    if enrichment:
        snapshot["enrichment"] = enrichment
    return json.dumps(snapshot, ensure_ascii=False)


def buildArtistReviewSnapshot(artist) -> str:
    snapshot = {
        "artist_id": str(artist.id),
        "artist_name": artist.get_artist_name(),
        "issues": getArtistReviewIssues(artist),
    }
    return json.dumps(snapshot, ensure_ascii=False)


def getAlbumReviewReason(album: Album) -> str:
    return MISSING_YEAR_REVIEW_REASON if not album.year else NEW_ALBUM_REVIEW_REASON


def getAlbumReviewIssues(album: Album) -> list[str]:
    issues = []
    if not album.year:
        issues.append(MISSING_YEAR_REVIEW_REASON)
    if any(track.artist_id != album.artist_id for track in album.tracks):
        issues.append("track_artist_mapping_needs_review")
    return issues


def getArtistReviewIssues(artist) -> list[str]:
    artist_info = artist.get_info()
    if any(artist_info.get(key) for key in ("largeImageUrl", "mediumImageUrl", "smallImageUrl")):
        return []
    return [MISSING_IMAGE_REVIEW_REASON]


def _getTaskExpiry(task) -> object:
    if task.reason == NEW_ARTIST_REVIEW_REASON:
        return now() + timedelta(days=NEW_ARTIST_REVIEW_TTL_DAYS)
    if task.reason in AUTO_CONFIRM_ALBUM_REVIEW_REASONS:
        issues = json.loads(task.snapshot_json or "{}").get("issues", [])
        if not issues:
            return now() + timedelta(days=NEW_ALBUM_REVIEW_TTL_DAYS)
    return None


def _syncTask(task: ReviewTask) -> None:
    task.expires_at = _getTaskExpiry(task)
    task.updated = now()
    task.save()


def _upsertArtistTask(artist, reason, snapshot_json, expires_at=None):
    task, was_created = ReviewTask.get_or_create(
        pending_key=f"artist:{artist.id}:pending:{reason}",
        defaults={
            "entity_type": "artist",
            "entity_id": str(artist.id),
            "task_type": METADATA_REVIEW_TASK_TYPE,
            "status": PENDING_REVIEW_TASK_STATUS,
            "reason": reason,
            "snapshot_json": snapshot_json,
            "expires_at": expires_at,
        },
    )
    if was_created:
        task.expires_at = expires_at
        task.updated = now()
        task.save()
        return 1

    if task.snapshot_json == snapshot_json and task.expires_at == expires_at:
        return 0

    task.snapshot_json = snapshot_json
    task.expires_at = expires_at
    task.updated = now()
    task.save()
    return 0


def _confirmPendingArtistTasks(artist, reason, snapshot_json):
    updated = 0
    current_time = now()
    query = ReviewTask.select().where(
        ReviewTask.entity_type == "artist",
        ReviewTask.entity_id == str(artist.id),
        ReviewTask.status == PENDING_REVIEW_TASK_STATUS,
        ReviewTask.reason == reason,
    )
    for task in query:
        task.snapshot_json = snapshot_json
        task.status = "confirmed"
        task.resolved_at = current_time
        task.updated = current_time
        task.save()
        updated += 1
    return updated


def _deletePendingArtistTasks(artist, reason) -> int:
    removed = 0
    query = ReviewTask.select().where(
        ReviewTask.entity_type == "artist",
        ReviewTask.entity_id == str(artist.id),
        ReviewTask.status == PENDING_REVIEW_TASK_STATUS,
        ReviewTask.reason == reason,
    )
    for task in query:
        task.delete_instance()
        removed += 1
    return removed


def _getPendingTaskTitle(task: ReviewTask) -> str:
    snapshot = json.loads(task.snapshot_json or "{}")
    if task.is_artist_task():
        return snapshot.get("artist_name") or "Unknown artist"
    return snapshot.get("album_name") or "Unknown album"


def _getPendingTaskExpiryPolicy(task: ReviewTask) -> str:
    if task.expires_at is not None:
        return "expires"
    if task.reason == MISSING_IMAGE_REVIEW_REASON:
        return "awaiting_artist_image"
    if task.reason == MISSING_YEAR_REVIEW_REASON:
        return "awaiting_album_year"
    return "no_expiry_policy"


def _getCanonicalAlbumPendingKey(album: Album) -> str:
    return f"album:{album.id}:pending"


def _getLegacyAlbumPendingKey(album: Album) -> str:
    return f"{album.id}:pending"


def _getExternalAlbumPendingKey(album: Album) -> str:
    return f"album:{album.id}:pending:{EXTERNAL_ENRICHMENT_REVIEW_REASON}"


def _logExternalEnrichmentReviewTask(event: str, album: Album, task: ReviewTask) -> None:
    logger.info(
        format_log_event(
            "scanner",
            event,
            album_id=album.id,
            album=album.name,
            task_id=task.id,
            pending_key=task.pending_key or "-",
            reason=task.reason,
        )
    )


def _getPendingAlbumTask(album: Album):
    return (
        ReviewTask.select()
        .where(
            ReviewTask.entity_type == "album",
            ReviewTask.entity_id == str(album.id),
            ReviewTask.status == PENDING_REVIEW_TASK_STATUS,
        )
        .order_by(ReviewTask.created.asc())
        .first()
    )


def removeLegacyDuplicateAlbumPendingTasks() -> int:
    removed = 0
    pending_album_tasks = list(
        ReviewTask.select().where(
            ReviewTask.entity_type == "album",
            ReviewTask.status == PENDING_REVIEW_TASK_STATUS,
        )
    )
    canonical_pending_keys = {task.pending_key for task in pending_album_tasks if task.pending_key.startswith("album:")}

    for task in pending_album_tasks:
        if task.pending_key.startswith("album:"):
            continue
        album = task.get_album()
        if album is None:
            continue
        legacy_pending_key = _getLegacyAlbumPendingKey(album)
        canonical_pending_key = _getCanonicalAlbumPendingKey(album)
        if task.pending_key != legacy_pending_key or canonical_pending_key not in canonical_pending_keys:
            continue
        logger.info(
            "Removed legacy duplicate album review task: id=%s album_id=%s old_pending_key=%s canonical_pending_key=%s",
            task.id,
            album.id,
            task.pending_key,
            canonical_pending_key,
        )
        task.delete_instance()
        removed += 1

    return removed


def removeSupersededPendingNewArtistTasks() -> int:
    removed = 0
    pending_artist_tasks = list(
        ReviewTask.select().where(
            ReviewTask.entity_type == "artist",
            ReviewTask.status == PENDING_REVIEW_TASK_STATUS,
        )
    )
    artists_with_missing_image = {
        task.entity_id for task in pending_artist_tasks if task.reason == MISSING_IMAGE_REVIEW_REASON
    }

    for task in pending_artist_tasks:
        if task.reason != NEW_ARTIST_REVIEW_REASON or task.entity_id not in artists_with_missing_image:
            continue
        logger.info(
            "Removed superseded new-artist review task: id=%s artist_id=%s superseded_by=%s",
            task.id,
            task.entity_id,
            MISSING_IMAGE_REVIEW_REASON,
        )
        task.delete_instance()
        removed += 1

    return removed


def logPendingReviewTasks(context: str, include_details: bool = True) -> int:
    pending_tasks = list(
        ReviewTask.select()
        .where(ReviewTask.status == PENDING_REVIEW_TASK_STATUS)
        .order_by(ReviewTask.created.asc())
    )
    logger.info("Pending review tasks after %s: %d", context, len(pending_tasks))
    if not include_details:
        return len(pending_tasks)
    for task in pending_tasks:
        expires_at = task.expires_at.isoformat() if task.expires_at is not None else "-"
        logger.info(
            "Pending review task detail: id=%s entity_type=%s entity_id=%s reason=%s title=%s expires_at=%s expiry_policy=%s",
            task.id,
            task.entity_type,
            task.entity_id,
            task.reason,
            _getPendingTaskTitle(task),
            expires_at,
            _getPendingTaskExpiryPolicy(task),
        )
    return len(pending_tasks)


def createAlbumReviewTasks(scanner: Scanner) -> int:
    album_ids = getattr(scanner, "review_task_album_ids", set())
    created = 0
    for album_id in album_ids:
        album = Album.get_or_none(Album.id == album_id)
        if album is None:
            continue

        snapshot_json = buildAlbumReviewSnapshot(album)
        reason = getAlbumReviewReason(album)
        existing_task = _getPendingAlbumTask(album)
        if existing_task is not None:
            if existing_task.reason == reason and existing_task.snapshot_json == snapshot_json:
                continue
            existing_task.reason = reason
            existing_task.snapshot_json = snapshot_json
            _syncTask(existing_task)
            continue

        task, was_created = ReviewTask.get_or_create(
            pending_key=f"album:{album.id}:pending",
            defaults={
                "entity_type": "album",
                "entity_id": str(album.id),
                "task_type": METADATA_REVIEW_TASK_TYPE,
                "status": PENDING_REVIEW_TASK_STATUS,
                "reason": reason,
                "snapshot_json": snapshot_json,
                "expires_at": None,
            },
        )
        if was_created:
            _syncTask(task)
            created += 1
            continue

        if task.reason == reason and task.snapshot_json == snapshot_json:
            continue

        task.reason = reason
        task.snapshot_json = snapshot_json
        _syncTask(task)

    enriched_album_ids = getattr(scanner, "review_task_enriched_album_ids", set())
    for album_id in enriched_album_ids:
        album = Album.get_or_none(Album.id == album_id)
        if album is None:
            continue

        snapshot_json = buildAlbumReviewSnapshot(album)
        existing_task = _getPendingAlbumTask(album)
        if existing_task is not None:
            if existing_task.snapshot_json != snapshot_json:
                existing_task.snapshot_json = snapshot_json
                _syncTask(existing_task)
                _logExternalEnrichmentReviewTask(
                    "external_enrichment_review_task_updated",
                    album,
                    existing_task,
                )
            else:
                _logExternalEnrichmentReviewTask(
                    "external_enrichment_review_task_merged_existing",
                    album,
                    existing_task,
                )
            continue

        task, was_created = ReviewTask.get_or_create(
            pending_key=_getExternalAlbumPendingKey(album),
            defaults={
                "entity_type": "album",
                "entity_id": str(album.id),
                "task_type": METADATA_REVIEW_TASK_TYPE,
                "status": PENDING_REVIEW_TASK_STATUS,
                "reason": EXTERNAL_ENRICHMENT_REVIEW_REASON,
                "snapshot_json": snapshot_json,
                "expires_at": None,
            },
        )
        if was_created:
            _syncTask(task)
            created += 1
            _logExternalEnrichmentReviewTask(
                "external_enrichment_review_task_created",
                album,
                task,
            )
            continue

        if task.snapshot_json != snapshot_json:
            task.snapshot_json = snapshot_json
            _syncTask(task)
            _logExternalEnrichmentReviewTask(
                "external_enrichment_review_task_updated",
                album,
                task,
            )
        else:
            _logExternalEnrichmentReviewTask(
                "external_enrichment_review_task_merged_existing",
                album,
                task,
            )
    return created


def createArtistReviewTasks(scanner: Scanner) -> int:
    artist_ids = getattr(scanner, "review_task_artist_ids", set())
    created = 0

    for artist_id in artist_ids:
        artist = Artist.get_or_none(Artist.id == artist_id)
        if artist is None:
            continue

        snapshot_json = buildArtistReviewSnapshot(artist)
        issues = getArtistReviewIssues(artist)
        if MISSING_IMAGE_REVIEW_REASON in issues:
            created += _upsertArtistTask(
                artist,
                MISSING_IMAGE_REVIEW_REASON,
                snapshot_json,
                None,
            )
            created += _deletePendingArtistTasks(artist, NEW_ARTIST_REVIEW_REASON)
        else:
            created += _upsertArtistTask(
                artist,
                NEW_ARTIST_REVIEW_REASON,
                snapshot_json,
                now() + timedelta(days=NEW_ARTIST_REVIEW_TTL_DAYS),
            )
            _confirmPendingArtistTasks(
                artist,
                MISSING_IMAGE_REVIEW_REASON,
                snapshot_json,
            )
    return created


def createReviewTasks(scanner: Scanner) -> int:
    return createAlbumReviewTasks(scanner) + createArtistReviewTasks(scanner)


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
        _, was_created = ReviewTask.get_or_create(
            pending_key=f"album:{album.id}:pending",
            defaults={
                "entity_type": "album",
                "entity_id": str(album.id),
                "task_type": METADATA_REVIEW_TASK_TYPE,
                "status": PENDING_REVIEW_TASK_STATUS,
                "reason": MISSING_YEAR_REVIEW_REASON,
                "snapshot_json": buildAlbumReviewSnapshot(album),
                "expires_at": None,
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


def createMissingImageArtistReviewTasks() -> int:
    created = 0
    for artist in Artist.select():
        if not getArtistReviewIssues(artist):
            continue

        task, was_created = ReviewTask.get_or_create(
            pending_key=f"artist:{artist.id}:pending:{MISSING_IMAGE_REVIEW_REASON}",
            defaults={
                "entity_type": "artist",
                "entity_id": str(artist.id),
                "task_type": METADATA_REVIEW_TASK_TYPE,
                "status": PENDING_REVIEW_TASK_STATUS,
                "reason": MISSING_IMAGE_REVIEW_REASON,
                "snapshot_json": buildArtistReviewSnapshot(artist),
                "expires_at": None,
            },
        )
        if not was_created:
            continue
        task.updated = now()
        task.save()
        created += 1
    return created


def expirePendingNewArtistTasks() -> int:
    updated = 0
    current_time = now()
    query = ReviewTask.select().where(
        ReviewTask.entity_type == "artist",
        ReviewTask.status == PENDING_REVIEW_TASK_STATUS,
        ReviewTask.reason == NEW_ARTIST_REVIEW_REASON,
        ReviewTask.expires_at.is_null(False),
        ReviewTask.expires_at <= current_time,
    )
    for task in query:
        task.status = "expired"
        task.resolved_at = current_time
        task.updated = current_time
        task.save()
        updated += 1
    return updated


def backfillPendingAlbumTaskExpiries() -> int:
    updated = 0
    query = ReviewTask.select().where(
        ReviewTask.entity_type == "album",
        ReviewTask.status == PENDING_REVIEW_TASK_STATUS,
        ReviewTask.reason.in_(AUTO_CONFIRM_ALBUM_REVIEW_REASONS),
        ReviewTask.expires_at.is_null(True),
    )
    for task in query:
        album = task.get_album()
        if album is None or getAlbumReviewIssues(album):
            continue
        task.expires_at = task.created + timedelta(days=NEW_ALBUM_REVIEW_TTL_DAYS)
        task.updated = now()
        task.save()
        updated += 1
    return updated


def confirmCleanAutoExpireAlbumTasks() -> int:
    updated = 0
    current_time = now()
    query = ReviewTask.select().where(
        ReviewTask.entity_type == "album",
        ReviewTask.status == PENDING_REVIEW_TASK_STATUS,
        ReviewTask.reason.in_(AUTO_CONFIRM_ALBUM_REVIEW_REASONS),
        ReviewTask.expires_at.is_null(False),
        ReviewTask.expires_at <= current_time,
    )
    for task in query:
        album = task.get_album()
        if album is None or getAlbumReviewIssues(album):
            continue
        task.status = "confirmed"
        task.resolved_at = current_time
        task.updated = current_time
        task.save()
        updated += 1
    return updated


def createReviewTaskBootstrap() -> int:
    return (
        createMissingYearAlbumReviewTasks()
        + createMissingImageArtistReviewTasks()
        + removeLegacyDuplicateAlbumPendingTasks()
        + removeSupersededPendingNewArtistTasks()
    )


def runReviewTaskBootstrap() -> int:
    open_connection(reuse=True)
    try:
        created = createReviewTaskBootstrap()
        logPendingReviewTasks("bootstrap")
        return created
    finally:
        close_connection()


def createReviewTaskMaintenance() -> int:
    return (
        removeLegacyDuplicateAlbumPendingTasks()
        + removeSupersededPendingNewArtistTasks()
        +
        expirePendingNewArtistTasks()
        + backfillPendingAlbumTaskExpiries()
        + confirmCleanAutoExpireAlbumTasks()
    )


def runReviewTaskMaintenance() -> int:
    open_connection(reuse=True)
    try:
        updated = createReviewTaskMaintenance()
        logPendingReviewTasks("maintenance", include_details=False)
        return updated
    finally:
        close_connection()


def runMissingYearAlbumReviewBootstrap() -> int:
    open_connection(reuse=True)
    try:
        return createMissingYearAlbumReviewTasks()
    finally:
        close_connection()
